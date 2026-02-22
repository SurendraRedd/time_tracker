# ⏱️ Freelance Time Tracker

A personal time-tracking app built with **Streamlit** and **SQLite**.

## Features

- **Timer** — Start / Pause / Resume / Stop with live display
- **Task management** — Create, archive, and color-code tasks
- **Manual entries** — Log hours after the fact
- **History** — Browse entries grouped by day, filter by date range, export to CSV
- **Dashboard** — Daily / Weekly / Monthly / Yearly analytics with interactive charts
  - Total hours, days worked, average hours per day
  - Login & logout times, break time
  - Hours-by-day bar chart with 8 h target line
  - Task distribution pie chart
  - Weekly work-pattern analysis
  - Monthly summary (yearly view)

## Quick Start

```bash
# 1. Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app opens at **http://localhost:8501**. The SQLite database (`time_tracker.db`) is created automatically in the project folder.

## Project Structure

```
time_tracker/
├── app.py              # Streamlit UI (Timer, History, Dashboard, Tasks)
├── database.py         # SQLite schema & queries
├── requirements.txt    # Python dependencies
├── README.md           # This file
└── time_tracker.db     # Auto-created on first run
```

## Notes

- `streamlit-autorefresh` is optional — if not installed, the timer still works with a manual Refresh button.
- All data is stored locally in `time_tracker.db`. Back up this file to preserve your data.
