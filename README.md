# SubTrack

SubTrack is a Flask web app for tracking personal subscriptions, renewal dates, monthly costs, reminders, categories, reports, and currency preferences.

## Project Structure

- `app.py` - Flask routes, SQLite database access, auth, reports, reminders, and API logic.
- `templates/` - Flask HTML templates.
- `static/css/` - App and printable report styling.
- `static/js/` - Browser-side API calls and UI behavior.
- `data/subtrack.db` - SQLite database for users, subscriptions, and categories (automatically created on first run).

## Run Locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`.

This workspace also supports installing Flask into a local `.vendor` folder:

```powershell
python -m pip install --target .vendor -r requirements.txt
python app.py
```

## Database

SubTrack uses SQLite for secure data storage. The database file (`data/subtrack.db`) is created automatically on first run. If you have an existing JSON database (`data/subtrack_db.json`), it will be automatically migrated to SQLite on the next startup.

## Email Reminders

Reminder emails are sent as test emails. The email sending functionality is in test mode only.
