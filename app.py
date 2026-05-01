from __future__ import annotations

import csv
import io
import json
import os
import sys
import uuid
from datetime import date, datetime
 
from functools import wraps
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = BASE_DIR / ".vendor"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

from flask import Flask, Response, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash


DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "subtrack_db.json"

DEFAULT_CATEGORIES = [
    {"id": "streaming", "name": "Streaming"},
    {"id": "gaming", "name": "Gaming"},
    {"id": "productivity", "name": "Productivity"},
    {"id": "music", "name": "Music"},
    {"id": "cloud", "name": "Cloud"},
    {"id": "fitness", "name": "Fitness"},
    {"id": "other", "name": "Other"},
]

CURRENCY_SYMBOLS = {
    "PHP": "PHP ",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}

app = Flask(__name__)
app.secret_key = os.environ.get("SUBTRACK_SECRET_KEY", "subtrack-dev-secret-change-me")


def today() -> date:
    return date.today()


def empty_db() -> dict:
    return {"users": [], "subscriptions": [], "categories": DEFAULT_CATEGORIES}





def ensure_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not DB_PATH.exists():
        write_db(empty_db())


def read_db() -> dict:
    ensure_files()
    with DB_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    data.setdefault("users", [])
    data.setdefault("subscriptions", [])
    data.setdefault("categories", DEFAULT_CATEGORIES)
    return data


def write_db(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    DB_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def current_user() -> dict | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return next((u for u in read_db()["users"] if u["id"] == user_id), None)


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "settings": user.get("settings", default_settings()),
    }


def default_settings() -> dict:
    return {
        "currency": "PHP",
        "remindSevenDays": True,
        "remindOneDay": True,
    }


def require_login(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "Please sign in first."}), 401
        return handler(*args, **kwargs)

    return wrapper


def parse_json() -> dict:
    return request.get_json(silent=True) or {}


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def owned_subscriptions(data: dict, user_id: str) -> list[dict]:
    return [s for s in data["subscriptions"] if s.get("userId") == user_id]


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def to_monthly(cost: float, cycle: str) -> float:
    if cycle == "weekly":
        return cost * 52 / 12
    if cycle == "yearly":
        return cost / 12
    return cost


def to_annual(cost: float, cycle: str) -> float:
    if cycle == "weekly":
        return cost * 52
    if cycle == "yearly":
        return cost
    return cost * 12


def days_until(renewal: str) -> int:
    parsed = parse_date(renewal)
    if not parsed:
        return 9999
    return (parsed - today()).days


def status_for(renewal: str) -> str:
    days = days_until(renewal)
    if days < 0:
        return "expired"
    if days <= 7:
        return "renewing"
    return "active"


def is_default_category(category_id: str) -> bool:
    return any(category["id"] == category_id for category in DEFAULT_CATEGORIES)


def visible_categories(data: dict, user_id: str) -> list[dict]:
    custom = [
        category
        for category in data["categories"]
        if category.get("userId") == user_id and not is_default_category(category["id"])
    ]
    return DEFAULT_CATEGORIES + custom


def category_name(data: dict, category_id: str, user_id: str) -> str:
    category = next((c for c in visible_categories(data, user_id) if c["id"] == category_id), None)
    return category["name"] if category else "Other"


def validate_subscription(payload: dict) -> tuple[dict | None, str | None]:
    name = normalize_text(payload.get("name"))
    cycle = normalize_text(payload.get("cycle")) or "monthly"
    category_id = normalize_text(payload.get("categoryId")) or "other"
    renewal = normalize_text(payload.get("renewalDate"))
    notes = normalize_text(payload.get("notes"))
    try:
        cost = float(payload.get("cost"))
    except (TypeError, ValueError):
        return None, "Cost must be a number."
    if not name:
        return None, "Subscription name is required."
    if cost < 0:
        return None, "Cost cannot be negative."
    if cycle not in {"weekly", "monthly", "yearly"}:
        return None, "Billing cycle is invalid."
    if not parse_date(renewal):
        return None, "Renewal date must use YYYY-MM-DD."
    return {
        "name": name,
        "cost": round(cost, 2),
        "cycle": cycle,
        "categoryId": category_id,
        "renewalDate": renewal,
        "notes": notes,
    }, None


def serialize_subscription(sub: dict, data: dict) -> dict:
    return {
        **sub,
        "categoryName": category_name(data, sub.get("categoryId", "other"), sub["userId"]),
        "monthlyCost": round(to_monthly(float(sub["cost"]), sub["cycle"]), 2),
        "annualCost": round(to_annual(float(sub["cost"]), sub["cycle"]), 2),
        "daysUntilRenewal": days_until(sub["renewalDate"]),
        "status": status_for(sub["renewalDate"]),
    }


def build_dashboard(data: dict, user: dict) -> dict:
    subs = [serialize_subscription(s, data) for s in owned_subscriptions(data, user["id"])]
    monthly_total = round(sum(s["monthlyCost"] for s in subs), 2)
    annual_total = round(sum(s["annualCost"] for s in subs), 2)
    upcoming = sorted(
        [s for s in subs if s["daysUntilRenewal"] >= 0],
        key=lambda item: item["daysUntilRenewal"],
    )
    category_totals: dict[str, float] = {}
    cycle_counts: dict[str, int] = {}
    for sub in subs:
        category_totals[sub["categoryName"]] = category_totals.get(sub["categoryName"], 0) + sub["monthlyCost"]
        cycle_counts[sub["cycle"]] = cycle_counts.get(sub["cycle"], 0) + 1
    reminders = due_reminders(subs, user.get("settings", default_settings()))
    return {
        "monthlyTotal": monthly_total,
        "annualTotal": annual_total,
        "activeCount": len([s for s in subs if s["status"] != "expired"]),
        "renewingSoonCount": len([s for s in subs if 0 <= s["daysUntilRenewal"] <= 7]),
        "upcoming": upcoming[:6],
        "categoryTotals": {k: round(v, 2) for k, v in category_totals.items()},
        "cycleCounts": cycle_counts,
        "reminders": reminders,
    }


def due_reminders(subs: list[dict], settings: dict) -> list[dict]:
    days_enabled = set()
    if settings.get("remindSevenDays", True):
        days_enabled.add(7)
    if settings.get("remindOneDay", True):
        days_enabled.add(1)
    days_enabled.add(0)
    return [
        {
            "subscriptionId": sub["id"],
            "name": sub["name"],
            "renewalDate": sub["renewalDate"],
            "daysUntilRenewal": sub["daysUntilRenewal"],
            "message": f"{sub['name']} renews {'today' if sub['daysUntilRenewal'] == 0 else 'in ' + str(sub['daysUntilRenewal']) + ' day(s)'}.",
        }
        for sub in subs
        if sub["daysUntilRenewal"] in days_enabled
    ]


def send_email(data: dict, to_email: str, subject: str, body: str) -> tuple[dict, int]:
    # SMTP features removed — this is a test-only stub.
    # Return the email contents without attempting to send.
    return {
        "sent": 1,
        "message": f"Email woud've been sent to {to_email}, but this is only a test.",
        "subject": subject,
        "body": body,
    }, 200


def send_reminder_email(data: dict, user: dict, reminders: list[dict]) -> tuple[dict, int]:
    if not reminders:
        return {"sent": 0, "message": "No reminders are due today."}, 200
    subject = "SubTrack renewal reminder"
    body = "\n".join(reminder["message"] for reminder in reminders)
    return send_email(data, user["email"], subject, body)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/session")
def session_info():
    user = current_user()
    return jsonify({"user": public_user(user) if user else None})


@app.post("/api/register")
def register():
    payload = parse_json()
    name = normalize_text(payload.get("name"))
    email = normalize_text(payload.get("email")).lower()
    password = str(payload.get("password") or "")
    if not name or not email or len(password) < 6:
        return jsonify({"error": "Name, email, and a 6-character password are required."}), 400
    data = read_db()
    if any(u["email"] == email for u in data["users"]):
        return jsonify({"error": "An account with that email already exists."}), 400
    user = {
        "id": uuid.uuid4().hex,
        "name": name,
        "email": email,
        "passwordHash": generate_password_hash(password),
        "settings": default_settings(),
        "createdAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    data["users"].append(user)
    write_db(data)
    session["user_id"] = user["id"]
    email_result, email_status = send_email(
        data,
        user["email"],
        "Welcome to SubTrack",
        f"Hi {user['name']},\n\nWelcome to SubTrack. You can now track subscriptions, renewal dates, reminders, and spending reports in one place.\n\n- SubTrack",
    )
    response = {"user": public_user(user), "welcomeEmailSent": email_status == 200}
    if email_status != 200:
        response["emailWarning"] = email_result.get("error", "Welcome email could not be sent.")
    return jsonify(response), 201


@app.post("/api/login")
def login():
    payload = parse_json()
    email = normalize_text(payload.get("email")).lower()
    password = str(payload.get("password") or "")
    user = next((u for u in read_db()["users"] if u["email"] == email), None)
    if not user or not check_password_hash(user["passwordHash"], password):
        return jsonify({"error": "Invalid email or password."}), 401
    session["user_id"] = user["id"]
    return jsonify({"user": public_user(user)})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.put("/api/profile")
@require_login
def update_profile():
    payload = parse_json()
    name = normalize_text(payload.get("name"))
    if not name:
        return jsonify({"error": "Name is required."}), 400
    data = read_db()
    user = next(u for u in data["users"] if u["id"] == session["user_id"])
    user["name"] = name
    user["settings"] = {**default_settings(), **user.get("settings", {}), **payload.get("settings", {})}
    write_db(data)
    return jsonify({"user": public_user(user)})





@app.get("/api/categories")
@require_login
def get_categories():
    data = read_db()
    return jsonify({"categories": visible_categories(data, session["user_id"])})


@app.post("/api/categories")
@require_login
def create_category():
    name = normalize_text(parse_json().get("name"))
    if not name:
        return jsonify({"error": "Category name is required."}), 400
    data = read_db()
    category_id = name.lower().replace(" ", "-")
    if any(c["id"] == category_id for c in visible_categories(data, session["user_id"])):
        return jsonify({"error": "That category already exists."}), 400
    category = {"id": category_id, "name": name, "userId": session["user_id"]}
    data["categories"].append(category)
    write_db(data)
    return jsonify({"category": category}), 201


@app.get("/api/subscriptions")
@require_login
def list_subscriptions():
    data = read_db()
    query = normalize_text(request.args.get("q")).lower()
    category = normalize_text(request.args.get("category"))
    status = normalize_text(request.args.get("status"))
    subs = [serialize_subscription(s, data) for s in owned_subscriptions(data, session["user_id"])]
    if query:
        subs = [s for s in subs if query in s["name"].lower() or query in s.get("notes", "").lower()]
    if category:
        subs = [s for s in subs if s["categoryId"] == category]
    if status:
        subs = [s for s in subs if s["status"] == status]
    return jsonify({"subscriptions": sorted(subs, key=lambda item: item["renewalDate"])})


@app.post("/api/subscriptions")
@require_login
def create_subscription():
    fields, error = validate_subscription(parse_json())
    if error:
        return jsonify({"error": error}), 400
    data = read_db()
    sub = {
        "id": uuid.uuid4().hex,
        "userId": session["user_id"],
        **fields,
        "createdAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    data["subscriptions"].append(sub)
    write_db(data)
    return jsonify({"subscription": serialize_subscription(sub, data)}), 201


@app.put("/api/subscriptions/<sub_id>")
@require_login
def update_subscription(sub_id: str):
    fields, error = validate_subscription(parse_json())
    if error:
        return jsonify({"error": error}), 400
    data = read_db()
    sub = next((s for s in data["subscriptions"] if s["id"] == sub_id and s["userId"] == session["user_id"]), None)
    if not sub:
        return jsonify({"error": "Subscription not found."}), 404
    sub.update(fields)
    write_db(data)
    return jsonify({"subscription": serialize_subscription(sub, data)})


@app.delete("/api/subscriptions/<sub_id>")
@require_login
def delete_subscription(sub_id: str):
    data = read_db()
    before = len(data["subscriptions"])
    data["subscriptions"] = [
        s for s in data["subscriptions"] if not (s["id"] == sub_id and s["userId"] == session["user_id"])
    ]
    if len(data["subscriptions"]) == before:
        return jsonify({"error": "Subscription not found."}), 404
    write_db(data)
    return jsonify({"ok": True})


@app.get("/api/dashboard")
@require_login
def dashboard():
    data = read_db()
    user = next(u for u in data["users"] if u["id"] == session["user_id"])
    return jsonify(build_dashboard(data, user))


@app.post("/api/reminders/send")
@require_login
def send_reminders():
    data = read_db()
    user = next(u for u in data["users"] if u["id"] == session["user_id"])
    subs = [serialize_subscription(s, data) for s in owned_subscriptions(data, user["id"])]
    reminders = due_reminders(subs, user.get("settings", default_settings()))
    payload, status = send_reminder_email(data, user, reminders)
    return jsonify(payload), status


@app.get("/reports/subscriptions.csv")
@require_login
def export_csv():
    data = read_db()
    subs = [serialize_subscription(s, data) for s in owned_subscriptions(data, session["user_id"])]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Category", "Billing Cycle", "Cost", "Monthly Cost", "Annual Cost", "Next Renewal", "Status", "Notes"])
    for sub in subs:
        writer.writerow([
            sub["name"],
            sub["categoryName"],
            sub["cycle"],
            sub["cost"],
            sub["monthlyCost"],
            sub["annualCost"],
            sub["renewalDate"],
            sub["status"],
            sub.get("notes", ""),
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=subtrack-report.csv"},
    )


@app.get("/reports/print")
@require_login
def print_report():
    data = read_db()
    user = next(u for u in data["users"] if u["id"] == session["user_id"])
    dashboard_data = build_dashboard(data, user)
    subs = [serialize_subscription(s, data) for s in owned_subscriptions(data, user["id"])]
    currency = user.get("settings", default_settings()).get("currency", "PHP")
    return render_template(
        "report.html",
        user=user,
        subscriptions=subs,
        summary=dashboard_data,
        symbol=CURRENCY_SYMBOLS.get(currency, f"{currency} "),
        generated_at=datetime.now().strftime("%B %d, %Y"),
    )


if __name__ == "__main__":
    ensure_files()
    app.run(debug=True)
