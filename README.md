# SubTrack

SubTrack is a Flask web app for tracking personal subscriptions, renewal dates, monthly costs, reminders, categories, reports, and currency preferences.

## Project Structure

- `app.py` - Flask routes, JSON database access, auth, reports, reminders, and API logic.
- `templates/` - Flask HTML templates.
- `static/css/` - App and printable report styling.
- `static/js/` - Browser-side API calls and UI behavior.
- `data/subtrack_db.json` - Local file database for users, categories, and subscriptions.

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

## Email Reminders

Reminder emails are sent as test emails. The email sending functionality currently does not work.
