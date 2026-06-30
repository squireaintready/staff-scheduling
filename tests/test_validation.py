"""Unit tests for the input validators."""

import validation as v


class TestValidateShift:
    def test_valid_shift_no_lunch(self):
        assert v.validate_shift("09:00", "17:00") == []

    def test_valid_shift_with_lunch(self):
        assert v.validate_shift("09:00", "17:00", "12:00", "13:00") == []

    def test_end_before_start_is_rejected(self):
        errors = v.validate_shift("17:00", "09:00")
        assert errors == ["Shift end time must be after the start time."]

    def test_zero_length_shift_is_rejected(self):
        assert v.validate_shift("09:00", "09:00") != []

    def test_lunch_outside_shift_is_rejected(self):
        errors = v.validate_shift("09:00", "12:00", "13:00", "14:00")
        assert any("within the shift" in e for e in errors)

    def test_inverted_lunch_is_rejected(self):
        errors = v.validate_shift("09:00", "17:00", "13:00", "12:00")
        assert any("Lunch end must be after" in e for e in errors)


class TestValidateEmployeeName:
    def test_valid_name(self):
        assert v.validate_employee_name("Alice") == []

    def test_empty_name_is_rejected(self):
        assert v.validate_employee_name("   ") == ["Name cannot be empty."]

    def test_overlong_name_is_rejected(self):
        errors = v.validate_employee_name("x" * 51)
        assert any("characters or fewer" in e for e in errors)

    def test_duplicate_name_is_rejected_case_insensitively(self):
        errors = v.validate_employee_name("alice", existing_names=["Alice", "Bob"])
        assert any("already exists" in e for e in errors)

    def test_unique_name_passes(self):
        assert v.validate_employee_name("Carol", existing_names=["Alice", "Bob"]) == []
