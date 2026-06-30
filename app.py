"""
Employee Scheduling & Payroll Application
Streamlit-based GUI for managing schedules and calculating payroll.
"""

import hmac
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import database as db
import payroll as pr


def check_password():
    """Simple password authentication."""

    # Already authenticated
    if st.session_state.get("authenticated"):
        return True

    # Get password from secrets
    try:
        correct_password = st.secrets["password"]
    except Exception:
        st.error("Password not configured. Add to Streamlit secrets.")
        st.code('password = "your-password-here"')
        return False

    # Show login form
    st.title("Employee Scheduling & Payroll")

    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", type="primary"):
        if hmac.compare_digest(password, correct_password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password")

    return False


def format_time_12h(time_str: str) -> str:
    """Convert 24h time string (HH:MM) to 12h format (h:MM AM/PM)."""
    try:
        t = datetime.strptime(time_str, "%H:%M")
        hour = t.hour % 12 or 12
        minute = t.minute
        period = "AM" if t.hour < 12 else "PM"
        if minute == 0:
            return f"{hour}{period}"
        return f"{hour}:{minute:02d}{period}"
    except (ValueError, TypeError):
        return time_str


def format_time_range(start: str, end: str) -> str:
    """Format a time range in 12h format."""
    return f"{format_time_12h(start)}-{format_time_12h(end)}"


def get_default_lunch(start_time: str, end_time: str) -> tuple:
    """
    Determine default lunch based on shift times.
    - If shift starts after 4pm → no lunch
    - If shift ends before 4pm → no lunch
    - Otherwise → lunch is 3-4pm

    Returns (lunch_start, lunch_end) or (None, None) for no lunch
    """
    try:
        start_hour = int(start_time.split(':')[0])
        end_hour = int(end_time.split(':')[0])

        # Shift starts at or after 4pm (16:00) → no lunch
        if start_hour >= 16:
            return None, None

        # Shift ends at or before 4pm (16:00) → no lunch
        if end_hour <= 16:
            return None, None

        # Default lunch 3pm-4pm
        return "15:00", "16:00"
    except (ValueError, IndexError, AttributeError):
        return "15:00", "16:00"


def get_time_options():
    """Generate time options in 12-hour format for dropdowns.
    15-minute increments from 8:45 AM to 11:15 PM.
    """
    options = []
    # Start at 8:45 AM (08:45) and end at 11:15 PM (23:15)
    start_minutes = 8 * 60 + 45  # 8:45 AM
    end_minutes = 23 * 60 + 15   # 11:15 PM

    for total_mins in range(start_minutes, end_minutes + 1, 15):
        hour = total_mins // 60
        minute = total_mins % 60
        time_24 = f"{hour:02d}:{minute:02d}"
        hour_12 = hour % 12 or 12
        period = "AM" if hour < 12 else "PM"
        label = f"{hour_12}{period}" if minute == 0 else f"{hour_12}:{minute:02d}{period}"
        options.append((time_24, label))
    return options


TIME_OPTIONS = get_time_options()
TIME_24_TO_LABEL = {t[0]: t[1] for t in TIME_OPTIONS}
TIME_LABEL_TO_24 = {t[1]: t[0] for t in TIME_OPTIONS}
TIME_LABELS = [t[1] for t in TIME_OPTIONS]


def time_to_label(time_24: str) -> str:
    """Convert 24h time to 12h label, rounding to nearest 15-min option."""
    h, m = int(time_24.split(':')[0]), int(time_24.split(':')[1])
    # Round to nearest 15 minutes
    m = round(m / 15) * 15
    if m == 60:
        m = 0
        h = (h + 1) % 24
    rounded = f"{h:02d}:{m:02d}"
    # If outside our range, clamp to nearest boundary
    if rounded in TIME_24_TO_LABEL:
        return TIME_24_TO_LABEL[rounded]
    # Fallback: find closest option
    if h < 9 or (h == 8 and m < 45):
        return TIME_LABELS[0]  # 8:45AM
    if h >= 23 and m > 15:
        return TIME_LABELS[-1]  # 11:15PM
    return TIME_LABELS[0]


def label_to_time(label: str) -> str:
    """Convert 12h label to 24h time."""
    return TIME_LABEL_TO_24.get(label, "10:00")


def get_time_index(label: str, default_label: str = "10AM") -> int:
    """Get index of a time label in TIME_LABELS, with fallback."""
    if label in TIME_LABELS:
        return TIME_LABELS.index(label)
    if default_label in TIME_LABELS:
        return TIME_LABELS.index(default_label)
    return 0




def should_have_lunch(start_time: str, end_time: str) -> bool:
    """Check if a shift should have lunch based on times."""
    lunch_s, lunch_e = get_default_lunch(start_time, end_time)
    return lunch_s is not None


# Page configuration
st.set_page_config(
    page_title="Employee Scheduling & Payroll",
    page_icon="📅",
    layout="wide"
)

# Custom CSS for better layout
st.markdown("""
<style>
    /* Remove top padding to bring content to very top */
    .main .block-container {
        padding-top: 0;
        margin-top: 0;
    }

    /* Remove any extra spacing at top */
    .main > div:first-child {
        padding-top: 0;
    }

    /* Make Streamlit header minimal but keep hamburger menu visible */
    header[data-testid="stHeader"] {
        background: transparent;
        height: 2.5rem;
    }

    /* Narrow sidebar - wide enough for "Shift Templates" */
    [data-testid="stSidebar"] {
        min-width: 180px;
        max-width: 200px;
    }

    /* Prevent text wrapping/vertical text */
    .stSelectbox label, .stSelectbox div[data-baseweb="select"] {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Make selectbox dropdown text not wrap */
    [data-baseweb="select"] span {
        white-space: nowrap;
    }

    /* Compact the schedule grid */
    [data-testid="column"] {
        padding: 0 4px;
    }

    /* Smaller captions */
    .stCaption {
        font-size: 0.75rem;
        white-space: nowrap;
    }

    /* Ensure metric values don't wrap */
    [data-testid="stMetricValue"] {
        white-space: nowrap;
    }

    /* Compact buttons */
    .stButton button {
        padding: 0.25rem 0.5rem;
        font-size: 0.75rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }

    /* ===== MOBILE RESPONSIVE ===== */
    @media (max-width: 768px) {
        /* Make main content full width */
        .main .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
            max-width: 100%;
        }

        /* Allow horizontal scroll for schedule grid */
        [data-testid="stHorizontalBlock"] {
            overflow-x: auto;
            flex-wrap: nowrap !important;
            -webkit-overflow-scrolling: touch;
            padding-bottom: 0.5rem;
        }

        /* Minimum width for day columns on mobile */
        [data-testid="column"] {
            min-width: 55px;
            flex-shrink: 0;
        }

        /* Employee name column wider on mobile */
        [data-testid="column"]:first-child {
            min-width: 90px;
        }

        /* Stack form elements better on mobile */
        .stSelectbox, .stCheckbox {
            margin-bottom: 0.25rem;
        }

        /* Smaller text on mobile */
        .stMarkdown {
            font-size: 0.85rem;
        }

        .stMarkdown h3 {
            font-size: 1.1rem;
        }

        /* Smaller captions on mobile */
        .stCaption {
            font-size: 0.65rem;
        }

        /* Touch-friendly buttons on mobile */
        .stButton button {
            padding: 0.4rem 0.6rem;
            font-size: 0.8rem;
            min-height: 38px;
        }

        /* Touch-friendly checkboxes */
        .stCheckbox {
            padding: 0.25rem 0;
        }

        /* Compact progress bar */
        .stProgress {
            margin: 0.25rem 0;
        }

        /* Hide sidebar by default on mobile (user can open) */
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 200px;
        }
    }

    /* Tablet adjustments */
    @media (max-width: 1200px) and (min-width: 769px) {
        [data-testid="stSidebar"] {
            min-width: 160px;
            max-width: 180px;
        }

        [data-testid="column"] {
            min-width: 70px;
        }
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Check authentication first
    if not check_password():
        return

    st.title("Employee Scheduling & Payroll")

    # Sidebar navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Schedule", "Employees", "Shift Templates", "Payroll", "Settings"]
    )

    # Logout button in sidebar
    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()

    if page == "Schedule":
        schedule_page()
    elif page == "Employees":
        employees_page()
    elif page == "Shift Templates":
        templates_page()
    elif page == "Payroll":
        payroll_page()
    elif page == "Settings":
        settings_page()


def schedule_page():
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


def employees_page():
    """Employee management page."""
    st.header("Employee Management")

    # Add new employee section
    st.subheader("Add New Employee")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        new_name = st.text_input("Name", key="new_emp_name", placeholder="Enter employee name")
    with col2:
        new_rate = st.number_input("Hourly Rate ($)", min_value=1.0,
                                   max_value=500.0, value=10.0, step=0.50,
                                   key="new_emp_rate")
    with col3:
        st.write("")  # Spacer
        st.write("")
        if st.button("Add Employee", type="primary"):
            if new_name.strip():
                db.add_employee(new_name.strip(), new_rate)
                st.success(f"Added {new_name}")
                st.rerun()
            else:
                st.error("Please enter a name")

    st.divider()

    # Get active and inactive employees separately
    all_employees = db.get_employees(active_only=False)
    active_employees = [e for e in all_employees if e['is_active']]
    inactive_employees = [e for e in all_employees if not e['is_active']]

    if not all_employees:
        st.info("No employees yet. Add your first employee above.")
        return

    # Active employees section
    st.subheader("Current Employees")
    if active_employees:
        st.caption("Click on an employee to edit their details")
        for emp in active_employees:
            label = f"**{emp['name']}** - ${emp['hourly_rate']:.2f}/hr"

            with st.expander(label):
                edit_cols = st.columns([2, 2, 1])

                with edit_cols[0]:
                    new_name = st.text_input(
                        "Name",
                        value=emp['name'],
                        key=f"emp_name_{emp['id']}"
                    )

                with edit_cols[1]:
                    new_rate = st.number_input(
                        "Hourly Rate ($)",
                        min_value=1.0,
                        max_value=500.0,
                        value=float(emp['hourly_rate']),
                        step=0.50,
                        key=f"emp_rate_{emp['id']}"
                    )

                with edit_cols[2]:
                    st.write("")
                    st.write("")
                    if st.button("Update", key=f"save_emp_{emp['id']}", type="primary"):
                        db.update_employee(emp['id'], name=new_name, hourly_rate=new_rate)
                        st.success("Updated!")
                        st.rerun()

                if st.button("Deactivate Employee", key=f"deact_emp_{emp['id']}"):
                    db.update_employee(emp['id'], is_active=False)
                    st.rerun()
    else:
        st.info("No active employees. Reactivate employees below or add new ones above.")

    # Inactive employees section
    if inactive_employees:
        st.divider()
        st.subheader("Inactive Employees")
        for emp in inactive_employees:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{emp['name']}** - ${emp['hourly_rate']:.2f}/hr")
            with col2:
                if st.button("Reactivate", key=f"reactivate_{emp['id']}"):
                    db.update_employee(emp['id'], is_active=True)
                    st.rerun()
            with col3:
                if st.button("Delete", key=f"delete_emp_{emp['id']}", type="secondary"):
                    st.session_state[f'confirm_delete_{emp["id"]}'] = True
                    st.rerun()

            # Confirmation dialog
            if st.session_state.get(f'confirm_delete_{emp["id"]}'):
                st.warning(f"Permanently delete **{emp['name']}**? This will also delete all their shift history.")
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    if st.button("Yes, Delete", key=f"confirm_del_{emp['id']}", type="primary"):
                        db.hard_delete_employee(emp['id'])
                        del st.session_state[f'confirm_delete_{emp["id"]}']
                        st.rerun()
                with c2:
                    if st.button("Cancel", key=f"cancel_del_{emp['id']}"):
                        del st.session_state[f'confirm_delete_{emp["id"]}']
                        st.rerun()


def templates_page():
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


def payroll_page():
    """Payroll reports page."""
    st.header("Payroll Reports")

    # Period selector
    col1, col2, col3 = st.columns(3)

    with col1:
        period_type = st.radio("Pay Period", ["Weekly", "Bi-Weekly", "Custom"], horizontal=True)

    # Get dates based on period type
    today = date.today()

    if period_type == "Weekly":
        start_date, end_date, _ = pr.get_week_dates(today)
        with col2:
            week_offset = st.number_input("Weeks ago", min_value=0, max_value=52, value=0)
            if week_offset > 0:
                ref_date = today - timedelta(weeks=week_offset)
                start_date, end_date, _ = pr.get_week_dates(ref_date)

    elif period_type == "Bi-Weekly":
        start_date, end_date = pr.get_biweekly_dates(today)
        with col2:
            period_offset = st.number_input("Periods ago", min_value=0, max_value=26, value=0)
            if period_offset > 0:
                ref_date = today - timedelta(weeks=period_offset * 2)
                start_date, end_date = pr.get_biweekly_dates(ref_date)

    else:  # Custom
        with col2:
            start_date = st.date_input("Start Date", value=today - timedelta(days=6)).isoformat()
        with col3:
            end_date = st.date_input("End Date", value=today).isoformat()

    st.markdown(f"**Period:** {start_date} to {end_date}")

    # Generate report
    if st.button("Generate Report", type="primary"):
        with st.spinner("Calculating payroll..."):
            report = pr.calculate_payroll_report(start_date, end_date)

        st.session_state['payroll_report'] = report

    # Display report
    if 'payroll_report' in st.session_state:
        report = st.session_state['payroll_report']
        display_payroll_report(report)


def build_schedule_grid_data(report: dict) -> list[dict]:
    """Build schedule grid data for display and export."""
    start_date = datetime.fromisoformat(report['start_date']).date()
    end_date = datetime.fromisoformat(report['end_date']).date()

    # Get all shifts for this period
    shifts = db.get_shifts_for_week(report['start_date'], report['end_date'])

    # Build shift lookup
    shift_lookup = {}
    for shift in shifts:
        key = (shift['employee_id'], shift['shift_date'])
        shift_lookup[key] = shift

    # Get all dates in range
    all_dates = []
    current = start_date
    while current <= end_date:
        all_dates.append(current)
        current += timedelta(days=1)

    # Build grid data
    grid_data = []
    day_names = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

    for emp_payroll in report['employees']:
        row = {'Employee': emp_payroll.employee_name}

        for d in all_dates:
            date_str = d.isoformat()
            day_label = f"{day_names[d.weekday()]} {d.day}"

            key = (emp_payroll.employee_id, date_str)
            shift = shift_lookup.get(key)

            if shift:
                lunch_s = shift.get('lunch_start')
                lunch_e = shift.get('lunch_end')
                hours = pr.calculate_shift_hours(shift['start_time'], shift['end_time'], lunch_s, lunch_e)
                shift_display = format_time_range(shift['start_time'], shift['end_time'])
                if lunch_s and lunch_e:
                    shift_display += f" (L:{format_time_range(lunch_s, lunch_e)})"
                row[day_label] = f"{shift_display} - {hours}h"
            else:
                row[day_label] = "----"

        row['Total Hours'] = emp_payroll.total_hours
        row['Pay'] = f"${emp_payroll.total_pay:.2f}"
        grid_data.append(row)

    return grid_data


def build_schedule_csv(report: dict) -> str:
    """Build CSV string for schedule grid."""
    grid_data = build_schedule_grid_data(report)
    if grid_data:
        df = pd.DataFrame(grid_data)
        return df.to_csv(index=False)
    return ""


def display_schedule_grid(report: dict):
    """Display a schedule grid showing shifts for the pay period."""
    grid_data = build_schedule_grid_data(report)

    if grid_data:
        df = pd.DataFrame(grid_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No scheduled shifts for this period")


def display_payroll_report(report: dict):
    """Display a payroll report."""
    st.divider()

    # Summary metrics
    summary = report['summary']
    settings = report['settings']

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Employees", summary['total_employees'])
    col2.metric("Total Hours", f"{summary['total_hours']:.1f}")
    col3.metric("Overtime Hours", f"{summary['total_overtime_hours']:.1f}")
    col4.metric("Total Payroll", f"${summary['total_pay']:.2f}")

    st.caption(f"OT after {settings['overtime_weekly_threshold']}hrs/week or {settings['overtime_daily_threshold']}hrs/day @ {settings['overtime_multiplier']}x")

    st.divider()

    # Schedule Grid
    st.subheader("Schedule Grid")
    display_schedule_grid(report)

    st.divider()

    # Employee breakdown
    st.subheader("Employee Breakdown")

    for emp_payroll in report['employees']:
        if emp_payroll.total_hours == 0:
            continue

        with st.expander(f"**{emp_payroll.employee_name}** - {emp_payroll.total_hours}hrs - ${emp_payroll.total_pay:.2f}"):
            # Daily breakdown table
            daily_data = []
            for dh in emp_payroll.daily_breakdown:
                if dh.total_hours > 0:
                    daily_data.append({
                        'Date': dh.date,
                        'Regular': dh.regular_hours,
                        'Overtime': dh.overtime_hours,
                        'Total': dh.total_hours
                    })

            if daily_data:
                df = pd.DataFrame(daily_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

            # Summary
            cols = st.columns(4)
            cols[0].metric("Rate", f"${emp_payroll.hourly_rate:.2f}/hr")
            cols[1].metric("Regular Pay", f"${emp_payroll.regular_pay:.2f}")
            cols[2].metric("OT Pay", f"${emp_payroll.overtime_pay:.2f}")
            cols[3].metric("Total", f"${emp_payroll.total_pay:.2f}")

    # Export
    st.divider()
    st.subheader("Export")

    col1, col2 = st.columns(2)

    with col1:
        # Payroll summary CSV
        export_data = []
        for emp in report['employees']:
            export_data.append({
                'Employee': emp.employee_name,
                'Hourly Rate': emp.hourly_rate,
                'Regular Hours': emp.total_regular_hours,
                'Overtime Hours': emp.total_overtime_hours,
                'Total Hours': emp.total_hours,
                'Regular Pay': emp.regular_pay,
                'Overtime Pay': emp.overtime_pay,
                'Total Pay': emp.total_pay
            })

        export_df = pd.DataFrame(export_data)
        csv = export_df.to_csv(index=False)
        st.download_button(
            "Download Payroll CSV",
            csv,
            file_name=f"payroll_{report['start_date']}_to_{report['end_date']}.csv",
            mime="text/csv"
        )

    with col2:
        # Schedule grid CSV
        schedule_csv = build_schedule_csv(report)
        st.download_button(
            "Download Schedule CSV",
            schedule_csv,
            file_name=f"schedule_{report['start_date']}_to_{report['end_date']}.csv",
            mime="text/csv"
        )


def settings_page():
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


if __name__ == "__main__":
    main()
