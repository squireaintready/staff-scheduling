"""Weekly schedule grid view with per-employee editing."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

import database as db
from timeutils import (
    TIME_LABELS,
    format_time_12h,
    get_default_lunch,
    label_to_time,
    should_have_lunch,
    time_to_label,
)
from validation import validate_shift


def render():
    """Weekly schedule grid view with employee-by-employee editing."""
    st.header("Weekly Schedule")

    # Week selector
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("< Previous Week"):
            if 'current_week_start' in st.session_state:
                st.session_state.current_week_start -= timedelta(days=7)
            else:
                st.session_state.current_week_start = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=7)
            st.rerun()

    with col3:
        if st.button("Next Week >"):
            if 'current_week_start' in st.session_state:
                st.session_state.current_week_start += timedelta(days=7)
            else:
                st.session_state.current_week_start = date.today() - timedelta(days=date.today().weekday()) + timedelta(days=7)
            st.rerun()

    # Get current week dates
    if 'current_week_start' not in st.session_state:
        today = date.today()
        # Week starts on Monday (weekday() returns 0 for Monday)
        st.session_state.current_week_start = today - timedelta(days=today.weekday())

    week_start = st.session_state.current_week_start
    week_dates = [(week_start + timedelta(days=i)) for i in range(7)]
    week_end = week_dates[-1]

    with col2:
        st.markdown(f"### {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")

    # Get employees and shifts
    employees = db.get_employees()
    shifts = db.get_shifts_for_week(week_start.isoformat(), week_end.isoformat())
    templates = db.get_shift_templates()

    if not employees:
        st.info("No employees found. Add employees in the Employees page first.")
        return

    # Create shift lookup
    shift_lookup = {}
    for shift in shifts:
        key = (shift['employee_id'], shift['shift_date'])
        shift_lookup[key] = shift

    # Day names
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_names_short = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

    # Categorize employees by scheduling status
    def employee_has_shifts(emp_id):
        return any(shift_lookup.get((emp_id, d.isoformat())) for d in week_dates)

    def get_last_modified(emp_id):
        last_mod = db.get_last_modified_for_employee(emp_id, week_start.isoformat(), week_end.isoformat())
        if last_mod:
            try:
                dt = datetime.fromisoformat(last_mod)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                dt_est = dt.astimezone(ZoneInfo("America/New_York"))
                return dt_est.strftime("%b %d, %I:%M%p").lower()
            except (ValueError, TypeError):
                return None
        return None

    scheduled_employees = [e for e in employees if employee_has_shifts(e['id'])]
    unscheduled_employees = [e for e in employees if not employee_has_shifts(e['id'])]

    # Progress indicator
    total = len(employees)
    done = len(scheduled_employees)
    st.divider()

    if unscheduled_employees:
        st.progress(done / total if total > 0 else 0)
        st.markdown(f"**Progress: {done}/{total} employees scheduled** — {len(unscheduled_employees)} remaining")
    else:
        st.success(f"All {total} employees scheduled for this week!")

    # Needs Scheduling section (always visible at top if any)
    if unscheduled_employees:
        st.markdown("### Needs Scheduling")
        header_cols = st.columns([1.8] + [1] * 7)
        header_cols[0].write("**Employee**")
        for i, d in enumerate(week_dates):
            header_cols[i + 1].write(f"**{day_names_short[i]}** {d.day}")

        for emp in unscheduled_employees:
            cols = st.columns([1.8] + [1] * 7)
            with cols[0]:
                st.markdown(f":orange[**{emp['name']}**]")
            for i in range(len(week_dates)):
                with cols[i + 1]:
                    st.caption("—")

    # Scheduled section
    if scheduled_employees:
        st.markdown("### Scheduled")
        header_cols = st.columns([1.8] + [1] * 7)
        header_cols[0].write("**Employee**")
        for i, d in enumerate(week_dates):
            header_cols[i + 1].write(f"**{day_names_short[i]}** {d.day}")

        for emp in scheduled_employees:
            cols = st.columns([1.8] + [1] * 7)
            with cols[0]:
                last_mod = get_last_modified(emp['id'])
                st.markdown(f":green[**{emp['name']}**]")
                if last_mod:
                    st.caption(f"updated {last_mod}")
            for i, d in enumerate(week_dates):
                date_str = d.isoformat()
                shift = shift_lookup.get((emp['id'], date_str))
                with cols[i + 1]:
                    if shift:
                        st.caption(format_time_12h(shift['start_time']))
                    else:
                        st.caption("—")

    st.divider()

    # Employee selector for editing
    st.subheader("Edit Hours")

    # Sort: unscheduled first, then scheduled
    sorted_employees = unscheduled_employees + scheduled_employees

    def format_emp_option(emp_id):
        emp = next((e for e in employees if e['id'] == emp_id), None)
        if emp:
            # Get days this employee is working
            day_abbrevs = ['M', 'T', 'W', 'Th', 'F', 'Sa', 'Su']
            working_days = []
            for i, d in enumerate(week_dates):
                if shift_lookup.get((emp_id, d.isoformat())):
                    working_days.append(day_abbrevs[i])

            if working_days:
                return f"{emp['name']} [{', '.join(working_days)}]"
            else:
                return f"{emp['name']} [no shifts]"
        return str(emp_id)

    selected_emp_id = st.selectbox(
        "Select Employee",
        options=[e['id'] for e in sorted_employees],
        format_func=format_emp_option,
        key="edit_employee_select"
    )

    if selected_emp_id:
        selected_emp = next((e for e in employees if e['id'] == selected_emp_id), None)
        st.write(f"**{selected_emp['name']}** - ${selected_emp['hourly_rate']:.2f}/hr")

        # Quick fill section - select days then apply template
        if templates:
            st.caption("Quick fill: select days, then click a template to apply")

            # Helper to trigger form reset so widgets match DB values
            def trigger_form_reset():
                st.session_state['_form_reset'] = True
                # Clear all form-related session state keys
                keys_to_clear = [
                    k for k in st.session_state
                    if k.startswith(('nowork_', 'no_lunch_', 'start_', 'end_', 'lunch_s_', 'lunch_e_'))
                ]
                for k in keys_to_clear:
                    del st.session_state[k]

            day_names_short = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

            # Initialize day selection checkboxes only if they don't exist (default: none selected)
            for i in range(7):
                if f"sel_day_{i}" not in st.session_state:
                    st.session_state[f"sel_day_{i}"] = False

            # Restore selection after template/clear apply (backup exists)
            if '_day_sel_backup' in st.session_state:
                for i in range(7):
                    st.session_state[f"sel_day_{i}"] = st.session_state['_day_sel_backup'][i]
                del st.session_state['_day_sel_backup']

            # Handle All/None BEFORE checkboxes render (Streamlit requirement)
            if st.session_state.pop('_select_all_days', False):
                for i in range(7):
                    st.session_state[f"sel_day_{i}"] = True
            if st.session_state.pop('_select_no_days', False):
                for i in range(7):
                    st.session_state[f"sel_day_{i}"] = False

            # Template buttons row - compact buttons with padding on right
            num_btns = len(templates) + 1
            btn_widths = [0.4] * num_btns + [3]  # Small fixed widths + padding
            btn_cols = st.columns(btn_widths)
            for t_idx, tmpl in enumerate(templates):
                with btn_cols[t_idx]:
                    if st.button(tmpl['name'], key=f"fill_tmpl_{tmpl['id']}", use_container_width=True):
                        # Backup selection before rerun
                        st.session_state['_day_sel_backup'] = [st.session_state[f"sel_day_{i}"] for i in range(7)]
                        for i, d in enumerate(week_dates):
                            if st.session_state[f"sel_day_{i}"]:
                                date_str = d.isoformat()
                                lunch_s = tmpl.get('lunch_start')
                                lunch_e = tmpl.get('lunch_end')
                                if not lunch_s:
                                    lunch_s, lunch_e = get_default_lunch(tmpl['start_time'], tmpl['end_time'])
                                db.add_shift(selected_emp_id, date_str, tmpl['start_time'], tmpl['end_time'], lunch_s, lunch_e, tmpl['id'])
                        trigger_form_reset()
                        st.rerun()
            with btn_cols[len(templates)]:
                if st.button("Clear", key="clear_selected_days", use_container_width=True):
                    # Backup selection before rerun
                    st.session_state['_day_sel_backup'] = [st.session_state[f"sel_day_{i}"] for i in range(7)]
                    for i, d in enumerate(week_dates):
                        if st.session_state[f"sel_day_{i}"]:
                            db.delete_shift(selected_emp_id, d.isoformat())
                    trigger_form_reset()
                    st.rerun()

            # Day checkboxes + All/None buttons in one row
            day_cols = st.columns([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.1, 0.4, 0.4, 3])
            for i in range(7):
                with day_cols[i]:
                    st.checkbox(day_names_short[i], key=f"sel_day_{i}")

            with day_cols[8]:
                if st.button("All", key="select_all_days", use_container_width=True):
                    st.session_state['_select_all_days'] = True
                    st.rerun()
            with day_cols[9]:
                if st.button("None", key="select_no_days", use_container_width=True):
                    st.session_state['_select_no_days'] = True
                    st.rerun()

        st.divider()

        # Edit form for each day
        # Header row: Day | Start | End | Off | Lunch Start | Lunch End | No Lunch
        hdr = st.columns([1.2, 1, 1, 0.5, 1, 1, 0.7])
        hdr[0].write("**Day**")
        hdr[1].write("**Start**")
        hdr[2].write("**End**")
        hdr[3].write("**Off**")
        hdr[4].write("**Lunch Start**")
        hdr[5].write("**Lunch End**")
        hdr[6].write("**No Lunch**")

        # Check if form needs reset (after quick fill actions)
        form_reset = st.session_state.pop('_form_reset', False)

        # Store form values
        day_data = {}

        for i, d in enumerate(week_dates):
            date_str = d.isoformat()
            existing = shift_lookup.get((selected_emp_id, date_str))

            # Default: no work if no existing shift
            def_no_work = (existing is None)
            nowork_key = f"nowork_{date_str}"

            # Initialize or reset the Off checkbox state
            if form_reset or nowork_key not in st.session_state:
                st.session_state[nowork_key] = def_no_work

            # Get current Off state from session
            is_off = st.session_state[nowork_key]

            # Default times (using 12hr labels)
            if existing:
                def_start = time_to_label(existing['start_time'])
                def_end = time_to_label(existing['end_time'])
                if existing.get('lunch_start'):
                    def_lunch_s = time_to_label(existing['lunch_start'])
                    def_lunch_e = time_to_label(existing['lunch_end'])
                    def_no_lunch = False
                else:
                    def_lunch_s = "3PM"
                    def_lunch_e = "4PM"
                    def_no_lunch = True
            else:
                def_start = "10AM"
                def_end = "6PM"
                def_lunch_s = "3PM"
                def_lunch_e = "4PM"
                def_no_lunch = False

            # Initialize/reset all form field session state values
            # This ensures widgets get fresh values from DB after template apply
            start_key = f"start_{date_str}"
            end_key = f"end_{date_str}"
            lunch_s_key = f"lunch_s_{date_str}"
            lunch_e_key = f"lunch_e_{date_str}"
            no_lunch_key = f"no_lunch_{date_str}"

            if form_reset or start_key not in st.session_state:
                st.session_state[start_key] = def_start
            if form_reset or end_key not in st.session_state:
                st.session_state[end_key] = def_end
            if form_reset or lunch_s_key not in st.session_state:
                st.session_state[lunch_s_key] = def_lunch_s
            if form_reset or lunch_e_key not in st.session_state:
                st.session_state[lunch_e_key] = def_lunch_e
            if form_reset or no_lunch_key not in st.session_state:
                st.session_state[no_lunch_key] = def_no_lunch

            row = st.columns([1.2, 1, 1, 0.5, 1, 1, 0.7])

            with row[0]:
                if is_off:
                    st.caption(f"{day_names[i]} {d.strftime('%m/%d')}")
                else:
                    st.write(f"**{day_names[i]}** {d.strftime('%m/%d')}")

            with row[1]:
                start_time = st.selectbox("Start", TIME_LABELS, key=start_key, label_visibility="collapsed", disabled=is_off)

            with row[2]:
                end_time = st.selectbox("End", TIME_LABELS, key=end_key, label_visibility="collapsed", disabled=is_off)

            with row[3]:
                no_work = st.checkbox("", key=nowork_key, label_visibility="collapsed")

            # Check if current times qualify for lunch
            current_start_24 = label_to_time(start_time)
            current_end_24 = label_to_time(end_time)
            should_no_lunch = not should_have_lunch(current_start_24, current_end_24)

            with row[4]:
                lunch_s = st.selectbox("Lunch Start", TIME_LABELS, key=lunch_s_key, label_visibility="collapsed", disabled=is_off or should_no_lunch)

            with row[5]:
                lunch_e = st.selectbox("Lunch End", TIME_LABELS, key=lunch_e_key, label_visibility="collapsed", disabled=is_off or should_no_lunch)

            with row[6]:
                # Force no_lunch if shift doesn't qualify
                if should_no_lunch and not is_off:
                    st.session_state[no_lunch_key] = True
                no_lunch = st.checkbox("", key=no_lunch_key, label_visibility="collapsed", disabled=is_off or should_no_lunch)

            day_data[date_str] = {
                'no_work': no_work,
                'start': start_time,
                'end': end_time,
                'lunch_s': lunch_s,
                'lunch_e': lunch_e,
                'no_lunch': no_lunch or should_no_lunch  # Force no lunch if times don't qualify
            }

        st.divider()

        # Save button
        if st.button("Save All Changes", type="primary", key="save_emp_schedule"):
            # Validate every working day before writing anything (all-or-nothing).
            errors = []
            for date_str, data in day_data.items():
                if data['no_work']:
                    continue
                l_start = None if data['no_lunch'] else label_to_time(data['lunch_s'])
                l_end = None if data['no_lunch'] else label_to_time(data['lunch_e'])
                for msg in validate_shift(label_to_time(data['start']),
                                          label_to_time(data['end']), l_start, l_end):
                    errors.append(f"{date_str}: {msg}")

            if errors:
                for msg in errors:
                    st.error(msg)
            else:
                for date_str, data in day_data.items():
                    if not data['no_work']:
                        l_start = None if data['no_lunch'] else label_to_time(data['lunch_s'])
                        l_end = None if data['no_lunch'] else label_to_time(data['lunch_e'])
                        db.add_shift(
                            selected_emp_id,
                            date_str,
                            label_to_time(data['start']),
                            label_to_time(data['end']),
                            l_start,
                            l_end
                        )
                    else:
                        # Delete shift if Off is checked
                        db.delete_shift(selected_emp_id, date_str)
                st.success(f"Saved schedule for {selected_emp['name']}!")
                st.rerun()
