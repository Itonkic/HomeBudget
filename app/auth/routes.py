from flask import request, jsonify
from app.auth import auth_bp
from app.utils import get_db_connection, validate_password
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from datetime import datetime

# Registration
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    errors = validate_password(password)
    if errors:
        return jsonify({"error": errors}), 400

    hashed_pw = generate_password_hash(password)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                return jsonify({"error": "Username already exists"}), 400
            cur.execute(
                "INSERT INTO users (username, password, balance, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
                (username, hashed_pw, 0, datetime.utcnow())
            )
            user_id = cur.fetchone()[0]
            conn.commit()

    return jsonify({"id": user_id, "username": username}), 201


# Login
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password FROM users WHERE username=%s", (username,))
            row = cur.fetchone()
            if not row or not check_password_hash(row[1], password):
                return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=username)
    return jsonify({"access_token": access_token})
