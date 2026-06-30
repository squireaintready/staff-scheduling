"""
Employee Scheduling & Payroll Application

Streamlit entry point: page configuration, styling, the authentication gate,
and sidebar navigation. Each page lives in its own module under ``views/``;
the business logic lives in ``payroll.py`` and the data layer in ``database.py``.
"""

import streamlit as st

import database  # used for the demo seed; also runs init_database() on import
from auth import check_password
from styles import inject_styles
from views import employees, payroll, schedule, settings, templates

st.set_page_config(
    page_title="Employee Scheduling & Payroll",
    page_icon="📅",
    layout="wide",
)

inject_styles()

# Sidebar label -> page render function.
PAGES = {
    "Schedule": schedule.render,
    "Employees": employees.render,
    "Shift Templates": templates.render,
    "Payroll": payroll.render,
    "Settings": settings.render,
}


def _maybe_seed_demo():
    """In demo mode, populate sample data when the database is empty.

    Gated behind the ``demo_mode`` secret so it never affects a real
    deployment. Streamlit Community Cloud has an ephemeral filesystem, so this
    quietly repopulates the demo after each cold start.
    """
    if st.session_state.get("_demo_checked"):
        return
    st.session_state["_demo_checked"] = True
    try:
        demo_mode = st.secrets.get("demo_mode", False)
    except Exception:
        demo_mode = False
    if demo_mode and not database.get_employees(active_only=False):
        import seed_demo
        seed_demo.seed()


def main():
    # Authentication gate — nothing renders until the manager logs in.
    if not check_password():
        return

    _maybe_seed_demo()

    st.title("Employee Scheduling & Payroll")

    page = st.sidebar.radio("Navigation", list(PAGES.keys()))

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()

    PAGES[page]()


if __name__ == "__main__":
    main()
