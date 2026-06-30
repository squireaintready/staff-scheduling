"""Input validation for schedule, template, and employee data.

Each validator is a pure function returning a list of human-readable error
messages (an empty list means valid). Keeping them free of Streamlit makes
them trivial to unit-test and reuse across views.
"""

MAX_NAME_LENGTH = 50


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def validate_shift(
    start: str,
    end: str,
    lunch_start: str | None = None,
    lunch_end: str | None = None,
) -> list[str]:
    """Validate a single shift's times. Returns a list of error messages."""
    errors: list[str] = []
    start_m, end_m = _to_minutes(start), _to_minutes(end)

    if end_m <= start_m:
        # The shift itself is invalid; lunch checks would just be noise.
        return ["Shift end time must be after the start time."]

    if lunch_start and lunch_end:
        lunch_s, lunch_e = _to_minutes(lunch_start), _to_minutes(lunch_end)
        if lunch_e <= lunch_s:
            errors.append("Lunch end must be after lunch start.")
        if lunch_s < start_m or lunch_e > end_m:
            errors.append("Lunch must fall within the shift.")

    return errors


def validate_employee_name(name: str, existing_names: list[str] | None = None) -> list[str]:
    """Validate an employee name (non-empty, length-bounded, unique)."""
    cleaned = name.strip()
    if not cleaned:
        return ["Name cannot be empty."]

    errors: list[str] = []
    if len(cleaned) > MAX_NAME_LENGTH:
        errors.append(f"Name must be {MAX_NAME_LENGTH} characters or fewer.")
    if existing_names and cleaned.casefold() in {n.strip().casefold() for n in existing_names}:
        errors.append(f"An employee named '{cleaned}' already exists.")
    return errors
