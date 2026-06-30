"""Authentication for the scheduling app.

A single shared manager password is read from Streamlit secrets and compared
with ``hmac.compare_digest`` to avoid leaking timing information. The password
is never stored in the repository — see the README's Security section.
"""

import hmac

import streamlit as st


def check_password() -> bool:
    """Gate the app behind a single shared password. Returns True if authed."""
    # Already authenticated this session.
    if st.session_state.get("authenticated"):
        return True

    # Get password from secrets.
    try:
        correct_password = st.secrets["password"]
    except Exception:
        st.error("Password not configured. Add to Streamlit secrets.")
        st.code('password = "your-password-here"')
        return False

    # Show login form.
    st.title("Employee Scheduling & Payroll")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", type="primary"):
        if hmac.compare_digest(password, correct_password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password")

    return False
