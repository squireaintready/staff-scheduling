"""CRUD and persistence tests for the SQLite data-access layer.

Each test runs against an isolated temporary database (see ``conftest.py``).
"""


class TestEmployeeCrud:
    def test_add_and_get_employee(self, temp_db):
        emp_id = temp_db.add_employee("Alice", 18.50)
        emp = temp_db.get_employee(emp_id)
        assert emp is not None
        assert emp["name"] == "Alice"
        assert emp["hourly_rate"] == 18.50
        assert emp["is_active"] == 1

    def test_get_employees_excludes_inactive_by_default(self, temp_db):
        active_id = temp_db.add_employee("Active")
        inactive_id = temp_db.add_employee("Inactive")
        temp_db.update_employee(inactive_id, is_active=False)

        active_names = {e["name"] for e in temp_db.get_employees()}
        all_names = {e["name"] for e in temp_db.get_employees(active_only=False)}

        assert active_names == {"Active"}
        assert all_names == {"Active", "Inactive"}
        assert active_id != inactive_id

    def test_update_employee_changes_only_supplied_fields(self, temp_db):
        emp_id = temp_db.add_employee("Bob", 12.0)
        temp_db.update_employee(emp_id, hourly_rate=15.0)
        emp = temp_db.get_employee(emp_id)
        assert emp["name"] == "Bob"  # unchanged
        assert emp["hourly_rate"] == 15.0  # changed

    def test_soft_delete_keeps_row_but_marks_inactive(self, temp_db):
        emp_id = temp_db.add_employee("Carol")
        temp_db.delete_employee(emp_id)
        assert temp_db.get_employee(emp_id)["is_active"] == 0

    def test_hard_delete_removes_employee_and_shifts(self, temp_db):
        emp_id = temp_db.add_employee("Dave")
        temp_db.add_shift(emp_id, "2026-01-19", "09:00", "17:00")
        temp_db.hard_delete_employee(emp_id)
        assert temp_db.get_employee(emp_id) is None
        assert temp_db.get_shifts_for_employee(emp_id, "2026-01-01", "2026-12-31") == []


class TestShiftCrud:
    def test_add_shift_is_idempotent_per_employee_per_day(self, temp_db):
        emp_id = temp_db.add_employee("Eve")
        temp_db.add_shift(emp_id, "2026-01-19", "09:00", "17:00")
        # Re-adding the same day should update in place, not duplicate.
        temp_db.add_shift(emp_id, "2026-01-19", "10:00", "18:00")
        shifts = temp_db.get_shifts_for_employee(emp_id, "2026-01-19", "2026-01-19")
        assert len(shifts) == 1
        assert shifts[0]["start_time"] == "10:00"

    def test_delete_shift(self, temp_db):
        emp_id = temp_db.add_employee("Frank")
        temp_db.add_shift(emp_id, "2026-01-19", "09:00", "17:00")
        assert temp_db.delete_shift(emp_id, "2026-01-19") is True
        assert temp_db.get_shifts_for_employee(emp_id, "2026-01-19", "2026-01-19") == []

    def test_get_shifts_for_week_joins_employee_data(self, temp_db):
        emp_id = temp_db.add_employee("Grace", 20.0)
        temp_db.add_shift(emp_id, "2026-01-20", "09:00", "17:00")
        rows = temp_db.get_shifts_for_week("2026-01-19", "2026-01-25")
        assert len(rows) == 1
        assert rows[0]["employee_name"] == "Grace"
        assert rows[0]["hourly_rate"] == 20.0


class TestSettings:
    def test_defaults_are_seeded_on_init(self, temp_db):
        settings = temp_db.get_all_settings()
        assert settings["overtime_weekly_threshold"] == "40"
        assert settings["overtime_multiplier"] == "1.5"

    def test_set_setting_overwrites(self, temp_db):
        temp_db.set_setting("overtime_multiplier", "2.0")
        assert temp_db.get_setting("overtime_multiplier") == "2.0"

    def test_get_setting_returns_default_when_missing(self, temp_db):
        assert temp_db.get_setting("does_not_exist", default="fallback") == "fallback"
