# app/utils.py

import re
import os
import psycopg2
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
import smtplib
from email.mime.text import MIMEText
from datetime import date, datetime

# ----------------- PASSWORD VALIDATION -----------------
PASSWORD_RULES = {
    "min_length": 8,
    "uppercase": True,
    "lowercase": True,
    "digit": True,
    "special_char": True
}

def validate_password(password: str):
    """
    Validates a password against defined rules.
    Returns a list of errors (empty if valid).
    """
    errors = []
    if len(password) < PASSWORD_RULES["min_length"]:
        errors.append(f"Must be at least {PASSWORD_RULES['min_length']} characters long.")
    if PASSWORD_RULES["uppercase"] and not re.search(r"[A-Z]", password):
        errors.append("Must contain at least one uppercase letter.")
    if PASSWORD_RULES["lowercase"] and not re.search(r"[a-z]", password):
        errors.append("Must contain at least one lowercase letter.")
    if PASSWORD_RULES["digit"] and not re.search(r"\d", password):
        errors.append("Must contain at least one digit.")
    if PASSWORD_RULES["special_char"] and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Must contain at least one special character (!@#$%^&* etc.).")
    return errors

# ----------------- DATABASE CONNECTION -----------------
def get_db_connection():
    """
    Creates and returns a new PostgreSQL database connection.
    """
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        database=os.environ.get("POSTGRES_DB", "home_budget"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres")
    )

# ----------------- ADMIN DECORATOR -----------------
def admin_required(fn):
    """
    Flask decorator to check if current JWT user is admin.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user = get_jwt_identity()
        from app.utils import get_db_connection  # avoid circular import
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM tba_sio WHERE key = %s", (current_user,))
                row = cur.fetchone()
        if not row or row[0] != 1:
            return jsonify({"error": "Access denied. Admin rights required."}), 403
        return fn(*args, **kwargs)
    return wrapper

# ----------------- EMAIL SENDING -----------------
def send_email(to_email, subject, message):
    """
    Sends an email using SMTP configuration from environment variables.
    """
    from_email = os.environ.get("EMAIL_USER", "example@example.com")
    smtp_server = os.environ.get("EMAIL_HOST", "localhost")
    smtp_port = int(os.environ.get("EMAIL_PORT", 1025))
    smtp_username = os.environ.get("EMAIL_USER", from_email)
    smtp_password = os.environ.get("EMAIL_PASS", "")

    msg = MIMEText(message, 'plain')
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_password:
                server.starttls()
                server.login(smtp_username, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

# ----------------- MONTHLY PAYDAY -----------------
def apply_monthly_payday(user_id):
    """
    Applies monthly salary to user balance and subtracts proportional rent.
    Updates last_payday in database.
    """
    from app.utils import get_db_connection  # avoid circular import
    today = date.today()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get user data
            cur.execute("SELECT balance, last_payday, salary FROM users WHERE id = %s", (user_id,))
            result = cur.fetchone()
            if not result:
                return None

            balance, last_payday, salary = result

            # Get rent
            cur.execute("SELECT key, value FROM tba_sio WHERE key='Rent'")
            sio_values = dict(cur.fetchall())
            rent = sio_values.get("Rent", 0)

            # Calculate per-user rent
            cur.execute("SELECT COUNT(DISTINCT username) FROM users")
            usercount = cur.fetchone()[0]
            rent = rent / usercount if usercount else 0

            # Convert last_payday to date if needed
            if last_payday and isinstance(last_payday, datetime):
                last_payday = last_payday.date()

            # Apply payday if not already applied this month
            if not last_payday or (last_payday.year < today.year or last_payday.month < today.month):
                balance += salary
                balance -= rent
                cur.execute("UPDATE users SET balance=%s, last_payday=%s WHERE id=%s",
                            (balance, today, user_id))
                conn.commit()
    return balance
