# REMARK: main.py is the single Streamlit entry point.
# It owns: global CSS injection, DB initialisation, and sidebar navigation.
# All page logic lives in views/ (not pages/ — that name triggers Streamlit's
# built-in multipage detection which would duplicate the navigation).

import sys
from pathlib import Path

# Make sure `core/` and `views/` resolve correctly regardless of where
# streamlit is invoked from.
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from core.db import initialize_database
from core.ui_tokens import (
    COLOR_ACCENT,
    COLOR_BG_APP,
    COLOR_BG_CARD,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    GLOBAL_CSS,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
)

# ── Page config — must be the first Streamlit call ───────────────────────────
st.set_page_config(
    page_title="Invoice Approval Tool",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject Maersk Design System–aligned CSS
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# Ensure DB tables exist on every startup (idempotent)
initialize_database()

# ── Sidebar navigation ────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("📊", "Dashboard"),
    ("🏢", "Vendor Master"),
    ("📤", "Upload Invoice"),
    ("🔍", "Invoice Search"),
    ("📈", "Vendor Detail"),
]

with st.sidebar:
    st.markdown(
        f"""
        <div style="padding-bottom:{SPACING_LG}px; border-bottom:1px solid {COLOR_BORDER}; margin-bottom:{SPACING_MD}px;">
          <div style="font-size:1.15rem; font-weight:800; color:{COLOR_ACCENT}; letter-spacing:-0.01em;">
            Invoice Approval
          </div>
          <div style="font-size:0.72rem; color:{COLOR_TEXT_SECONDARY}; text-transform:uppercase;
                      letter-spacing:0.08em; margin-top:2px;">
            Vendor · PO · Compliance
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selection = st.radio(
        "Navigate",
        [label for _, label in NAV_ITEMS],
        format_func=lambda label: next(
            f"{icon}  {label}" for icon, lbl in NAV_ITEMS if lbl == label
        ),
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border:none; border-top:1px solid #D1D9E0; margin:24px 0 12px;'>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.68rem; color:{COLOR_TEXT_SECONDARY};'>"
        "100 % local · no cloud · auditable</div>",
        unsafe_allow_html=True,
    )

# ── Page routing ──────────────────────────────────────────────────────────────
if selection == "Dashboard":
    from views.dashboard import render
    render()

elif selection == "Vendor Master":
    from views.vendor_master import render
    render()

elif selection == "Upload Invoice":
    from views.upload_invoice import render
    render()

elif selection == "Invoice Search":
    from views.invoice_search import render
    render()

elif selection == "Vendor Detail":
    from views.vendor_detail import render
    render()
