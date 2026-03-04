# Staff Scheduling — Shift Management & Payroll

A Streamlit-based scheduling and payroll application built for restaurant and hospitality operations. Manages employee shifts, calculates payroll, and provides an authenticated dashboard for managers.

## Features

- **Shift Scheduling** — Create, edit, and manage employee schedules by day and role
- **Payroll Calculator** — Automatic payroll calculations based on hours worked, roles, and rates
- **Authentication** — Password-protected access for managers
- **Database-Backed** — Persistent storage for employees, schedules, and payroll records
- **Responsive Dashboard** — Clean Streamlit UI accessible from any device

## Tech Stack

- **Framework:** Streamlit
- **Language:** Python
- **Data Processing:** Pandas
- **Database:** SQLite (via custom `database.py` module)

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Configure password (create .streamlit/secrets.toml)
echo 'password = "your-password"' > .streamlit/secrets.toml

# Run the app
streamlit run app.py
```

## Project Structure

```
staff-scheduling/
├── app.py           # Main Streamlit application
├── database.py      # Database models and operations
├── payroll.py       # Payroll calculation logic
└── requirements.txt # Python dependencies
```

## Why This Exists

Built to solve a real operational need — managing shift schedules and payroll for a 15+ person restaurant team. Replaced manual spreadsheet tracking with an automated, authenticated dashboard.

## Author

**Samuel Jo** — [GitHub](https://github.com/squireaintready) · [LinkedIn](https://linkedin.com/in/samuel-jo)
