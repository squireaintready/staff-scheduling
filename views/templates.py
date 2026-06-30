"""Shift-template management view."""


import streamlit as st

import database as db
import payroll as pr
from timeutils import (
    TIME_LABELS,
    format_time_range,
    get_time_index,
    label_to_time,
    should_have_lunch,
    time_to_label,
)


def render():
    """Shift templates management."""
    st.header("Shift Templates")

    # Add new template
    with st.expander("Add New Template", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            new_name = st.text_input("Template Name", placeholder="e.g., Morning", key="new_tmpl_name")

        with col2:
            new_color = st.color_picker("Color", value="#3498db", key="new_tmpl_color")

        st.write("**Shift Time**")
        time_cols = st.columns(4)
        with time_cols[0]:
            new_start = st.selectbox("Start", TIME_LABELS, index=get_time_index("9AM"), key="new_tmpl_start")
        with time_cols[1]:
            new_end = st.selectbox("End", TIME_LABELS, index=get_time_index("5PM"), key="new_tmpl_end")

        # Check if shift qualifies for lunch based on times
        start_24 = label_to_time(new_start)
        end_24 = label_to_time(new_end)
        should_no_lunch = not should_have_lunch(start_24, end_24)

        st.write("**Lunch Break** (optional, default 3-4PM)")
        lunch_cols = st.columns([1, 1, 0.7, 1.3])
        with lunch_cols[0]:
            new_lunch_start = st.selectbox("Lunch Start", TIME_LABELS, index=get_time_index("3PM"), key="new_tmpl_lunch_start", disabled=should_no_lunch)
        with lunch_cols[1]:
            new_lunch_end = st.selectbox("Lunch End", TIME_LABELS, index=get_time_index("4PM"), key="new_tmpl_lunch_end", disabled=should_no_lunch)
        with lunch_cols[2]:
            st.write("")
            st.write("")
            # Auto-set no_lunch based on shift times
            no_lunch = st.checkbox("No lunch", value=should_no_lunch, key="new_tmpl_no_lunch", disabled=should_no_lunch)

        if should_no_lunch:
            st.caption("No lunch: shift starts after 4pm or ends before 4pm")

        if st.button("Add Template", type="primary"):
            if new_name.strip():
                # Force no lunch if shift doesn't qualify
                actual_no_lunch = no_lunch or should_no_lunch
                lunch_s = None if actual_no_lunch else label_to_time(new_lunch_start)
                lunch_e = None if actual_no_lunch else label_to_time(new_lunch_end)
                db.add_shift_template(
                    new_name.strip(),
                    label_to_time(new_start),
                    label_to_time(new_end),
                    lunch_s,
                    lunch_e,
                    new_color
                )
                st.success(f"Added template: {new_name}")
                st.rerun()
            else:
                st.error("Please enter a name")

    st.divider()

    # List templates
    templates = db.get_shift_templates()

    if not templates:
        st.info("No shift templates yet. Add common shifts like 'Morning', 'Evening', 'Close' above.")
        return

    st.subheader("Current Templates")

    for tmpl in templates:
        lunch_start = tmpl.get('lunch_start')
        lunch_end = tmpl.get('lunch_end')
        hours = pr.calculate_shift_hours(tmpl['start_time'], tmpl['end_time'], lunch_start, lunch_end)
        time_display = format_time_range(tmpl['start_time'], tmpl['end_time'])
        lunch_display = f", Lunch {format_time_range(lunch_start, lunch_end)}" if lunch_start and lunch_end else ""

        with st.expander(f"**{tmpl['name']}** - {time_display}{lunch_display} ({hours}h)"):
            col1, col2 = st.columns([3, 1])
            with col1:
                name = st.text_input("Name", value=tmpl['name'], key=f"tmpl_name_{tmpl['id']}")
            with col2:
                color = st.color_picker("Color", value=tmpl['color'] or "#3498db", key=f"tmpl_color_{tmpl['id']}")

            st.write("**Shift Time**")
            time_cols = st.columns(4)
            with time_cols[0]:
                start_label = time_to_label(tmpl['start_time'])
                start = st.selectbox("Start", TIME_LABELS, index=get_time_index(start_label, "9AM"), key=f"tmpl_start_{tmpl['id']}")
            with time_cols[1]:
                end_label = time_to_label(tmpl['end_time'])
                end = st.selectbox("End", TIME_LABELS, index=get_time_index(end_label, "5PM"), key=f"tmpl_end_{tmpl['id']}")

            # Check if current shift times qualify for lunch
            current_start_24 = label_to_time(start)
            current_end_24 = label_to_time(end)
            should_no_lunch = not should_have_lunch(current_start_24, current_end_24)

            st.write("**Lunch Break** (default 3-4PM)")
            lunch_cols = st.columns([1, 1, 0.7, 1.3])
            with lunch_cols[0]:
                lunch_s_label = time_to_label(lunch_start) if lunch_start else "3PM"
                edit_lunch_start = st.selectbox("Lunch Start", TIME_LABELS, index=get_time_index(lunch_s_label, "3PM"), key=f"tmpl_lunch_s_{tmpl['id']}", disabled=should_no_lunch)
            with lunch_cols[1]:
                lunch_e_label = time_to_label(lunch_end) if lunch_end else "4PM"
                edit_lunch_end = st.selectbox("Lunch End", TIME_LABELS, index=get_time_index(lunch_e_label, "4PM"), key=f"tmpl_lunch_e_{tmpl['id']}", disabled=should_no_lunch)
            with lunch_cols[2]:
                st.write("")
                st.write("")
                # Auto-set based on shift times, or use existing value if times allow lunch
                no_lunch_default = should_no_lunch or (not lunch_start)
                no_lunch = st.checkbox("No lunch", value=no_lunch_default, key=f"tmpl_no_lunch_{tmpl['id']}", disabled=should_no_lunch)

            if should_no_lunch:
                st.caption("No lunch: shift starts after 4pm or ends before 4pm")

            btn_cols = st.columns([1, 1, 2])
            with btn_cols[0]:
                if st.button("Update", key=f"save_tmpl_{tmpl['id']}", type="primary"):
                    # Force no lunch if shift doesn't qualify
                    actual_no_lunch = no_lunch or should_no_lunch
                    l_start = None if actual_no_lunch else label_to_time(edit_lunch_start)
                    l_end = None if actual_no_lunch else label_to_time(edit_lunch_end)
                    db.update_shift_template(
                        tmpl['id'],
                        name=name,
                        start_time=label_to_time(start),
                        end_time=label_to_time(end),
                        lunch_start=l_start,
                        lunch_end=l_end,
                        color=color
                    )
                    st.success("Saved")
                    st.rerun()
            with btn_cols[1]:
                if st.button("Delete", key=f"del_tmpl_{tmpl['id']}"):
                    db.delete_shift_template(tmpl['id'])
                    st.rerun()
