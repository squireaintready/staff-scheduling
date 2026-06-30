"""Seed the database with realistic sample data for demos and local exploration.

    python seed_demo.py

Safe to re-run — it clears employees, templates, and shifts first, then
recreates a full week of shifts (including some overtime) across several roles
so the payroll report has something interesting to show.
"""

from datetime import date, timedelta

import database as db

# (name, hourly_rate, role)
EMPLOYEES = [
    ("Ava Martinez", 18.0, "Server"),
    ("Ben Carter", 17.5, "Server"),
    ("Cody Nguyen", 24.0, "Cook"),
    ("Dana White", 26.0, "Cook"),
    ("Eli Brooks", 16.0, "Host"),
    ("Farah Khan", 22.0, "Bartender"),
    ("Grace Lee", 30.0, "Manager"),
    ("Hugo Diaz", 15.0, "Busser"),
]

# (name, start, end, lunch_start, lunch_end, color)
TEMPLATES = [
    ("Morning", "09:00", "17:00", "15:00", "16:00", "#3498db"),
    ("Mid", "11:00", "19:00", "15:00", "16:00", "#2ecc71"),
    ("Evening", "16:00", "23:00", None, None, "#e67e22"),
]


def clear() -> None:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM shifts")
        conn.execute("DELETE FROM shift_templates")
        conn.execute("DELETE FROM employees")


def seed() -> None:
    clear()
    emp_ids = [db.add_employee(name, rate, role) for name, rate, role in EMPLOYEES]
    for tmpl in TEMPLATES:
        db.add_shift_template(*tmpl)

    monday = date.today() - timedelta(days=date.today().weekday())

    for idx, emp_id in enumerate(emp_ids):
        # Everyone works Monday–Friday, 9–5 with a lunch (7h/day = 35h/week).
        for offset in range(5):
            day = (monday + timedelta(days=offset)).isoformat()
            db.add_shift(emp_id, day, "09:00", "17:00", "15:00", "16:00")

        # The manager also covers Saturday -> tips into weekly overtime (>40h).
        if EMPLOYEES[idx][2] == "Manager":
            sat = (monday + timedelta(days=5)).isoformat()
            db.add_shift(emp_id, sat, "09:00", "17:00", "15:00", "16:00")

        # One cook pulls a 10-hour Wednesday -> daily overtime.
        if EMPLOYEES[idx][0] == "Cody Nguyen":
            wed = (monday + timedelta(days=2)).isoformat()
            db.add_shift(emp_id, wed, "08:00", "18:00", "15:00", "16:00")

    print(
        f"Seeded {len(emp_ids)} employees, {len(TEMPLATES)} templates, "
        f"and a week of shifts starting {monday.isoformat()}."
    )


if __name__ == "__main__":
    seed()
