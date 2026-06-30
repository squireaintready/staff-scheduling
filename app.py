"""
Employee Scheduling & Payroll Application

Streamlit entry point: page configuration, styling, the authentication gate,
and sidebar navigation. Each page lives in its own module under ``views/``;
the business logic lives in ``payroll.py`` and the data layer in ``database.py``.
"""

import streamlit as st

import database  # noqa: F401  -- imported for its init-database-on-import side effect
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


def main():
    # Authentication gate — nothing renders until the manager logs in.
    if not check_password():
        return

    st.title("Employee Scheduling & Payroll")

    page = st.sidebar.radio("Navigation", list(PAGES.keys()))

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()

    PAGES[page]()


if __name__ == "__main__":
    main()
