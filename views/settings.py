"""App settings view: overtime rules, defaults, data management."""


import streamlit as st

import database as db
from timeutils import (
    TIME_LABELS,
    get_time_index,
    label_to_time,
    time_to_label,
)


def render():
    """App settings page."""
    st.header("Settings")

    settings = db.get_all_settings()

    st.subheader("Overtime Rules")

    col1, col2 = st.columns(2)

    with col1:
        weekly_threshold = st.number_input(
            "Weekly Overtime Threshold (hours)",
            min_value=0.0,
            max_value=168.0,
            value=float(settings.get('overtime_weekly_threshold', 40)),
            step=1.0,
            help="Hours worked beyond this per week are overtime"
        )

    with col2:
        daily_threshold = st.number_input(
            "Daily Overtime Threshold (hours)",
            min_value=0.0,
            max_value=24.0,
            value=float(settings.get('overtime_daily_threshold', 8)),
            step=0.5,
            help="Hours worked beyond this per day are overtime"
        )

    ot_multiplier = st.number_input(
        "Overtime Pay Multiplier",
        min_value=1.0,
        max_value=3.0,
        value=float(settings.get('overtime_multiplier', 1.5)),
        step=0.1,
        help="Overtime hours are paid at this multiple of regular rate"
    )

    st.divider()

    st.subheader("Default Times")

    close_time_24 = settings.get('default_close_time', '21:00')
    close_label = time_to_label(close_time_24)
    default_close = st.selectbox(
        "Default Close Time",
        TIME_LABELS,
        index=get_time_index(close_label, "9PM"),
        help="Used when shift end time is not specified"
    )

    st.divider()

    if st.button("Save Settings", type="primary"):
        db.set_setting('overtime_weekly_threshold', str(weekly_threshold))
        db.set_setting('overtime_daily_threshold', str(daily_threshold))
        db.set_setting('overtime_multiplier', str(ot_multiplier))
        db.set_setting('default_close_time', label_to_time(default_close))
        st.success("Settings saved!")

    st.divider()

    # Danger zone
    st.subheader("Data Management")

    with st.expander("Danger Zone", expanded=False):
        st.warning("These actions cannot be undone!")

        if st.button("Clear All Shifts"):
            with db.get_connection() as conn:
                conn.execute("DELETE FROM shifts")
            st.success("All shifts cleared")
            st.rerun()
