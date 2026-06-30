"""Unit tests for the pure time helpers in timeutils.py."""

import pytest

import timeutils as tu


@pytest.mark.parametrize(
    "value, expected",
    [
        ("09:00", "9AM"),
        ("13:30", "1:30PM"),
        ("00:00", "12AM"),
        ("12:00", "12PM"),
        ("23:15", "11:15PM"),
        ("not-a-time", "not-a-time"),  # invalid input passes through unchanged
    ],
)
def test_format_time_12h(value, expected):
    assert tu.format_time_12h(value) == expected


def test_format_time_range():
    assert tu.format_time_range("09:00", "17:00") == "9AM-5PM"


class TestDefaultLunch:
    def test_midday_shift_gets_3_to_4pm_lunch(self):
        assert tu.get_default_lunch("09:00", "18:00") == ("15:00", "16:00")

    def test_shift_starting_after_4pm_has_no_lunch(self):
        assert tu.get_default_lunch("16:00", "22:00") == (None, None)

    def test_shift_ending_by_4pm_has_no_lunch(self):
        assert tu.get_default_lunch("09:00", "16:00") == (None, None)

    def test_should_have_lunch_mirrors_default_lunch(self):
        assert tu.should_have_lunch("09:00", "18:00") is True
        assert tu.should_have_lunch("17:00", "22:00") is False


class TestTimeOptions:
    def test_range_and_step(self):
        opts = tu.get_time_options()
        assert opts[0] == ("08:45", "8:45AM")
        assert opts[-1] == ("23:15", "11:15PM")
        # 15-minute increments only.
        minutes = {int(t.split(":")[1]) for t, _ in opts}
        assert minutes == {0, 15, 30, 45}

    def test_lookup_tables_are_consistent(self):
        # Every label maps back to its 24h time.
        for time_24, label in tu.TIME_OPTIONS:
            assert tu.TIME_LABEL_TO_24[label] == time_24
            assert tu.TIME_24_TO_LABEL[time_24] == label


class TestLabelConversion:
    def test_label_to_time_round_trips(self):
        for _time_24, label in tu.TIME_OPTIONS:
            assert tu.time_to_label(tu.label_to_time(label)) == label

    def test_time_to_label_rounds_to_nearest_quarter_hour(self):
        assert tu.time_to_label("09:07") == "9AM"      # rounds down
        assert tu.time_to_label("09:08") == "9:15AM"   # rounds up

    def test_time_to_label_clamps_below_range(self):
        assert tu.time_to_label("06:00") == tu.TIME_LABELS[0]

    def test_unknown_label_falls_back_to_default(self):
        assert tu.label_to_time("nonsense") == "10:00"


def test_get_time_index_uses_fallback_when_missing():
    assert tu.get_time_index("10AM") == tu.TIME_LABELS.index("10AM")
    # Unknown label falls back to the supplied default label's index.
    assert tu.get_time_index("nope", default_label="9AM") == tu.TIME_LABELS.index("9AM")
