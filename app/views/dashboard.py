# REMARK: The dashboard is a read-only executive view.
# It surfaces the most critical signals (runway risk, overspend) without
# requiring the user to open individual vendor records.

from datetime import date, datetime
from typing import Optional

import pandas as pd
import streamlit as st

from core.analytics import get_dashboard_rows
from core.db import get_connection
from core.ui_tokens import (
    COLOR_ACCENT,
    COLOR_BG_CARD,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    GLOBAL_CSS,
    status_badge,
)


def render() -> None:
    st.markdown(
        f"<h1 style='font-size:1.6rem; font-weight:800; margin-bottom:4px;'>Dashboard</h1>"
        f"<p style='color:{COLOR_TEXT_SECONDARY}; font-size:0.85rem; margin-top:0;'>"
        f"Vendor PO health · spend runway · YTD consumption</p>",
        unsafe_allow_html=True,
    )

    rows = get_dashboard_rows()

    if not rows:
        st.info("No vendors yet. Add vendors in **Vendor Master** to see analytics here.")
        return

    # ── KPI bar ──────────────────────────────────────────────────────────────
    _render_kpis(rows)

    st.markdown("<hr class='mds-divider'>", unsafe_allow_html=True)

    # ── Filter bar ───────────────────────────────────────────────────────────
    col_filter, col_sort = st.columns([3, 2])
    with col_filter:
        search = st.text_input("Filter vendors", placeholder="Vendor name or code…", label_visibility="collapsed")
    with col_sort:
        sort_by = st.selectbox(
            "Sort by",
            ["Vendor Name", "YTD Spend", "Remaining PO", "Runway Status", "PO Expiration"],
            label_visibility="collapsed",
        )

    df = pd.DataFrame(rows)

    # Apply search filter
    if search:
        mask = (
            df["Vendor Name"].str.contains(search, case=False, na=False)
            | df["Vendor Code"].str.contains(search, case=False, na=False)
        )
        df = df[mask]

    # Apply sort
    ascending = sort_by not in ("YTD Spend",)
    df = df.sort_values(sort_by, ascending=ascending, ignore_index=True)

    if df.empty:
        st.warning("No vendors match the filter.")
        return

    # ── Vendor table ──────────────────────────────────────────────────────────
    st.markdown(
        "<div class='mds-section-title'>Vendor Spend Overview</div>",
        unsafe_allow_html=True,
    )

    _render_vendor_table(df)

    # ── Risk highlights ───────────────────────────────────────────────────────
    _render_risk_panel(df)


# ---------------------------------------------------------------------------
# Sub-renders
# ---------------------------------------------------------------------------

def _render_kpis(rows: list[dict]) -> None:
    total_vendors = len(rows)
    total_ytd = sum(r["YTD Spend"] for r in rows)
    total_po = sum(r["PO Value"] for r in rows)
    at_risk = sum(1 for r in rows if r["Runway Status"] in ("Risk", "Expired"))

    with get_connection() as conn:
        invoice_count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Vendors", total_vendors)
    c2.metric("Total PO Value", f"${total_po:,.0f}")
    c3.metric("YTD Spend", f"${total_ytd:,.0f}")
    c4.metric("Invoices Uploaded", invoice_count)
    c5.metric("At-Risk Vendors", at_risk, delta=None)


def _render_vendor_table(df: pd.DataFrame) -> None:
    # Build display DataFrame with formatted columns
    display = pd.DataFrame()
    display["Vendor Name"] = df["Vendor Name"]
    display["Vendor Code"] = df["Vendor Code"]
    display["PO Value"] = df["PO Value"].apply(lambda x: f"${x:,.0f}")
    display["PO Expiration"] = df["PO Expiration"]
    display["Avg Monthly"] = df["Avg Monthly"].apply(lambda x: f"${x:,.0f}")
    display["Last Monthly"] = df["Last Monthly"].apply(lambda x: f"${x:,.0f}")
    display["YTD Spend"] = df["YTD Spend"].apply(lambda x: f"${x:,.0f}")
    display["Remaining PO"] = df["Remaining PO"].apply(
        lambda x: f"${x:,.0f}" if x >= 0 else f"-${abs(x):,.0f}"
    )
    display["Months Left"] = df["Months Left"].apply(
        lambda x: str(x) if x is not None else "—"
    )
    display["Runway"] = df["Runway Status"]

    # Colour-code Runway column via Styler
    def colour_runway(val: str) -> str:
        if val == "On Track":
            return f"color: {COLOR_SUCCESS}; font-weight:700;"
        if val == "Risk":
            return f"color: {COLOR_WARNING}; font-weight:700;"
        if val == "Expired":
            return f"color: {COLOR_DANGER}; font-weight:700;"
        return ""

    styled = display.style.map(colour_runway, subset=["Runway"])

    # Highlight over-spent remaining PO
    def highlight_remaining(val: str) -> str:
        if val.startswith("-"):
            return f"background-color: #FEE2E2; color: {COLOR_DANGER}; font-weight:700;"
        return ""

    styled = styled.map(highlight_remaining, subset=["Remaining PO"])

    st.dataframe(styled, use_container_width=True, hide_index=True, height=420)


def _render_risk_panel(df: pd.DataFrame) -> None:
    at_risk = df[df["Runway Status"].isin(["Risk", "Expired"])]
    expiring_soon = df[
        df["PO Expiration"].apply(_expires_within_60_days)
    ]

    if at_risk.empty and expiring_soon.empty:
        st.success("All vendors are on track. No immediate risks detected.")
        return

    st.markdown("<hr class='mds-divider'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='mds-section-title'>Risk Alerts</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        if not at_risk.empty:
            st.markdown(
                f"<div style='color:{COLOR_DANGER}; font-weight:700; margin-bottom:8px;'>"
                f"⚠ Budget Risk ({len(at_risk)} vendor{'s' if len(at_risk)>1 else ''})</div>",
                unsafe_allow_html=True,
            )
            for _, row in at_risk.iterrows():
                st.markdown(
                    f"**{row['Vendor Name']}** — {row['Runway Status']} · "
                    f"Remaining: {row['Remaining PO']}",
                )

    with c2:
        if not expiring_soon.empty:
            st.markdown(
                f"<div style='color:{COLOR_WARNING}; font-weight:700; margin-bottom:8px;'>"
                f"⏰ PO Expiring Soon ({len(expiring_soon)} vendor{'s' if len(expiring_soon)>1 else ''})</div>",
                unsafe_allow_html=True,
            )
            for _, row in expiring_soon.iterrows():
                st.markdown(
                    f"**{row['Vendor Name']}** — expires {row['PO Expiration']}"
                )


def _expires_within_60_days(expiry_str: str) -> bool:
    if expiry_str in ("—", "", None):
        return False
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        delta = (expiry - date.today()).days
        return 0 <= delta <= 60
    except ValueError:
        return False
