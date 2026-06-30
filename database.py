"""
Database module for Employee Scheduling & Payroll App.
Uses SQLite for persistent storage.
"""

import os
import sqlite3
from contextlib import contextmanager, suppress

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "scheduling.db")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize database with all required tables."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Employees table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                hourly_rate REAL NOT NULL DEFAULT 10.0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Shift templates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shift_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                lunch_start TEXT,
                lunch_end TEXT,
                color TEXT DEFAULT '#3498db'
            )
        """)

        # Scheduled shifts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                shift_date DATE NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                lunch_start TEXT,
                lunch_end TEXT,
                template_id INTEGER,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (template_id) REFERENCES shift_templates(id),
                UNIQUE(employee_id, shift_date)
            )
        """)

        # Migration: Add lunch columns if they don't exist
        for table in ['shifts', 'shift_templates']:
            with suppress(sqlite3.OperationalError):
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN lunch_start TEXT")
            with suppress(sqlite3.OperationalError):
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN lunch_end TEXT")

        # Migration: Add last_modified column to shifts
        with suppress(sqlite3.OperationalError):
            cursor.execute(
                "ALTER TABLE shifts ADD COLUMN last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )

        # Settings table for app configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Insert default settings
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value) VALUES
            ('default_close_time', '21:00'),
            ('overtime_weekly_threshold', '40'),
            ('overtime_daily_threshold', '8'),
            ('overtime_multiplier', '1.5')
        """)


# ============ Employee CRUD ============

def add_employee(name: str, hourly_rate: float = 10.0) -> int:
    """Add a new employee."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO employees (name, hourly_rate) VALUES (?, ?)",
            (name, hourly_rate)
        )
        return cursor.lastrowid


def get_employees(active_only: bool = True) -> list[dict]:
    """Get all employees."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM employees WHERE is_active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM employees ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]


def get_employee(employee_id: int) -> dict | None:
    """Get a single employee by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_employee(employee_id: int, name: str | None = None, hourly_rate: float | None = None,
                    is_active: bool | None = None) -> bool:
    """Update an employee."""
    updates: list[str] = []
    values: list[object] = []

    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if hourly_rate is not None:
        updates.append("hourly_rate = ?")
        values.append(hourly_rate)
    if is_active is not None:
        updates.append("is_active = ?")
        values.append(1 if is_active else 0)

    if not updates:
        return False

    values.append(employee_id)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE employees SET {', '.join(updates)} WHERE id = ?",
            values
        )
        return cursor.rowcount > 0


def delete_employee(employee_id: int) -> bool:
    """Soft delete an employee (set inactive)."""
    return update_employee(employee_id, is_active=False)


def hard_delete_employee(employee_id: int) -> bool:
    """Permanently delete an employee and all their shifts."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Delete all shifts for this employee first
        cursor.execute("DELETE FROM shifts WHERE employee_id = ?", (employee_id,))
        # Delete the employee
        cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
        return cursor.rowcount > 0


# ============ Shift Template CRUD ============

def add_shift_template(name: str, start_time: str, end_time: str,
                       lunch_start: str | None = None, lunch_end: str | None = None,
                       color: str = "#3498db") -> int:
    """Add a new shift template."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO shift_templates (name, start_time, end_time, lunch_start, lunch_end, color) VALUES (?, ?, ?, ?, ?, ?)",
            (name, start_time, end_time, lunch_start, lunch_end, color)
        )
        return cursor.lastrowid


def get_shift_templates() -> list[dict]:
    """Get all shift templates."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shift_templates ORDER BY start_time")
        return [dict(row) for row in cursor.fetchall()]


def update_shift_template(template_id: int, name: str | None = None, start_time: str | None = None,
                          end_time: str | None = None, lunch_start: str | None = None,
                          lunch_end: str | None = None, color: str | None = None) -> bool:
    """Update a shift template."""
    updates: list[str] = []
    values: list[object] = []

    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if start_time is not None:
        updates.append("start_time = ?")
        values.append(start_time)
    if end_time is not None:
        updates.append("end_time = ?")
        values.append(end_time)
    if lunch_start is not None:
        updates.append("lunch_start = ?")
        values.append(lunch_start if lunch_start else None)
    if lunch_end is not None:
        updates.append("lunch_end = ?")
        values.append(lunch_end if lunch_end else None)
    if color is not None:
        updates.append("color = ?")
        values.append(color)

    if not updates:
        return False

    values.append(template_id)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE shift_templates SET {', '.join(updates)} WHERE id = ?",
            values
        )
        return cursor.rowcount > 0


def delete_shift_template(template_id: int) -> bool:
    """Delete a shift template."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shift_templates WHERE id = ?", (template_id,))
        return cursor.rowcount > 0


# ============ Shift CRUD ============

def add_shift(employee_id: int, shift_date: str, start_time: str,
              end_time: str, lunch_start: str | None = None, lunch_end: str | None = None,
              template_id: int | None = None) -> int:
    """Add or update a shift for an employee on a date."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shifts (employee_id, shift_date, start_time, end_time, lunch_start, lunch_end, template_id, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(employee_id, shift_date)
            DO UPDATE SET start_time = ?, end_time = ?, lunch_start = ?, lunch_end = ?, template_id = ?, last_modified = CURRENT_TIMESTAMP
        """, (employee_id, shift_date, start_time, end_time, lunch_start, lunch_end, template_id,
              start_time, end_time, lunch_start, lunch_end, template_id))
        return cursor.lastrowid


def get_shifts_for_week(start_date: str, end_date: str) -> list[dict]:
    """Get all shifts for a date range."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, e.name as employee_name, e.hourly_rate,
                   t.name as template_name, t.color as template_color
            FROM shifts s
            JOIN employees e ON s.employee_id = e.id
            LEFT JOIN shift_templates t ON s.template_id = t.id
            WHERE s.shift_date BETWEEN ? AND ?
            ORDER BY s.shift_date, e.name
        """, (start_date, end_date))
        return [dict(row) for row in cursor.fetchall()]


def get_shifts_for_employee(employee_id: int, start_date: str, end_date: str) -> list[dict]:
    """Get shifts for a specific employee in a date range."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM shifts
            WHERE employee_id = ? AND shift_date BETWEEN ? AND ?
            ORDER BY shift_date
        """, (employee_id, start_date, end_date))
        return [dict(row) for row in cursor.fetchall()]


def get_last_modified_for_employee(employee_id: int, start_date: str, end_date: str) -> str | None:
    """Get the most recent modification time for an employee's shifts in a date range."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(last_modified) as last_mod FROM shifts
            WHERE employee_id = ? AND shift_date BETWEEN ? AND ?
        """, (employee_id, start_date, end_date))
        row = cursor.fetchone()
        return row['last_mod'] if row and row['last_mod'] else None


def delete_shift(employee_id: int, shift_date: str) -> bool:
    """Delete a shift."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM shifts WHERE employee_id = ? AND shift_date = ?",
            (employee_id, shift_date)
        )
        return cursor.rowcount > 0


def clear_shifts_for_week(start_date: str, end_date: str) -> int:
    """Clear all shifts for a week."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM shifts WHERE shift_date BETWEEN ? AND ?",
            (start_date, end_date)
        )
        return cursor.rowcount


# ============ Settings ============

def get_setting(key: str, default: str | None = None) -> str | None:
    """Get a setting value."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default


def set_setting(key: str, value: str) -> None:
    """Set a setting value."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )


def get_all_settings() -> dict:
    """Get all settings as a dictionary."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row['key']: row['value'] for row in cursor.fetchall()}


# Initialize database on module import
init_database()
