# REMARK: The Vendor Master is the source of truth for PO limits and
# ownership.  Every invoice must link to a vendor — no orphan invoices.
# Full CRUD is here so the manager can maintain it without touching the DB.

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from core.db import (
    delete_vendor,
    get_vendor_by_id,
    insert_vendor,
    list_vendors,
    update_vendor,
)
from core.ui_tokens import (
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_SECONDARY,
    SPACING_MD,
)


def render() -> None:
    st.markdown(
        "<h1 style='font-size:1.6rem; font-weight:800; margin-bottom:4px;'>Vendor Master</h1>"
        f"<p style='color:{COLOR_TEXT_SECONDARY}; font-size:0.85rem; margin-top:0;'>"
        "Add, edit, and manage vendor contracts and PO limits.</p>",
        unsafe_allow_html=True,
    )

    tab_list, tab_add = st.tabs(["📋  Vendor List", "➕  Add Vendor"])

    with tab_list:
        _render_vendor_list()

    with tab_add:
        _render_add_form()


# ---------------------------------------------------------------------------
# Vendor list with inline edit / delete
# ---------------------------------------------------------------------------

def _render_vendor_list() -> None:
    vendors = list_vendors()

    if not vendors:
        st.info("No vendors registered yet. Use the **Add Vendor** tab to get started.")
        return

    # Build display table
    rows = [
        {
            "ID": v["id"],
            "Name": v["vendor_name"],
            "Code": v["vendor_code"],
            "PO Number": v["po_number"] or "—",
            "PO Value": f"${v['po_value']:,.0f}",
            "Expiration": v["po_expiration_date"] or "—",
            "Owner": v["application_owner"] or "—",
        }
        for v in vendors
    ]

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown(f"<hr class='mds-divider'>", unsafe_allow_html=True)

    # Edit / Delete controls
    vendor_options = {f"{v['vendor_name']} ({v['vendor_code']})": v["id"] for v in vendors}
    selected_label = st.selectbox("Select vendor to edit or delete", list(vendor_options.keys()))
    selected_id = vendor_options[selected_label]
    selected = get_vendor_by_id(selected_id)

    if selected:
        col_edit, col_del = st.columns([1, 1])

        with col_edit:
            with st.expander("✏️  Edit this vendor", expanded=False):
                _render_edit_form(selected)

        with col_del:
            st.markdown(f"<div style='padding-top:{SPACING_MD}px;'>", unsafe_allow_html=True)
            if st.button("🗑️  Delete vendor", type="secondary"):
                try:
                    delete_vendor(selected_id)
                    st.success(f"Vendor '{selected['vendor_name']}' deleted.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.markdown("</div>", unsafe_allow_html=True)


def _render_edit_form(vendor: dict) -> None:
    with st.form(f"edit_vendor_{vendor['id']}"):
        name = st.text_input("Vendor Name *", value=vendor["vendor_name"])
        code = st.text_input("Vendor Code *", value=vendor["vendor_code"])
        po_num = st.text_input("PO Number", value=vendor["po_number"] or "")
        po_val = st.number_input("PO Value *", min_value=0.0, value=float(vendor["po_value"]), step=1000.0, format="%.2f")
        expiry_val = None
        if vendor["po_expiration_date"]:
            try:
                from datetime import datetime
                expiry_val = datetime.strptime(vendor["po_expiration_date"], "%Y-%m-%d").date()
            except ValueError:
                expiry_val = None
        expiry = st.date_input("PO Expiration Date", value=expiry_val)
        owner = st.text_input("Application Owner", value=vendor["application_owner"] or "")

        submitted = st.form_submit_button("Save Changes", type="primary")
        if submitted:
            if not name.strip() or not code.strip():
                st.error("Vendor Name and Vendor Code are required.")
            else:
                from core.pdf_utils import validate_vendor_code
                import sys
                try:
                    safe_code = validate_vendor_code(code)
                    update_vendor(
                        vendor_id=vendor["id"],
                        vendor_name=name.strip()[:200],
                        vendor_code=safe_code,
                        po_number=po_num.strip()[:100],
                        po_value=po_val,
                        po_expiration_date=expiry.strftime("%Y-%m-%d") if expiry else None,
                        application_owner=owner.strip()[:200],
                    )
                    st.success("Vendor updated successfully.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    # Log full error server-side; show generic message to user
                    print(f"[ERROR] Vendor update failed: {exc}", file=sys.stderr)
                    st.error("Could not update vendor. Please check the input and try again.")


# ---------------------------------------------------------------------------
# Add vendor form
# ---------------------------------------------------------------------------

def _render_add_form() -> None:
    st.markdown(
        "<div class='mds-section-title'>New Vendor</div>",
        unsafe_allow_html=True,
    )

    with st.form("add_vendor_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Vendor Name *", placeholder="Acme Corp")
            code = st.text_input("Vendor Code *", placeholder="ACME001")
            po_num = st.text_input("PO Number", placeholder="PO-2024-001")

        with col2:
            po_val = st.number_input("PO Value *", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
            expiry = st.date_input("PO Expiration Date", value=None, min_value=date.today())
            owner = st.text_input("Application Owner", placeholder="Jane Smith")

        submitted = st.form_submit_button("➕  Add Vendor", type="primary")

        if submitted:
            from core.pdf_utils import validate_vendor_code
            import sys
            errors = []
            if not name.strip():
                errors.append("Vendor Name is required.")
            if not code.strip():
                errors.append("Vendor Code is required.")
            if po_val <= 0:
                errors.append("PO Value must be greater than 0.")

            # Validate vendor code format to prevent path traversal
            safe_code = None
            if code.strip():
                try:
                    safe_code = validate_vendor_code(code)
                except ValueError as exc:
                    errors.append(str(exc))

            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    insert_vendor(
                        vendor_name=name.strip()[:200],
                        vendor_code=safe_code,
                        po_number=po_num.strip()[:100],
                        po_value=po_val,
                        po_expiration_date=expiry.strftime("%Y-%m-%d") if expiry else None,
                        application_owner=owner.strip()[:200],
                    )
                    st.success(f"✅ Vendor **{name.strip()}** added successfully.")
                except Exception as exc:
                    print(f"[ERROR] Vendor insert failed: {exc}", file=sys.stderr)
                    if "UNIQUE constraint" in str(exc):
                        st.error("A vendor with that code already exists. Use a different Vendor Code.")
                    else:
                        st.error("Could not add vendor. Please check the input and try again.")
