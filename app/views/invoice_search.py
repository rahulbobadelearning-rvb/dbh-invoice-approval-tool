# REMARK: Search is intentionally read-heavy.  The user should be able
# to find any past invoice in seconds, download the original PDF, and
# delete records that were uploaded in error (with confirmation).

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from core.db import delete_invoice, get_connection, list_invoices, list_vendors
from core.ui_tokens import COLOR_DANGER, COLOR_TEXT_SECONDARY


def render() -> None:
    st.markdown(
        "<h1 style='font-size:1.6rem; font-weight:800; margin-bottom:4px;'>Invoice Search</h1>"
        f"<p style='color:{COLOR_TEXT_SECONDARY}; font-size:0.85rem; margin-top:0;'>"
        "Search, download, and manage uploaded invoices.</p>",
        unsafe_allow_html=True,
    )

    # ── Filter bar ────────────────────────────────────────────────────────────
    vendors = list_vendors()
    vendor_options = {"All Vendors": None}
    vendor_options.update({f"{v['vendor_name']} ({v['vendor_code']})": v["id"] for v in vendors})

    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        vendor_label = st.selectbox("Vendor", list(vendor_options.keys()))
        vendor_id = vendor_options[vendor_label]

    with col2:
        search_text = st.text_input("Invoice number / amount", placeholder="INV-001 or 12500…")

    with col3:
        # Month range filter (YYYY-MM)
        from datetime import datetime
        current_year = datetime.now().year
        month_opts = ["All Months"] + [
            f"{y}-{m:02d}"
            for y in range(current_year - 2, current_year + 2)
            for m in range(1, 13)
        ]
        selected_month = st.selectbox("Service Month", month_opts)

    # ── Fetch and filter ──────────────────────────────────────────────────────
    rows = list_invoices(vendor_id=vendor_id)

    if not rows:
        st.info("No invoices found. Upload invoices via **Upload Invoice**.")
        return

    df = _build_display_df(rows)

    # Text filter
    if search_text:
        mask = (
            df["Invoice No"].str.contains(search_text, case=False, na=False)
            | df["Amount"].str.contains(search_text, case=False, na=False)
        )
        df = df[mask]

    # Month filter
    if selected_month != "All Months":
        df = df[df["Service Month"] == selected_month]

    # ── Results summary ───────────────────────────────────────────────────────
    total_amount = 0.0
    for row in rows:
        total_amount += row["invoice_amount"]

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.caption(f"Showing **{len(df)}** of **{len(rows)}** invoices")
    with col_b:
        st.caption(f"Total visible: **${df['_amount_raw'].sum():,.2f}**" if not df.empty else "")

    # ── Table ─────────────────────────────────────────────────────────────────
    if df.empty:
        st.warning("No invoices match the current filters.")
        return

    display_cols = ["Vendor", "Code", "Invoice No", "Invoice Date", "Service Month", "Amount", "Uploaded"]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True, height=420)

    # ── Row-level actions ─────────────────────────────────────────────────────
    st.markdown("<hr class='mds-divider'>", unsafe_allow_html=True)
    st.markdown("<div class='mds-section-title'>Actions</div>", unsafe_allow_html=True)

    # Build label map from visible rows (using original db id)
    id_options = {
        f"#{r['id']} — {r['vendor_name']} | {r['invoice_number'] or 'No No.'} | {r['service_month']} | ${r['invoice_amount']:,.2f}": r["id"]
        for r in rows
        if str(r["id"]) in df["_id"].values
    }

    if not id_options:
        return

    selected_label = st.selectbox("Select invoice", list(id_options.keys()))
    selected_id = id_options[selected_label]

    # Find the row
    selected_row = next((r for r in rows if r["id"] == selected_id), None)

    col_dl, col_del = st.columns([1, 1])

    with col_dl:
        if selected_row and selected_row["pdf_path"]:
            pdf_path = Path(selected_row["pdf_path"])
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇️  Download PDF",
                        data=f,
                        file_name=pdf_path.name,
                        mime="application/pdf",
                    )
            else:
                st.warning("PDF file not found on disk.")
        else:
            st.caption("No PDF attached to this invoice.")

    with col_del:
        if st.button("🗑️  Delete this invoice", type="secondary"):
            if st.session_state.get("confirm_delete") == selected_id:
                delete_invoice(selected_id)
                st.session_state.pop("confirm_delete", None)
                st.success("Invoice deleted.")
                st.rerun()
            else:
                st.session_state["confirm_delete"] = selected_id
                st.warning("Click delete again to confirm deletion.")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_display_df(rows: list) -> pd.DataFrame:
    records = []
    for r in rows:
        records.append(
            {
                "_id": str(r["id"]),
                "_amount_raw": r["invoice_amount"],
                "Vendor": r["vendor_name"],
                "Code": r["vendor_code"],
                "Invoice No": r["invoice_number"] or "—",
                "Invoice Date": r["invoice_date"] or "—",
                "Service Month": r["service_month"],
                "Amount": f"${r['invoice_amount']:,.2f}",
                "Uploaded": (r["upload_timestamp"] or "")[:10],
            }
        )
    return pd.DataFrame(records)
