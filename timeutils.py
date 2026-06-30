"""Pure time-handling helpers shared across the UI.

Times are stored as 24-hour ``HH:MM`` strings and presented to users as
12-hour labels (e.g. ``9AM``, ``3:30PM``). Keeping these functions free of any
Streamlit dependency makes them easy to unit-test in isolation.
"""

from datetime import datetime


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
    lunch_s, _lunch_e = get_default_lunch(start_time, end_time)
    return lunch_s is not None
