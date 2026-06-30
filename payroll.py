"""
Payroll calculation module.
Handles hours calculation, overtime, and pay computation.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import database as db


@dataclass
class DailyHours:
    """Hours worked in a single day."""
    date: str
    regular_hours: float
    overtime_hours: float
    total_hours: float


@dataclass
class EmployeePayroll:
    """Payroll summary for an employee."""
    employee_id: int
    employee_name: str
    hourly_rate: float
    daily_breakdown: list[DailyHours]
    total_regular_hours: float
    total_overtime_hours: float
    total_hours: float
    regular_pay: float
    overtime_pay: float
    total_pay: float


def parse_time(time_str: str) -> tuple[int, int]:
    """Parse time string (HH:MM) to hours and minutes."""
    parts = time_str.split(':')
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0


def calculate_shift_hours(start_time: str, end_time: str,
                          lunch_start: str | None = None, lunch_end: str | None = None) -> float:
    """Calculate hours between start and end time, minus lunch break."""
    start_h, start_m = parse_time(start_time)
    end_h, end_m = parse_time(end_time)

    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    # Handle overnight shifts
    if end_minutes < start_minutes:
        end_minutes += 24 * 60

    diff_minutes = end_minutes - start_minutes

    # Subtract lunch break if specified
    if lunch_start and lunch_end:
        lunch_s_h, lunch_s_m = parse_time(lunch_start)
        lunch_e_h, lunch_e_m = parse_time(lunch_end)
        lunch_start_mins = lunch_s_h * 60 + lunch_s_m
        lunch_end_mins = lunch_e_h * 60 + lunch_e_m
        lunch_duration = lunch_end_mins - lunch_start_mins
        if lunch_duration > 0:
            diff_minutes -= lunch_duration

    return round(max(0, diff_minutes) / 60, 2)


def calculate_daily_overtime(hours: float, daily_threshold: float) -> tuple[float, float]:
    """
    Calculate regular and overtime hours for a single day.

    Returns:
        Tuple of (regular_hours, overtime_hours)
    """
    if hours <= daily_threshold:
        return hours, 0.0
    else:
        return daily_threshold, round(hours - daily_threshold, 2)


def calculate_weekly_overtime(daily_hours: list[float], weekly_threshold: float,
                              daily_threshold: float) -> list[tuple[float, float]]:
    """
    Calculate regular and overtime hours for a week.
    Applies both daily and weekly overtime rules.

    Returns:
        List of (regular_hours, overtime_hours) for each day
    """
    results = []
    cumulative_regular = 0.0

    for hours in daily_hours:
        # First apply daily overtime
        daily_regular, daily_ot = calculate_daily_overtime(hours, daily_threshold)

        # Check if adding daily regular hours exceeds weekly threshold
        if cumulative_regular + daily_regular > weekly_threshold:
            # Some of today's "regular" hours become overtime
            allowed_regular = max(0, weekly_threshold - cumulative_regular)
            additional_ot = daily_regular - allowed_regular
            daily_regular = allowed_regular
            daily_ot += additional_ot

        cumulative_regular += daily_regular
        results.append((round(daily_regular, 2), round(daily_ot, 2)))

    return results


def get_week_dates(reference_date: date | None = None) -> tuple[str, str, list[str]]:
    """
    Get the start date, end date, and all dates for a week.
    Week starts on Monday.

    Returns:
        Tuple of (start_date, end_date, list_of_dates) as strings
    """
    if reference_date is None:
        reference_date = date.today()

    # Find Monday of this week (weekday() returns 0 for Monday)
    start = reference_date - timedelta(days=reference_date.weekday())

    dates = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    return dates[0], dates[6], dates


def calculate_employee_payroll(employee_id: int, start_date: str, end_date: str,
                                overtime_weekly: float = 40.0,
                                overtime_daily: float = 8.0,
                                overtime_multiplier: float = 1.5) -> EmployeePayroll:
    """
    Calculate payroll for a single employee over a date range.
    """
    employee = db.get_employee(employee_id)
    if not employee:
        raise ValueError(f"Employee {employee_id} not found")

    shifts = db.get_shifts_for_employee(employee_id, start_date, end_date)

    # Calculate hours for each day
    daily_hours_map = {}
    for shift in shifts:
        lunch_start = shift.get('lunch_start')
        lunch_end = shift.get('lunch_end')
        hours = calculate_shift_hours(shift['start_time'], shift['end_time'], lunch_start, lunch_end)
        daily_hours_map[shift['shift_date']] = hours

    # Get all dates in range
    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()
    all_dates = []
    current = start
    while current <= end:
        all_dates.append(current.isoformat())
        current += timedelta(days=1)

    # Get hours for each day (0 if no shift)
    daily_hours_list = [daily_hours_map.get(d, 0.0) for d in all_dates]

    # Calculate overtime
    overtime_results = calculate_weekly_overtime(
        daily_hours_list, overtime_weekly, overtime_daily
    )

    # Build daily breakdown
    daily_breakdown = []
    for i, d in enumerate(all_dates):
        regular, ot = overtime_results[i]
        daily_breakdown.append(DailyHours(
            date=d,
            regular_hours=regular,
            overtime_hours=ot,
            total_hours=round(regular + ot, 2)
        ))

    # Calculate totals
    total_regular = sum(dh.regular_hours for dh in daily_breakdown)
    total_ot = sum(dh.overtime_hours for dh in daily_breakdown)
    total_hours = total_regular + total_ot

    hourly_rate = employee['hourly_rate']
    regular_pay = round(total_regular * hourly_rate, 2)
    overtime_pay = round(total_ot * hourly_rate * overtime_multiplier, 2)
    total_pay = round(regular_pay + overtime_pay, 2)

    return EmployeePayroll(
        employee_id=employee_id,
        employee_name=employee['name'],
        hourly_rate=hourly_rate,
        daily_breakdown=daily_breakdown,
        total_regular_hours=round(total_regular, 2),
        total_overtime_hours=round(total_ot, 2),
        total_hours=round(total_hours, 2),
        regular_pay=regular_pay,
        overtime_pay=overtime_pay,
        total_pay=total_pay
    )


def calculate_payroll_report(start_date: str, end_date: str) -> dict:
    """
    Generate a full payroll report for all employees.
    """
    settings = db.get_all_settings()
    overtime_weekly = float(settings.get('overtime_weekly_threshold', 40))
    overtime_daily = float(settings.get('overtime_daily_threshold', 8))
    overtime_multiplier = float(settings.get('overtime_multiplier', 1.5))

    employees = db.get_employees(active_only=True)
    payrolls = []

    for emp in employees:
        payroll = calculate_employee_payroll(
            emp['id'], start_date, end_date,
            overtime_weekly, overtime_daily, overtime_multiplier
        )
        payrolls.append(payroll)

    # Calculate totals
    total_regular_hours = sum(p.total_regular_hours for p in payrolls)
    total_ot_hours = sum(p.total_overtime_hours for p in payrolls)
    total_hours = sum(p.total_hours for p in payrolls)
    total_regular_pay = sum(p.regular_pay for p in payrolls)
    total_ot_pay = sum(p.overtime_pay for p in payrolls)
    total_pay = sum(p.total_pay for p in payrolls)

    return {
        'start_date': start_date,
        'end_date': end_date,
        'employees': payrolls,
        'summary': {
            'total_employees': len(payrolls),
            'total_regular_hours': round(total_regular_hours, 2),
            'total_overtime_hours': round(total_ot_hours, 2),
            'total_hours': round(total_hours, 2),
            'total_regular_pay': round(total_regular_pay, 2),
            'total_overtime_pay': round(total_ot_pay, 2),
            'total_pay': round(total_pay, 2),
        },
        'settings': {
            'overtime_weekly_threshold': overtime_weekly,
            'overtime_daily_threshold': overtime_daily,
            'overtime_multiplier': overtime_multiplier,
        }
    }


def get_biweekly_dates(reference_date: date | None = None) -> tuple[str, str]:
    """
    Get start and end dates for a bi-weekly pay period.
    Assumes pay periods start on Monday.
    """
    if reference_date is None:
        reference_date = date.today()

    # Find Monday of this week (weekday() returns 0 for Monday)
    week_start = reference_date - timedelta(days=reference_date.weekday())

    # Determine which week of the bi-weekly period we're in
    # Using a fixed reference point (Jan 6, 2025 was a Monday)
    reference_monday = date(2025, 1, 6)
    weeks_diff = (week_start - reference_monday).days // 7

    # Even periods start on their own Monday; odd weeks belong to the prior period.
    start = week_start if weeks_diff % 2 == 0 else week_start - timedelta(days=7)

    end = start + timedelta(days=13)
    return start.isoformat(), end.isoformat()
