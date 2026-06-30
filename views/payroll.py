"""Payroll report view: summary, per-employee breakdown, exports."""

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import database as db
import payroll as pr
from timeutils import (
    format_time_range,
)


def render():
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
