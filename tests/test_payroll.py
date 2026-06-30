"""Unit tests for the payroll calculation engine.

These cover the pure business logic in ``payroll.py``: shift-hour math,
daily/weekly overtime distribution, and pay-period date helpers. No database
or Streamlit involvement, so they run fast and deterministically.
"""

from datetime import date

import pytest

import payroll as pr


# --------------------------------------------------------------------------- #
# parse_time
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "value, expected",
    [
        ("09:30", (9, 30)),
        ("00:00", (0, 0)),
        ("23:45", (23, 45)),
        ("9", (9, 0)),  # missing minutes defaults to 0
    ],
)
def test_parse_time(value, expected):
    assert pr.parse_time(value) == expected


# --------------------------------------------------------------------------- #
# calculate_shift_hours
# --------------------------------------------------------------------------- #
class TestCalculateShiftHours:
    def test_simple_shift_no_lunch(self):
        assert pr.calculate_shift_hours("09:00", "17:00") == 8.0

    def test_shift_with_lunch_deducted(self):
        assert pr.calculate_shift_hours("09:00", "17:00", "12:00", "13:00") == 7.0

    def test_fifteen_minute_resolution(self):
        assert pr.calculate_shift_hours("09:00", "09:15") == 0.25

    def test_overnight_shift_wraps_past_midnight(self):
        # 10pm -> 6am should be 8 hours, not negative.
        assert pr.calculate_shift_hours("22:00", "06:00") == 8.0

    def test_zero_length_shift_is_zero(self):
        assert pr.calculate_shift_hours("09:00", "09:00") == 0.0

    def test_partial_lunch_with_only_one_bound_ignored(self):
        # A lunch needs both bounds to be deducted.
        assert pr.calculate_shift_hours("09:00", "17:00", "12:00", None) == 8.0

    def test_negative_lunch_duration_is_ignored(self):
        # lunch_end before lunch_start should not add time back.
        assert pr.calculate_shift_hours("09:00", "17:00", "13:00", "12:00") == 8.0


# --------------------------------------------------------------------------- #
# calculate_daily_overtime
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "hours, threshold, expected",
    [
        (6.0, 8.0, (6.0, 0.0)),  # under threshold
        (8.0, 8.0, (8.0, 0.0)),  # exactly at threshold
        (10.0, 8.0, (8.0, 2.0)),  # over threshold -> 2h OT
        (0.0, 8.0, (0.0, 0.0)),  # day off
    ],
)
def test_calculate_daily_overtime(hours, threshold, expected):
    assert pr.calculate_daily_overtime(hours, threshold) == expected


# --------------------------------------------------------------------------- #
# calculate_weekly_overtime
# --------------------------------------------------------------------------- #
class TestCalculateWeeklyOvertime:
    def test_all_regular_under_weekly_cap(self):
        results = pr.calculate_weekly_overtime([8, 8, 8, 8, 8, 0, 0], 40, 8)
        assert sum(reg for reg, _ in results) == 40
        assert sum(ot for _, ot in results) == 0

    def test_sixth_eight_hour_day_becomes_weekly_overtime(self):
        # 6 x 8 = 48h. With a 40h weekly cap, 8h spill into overtime.
        results = pr.calculate_weekly_overtime([8, 8, 8, 8, 8, 8, 0], 40, 8)
        assert sum(reg for reg, _ in results) == 40
        assert sum(ot for _, ot in results) == 8

    def test_daily_overtime_triggers_even_in_a_light_week(self):
        # A single 10h day is under the weekly cap but over the daily cap.
        results = pr.calculate_weekly_overtime([10, 0, 0, 0, 0, 0, 0], 40, 8)
        assert results[0] == (8, 2)

    def test_daily_and_weekly_overtime_combine(self):
        # Five 10h days = 50h worked. Daily rule carves 2h/day (10h total) as OT,
        # leaving 40h of "regular" which exactly fills the weekly cap.
        results = pr.calculate_weekly_overtime([10, 10, 10, 10, 10, 0, 0], 40, 8)
        total_regular = sum(reg for reg, _ in results)
        total_ot = sum(ot for _, ot in results)
        assert total_regular == 40
        assert total_ot == 10
        assert total_regular + total_ot == 50


# --------------------------------------------------------------------------- #
# pay-period date helpers
# --------------------------------------------------------------------------- #
class TestPayPeriodDates:
    def test_get_week_dates_starts_on_monday(self):
        # 2026-01-21 is a Wednesday; the week should start Monday the 19th.
        start, end, days = pr.get_week_dates(date(2026, 1, 21))
        assert start == "2026-01-19"
        assert end == "2026-01-25"
        assert len(days) == 7
        assert days[0] == "2026-01-19"

    def test_biweekly_period_is_fourteen_days(self):
        start, end = pr.get_biweekly_dates(date(2026, 1, 21))
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
        assert (end_d - start_d).days == 13  # inclusive 14-day span

    def test_biweekly_periods_are_stable_within_a_period(self):
        # Two dates in different calendar weeks but the same biweekly period
        # must resolve to the same boundaries; the next week flips the period.
        week_one = pr.get_biweekly_dates(date(2026, 1, 6))
        week_two = pr.get_biweekly_dates(date(2026, 1, 14))
        next_period = pr.get_biweekly_dates(date(2026, 1, 19))
        assert week_one == week_two == ("2026-01-05", "2026-01-18")
        assert next_period == ("2026-01-19", "2026-02-01")
