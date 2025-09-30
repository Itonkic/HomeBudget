from flask import request, jsonify, Blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from datetime import datetime
from app.utils import get_db_connection, validate_password  # absolute import

auth_bp = Blueprint("auth", __name__, template_folder='../templates')


# Registration
@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user
    ---
    tags:
      - Authentication
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - password
            - email
          properties:
            username:
              type: string
              example: "john_doe"
            password:
              type: string
              example: "StrongP@ssw0rd"
            email:
              type: string
              example: "test@example.com"
    responses:
      201:
        description: User registered successfully
        schema:
          type: object
          properties:
            id:
              type: integer
              example: 1
            username:
              type: string
              example: "john_doe"
      400:
        description: Bad request (missing fields or username exists)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Username already exists or password invalid"
    """
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")

    if not username or not password or not email:
        return jsonify({"error": "Username, password, and email are required"}), 400

    # Optional: add basic email validation
    if "@" not in email:
        return jsonify({"error": "Invalid email address"}), 400

    errors = validate_password(password)
    if errors:
        return jsonify({"error": errors}), 400

    hashed_pw = generate_password_hash(password)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if username exists
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                return jsonify({"error": "Username already exists"}), 400

            # Check if email exists
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return jsonify({"error": "Email already exists"}), 400

            # Insert user with email
            cur.execute(
                """
                INSERT INTO users (username, password, email, balance, created_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (username, hashed_pw, email, 0, datetime.utcnow())
            )
            user_id = cur.fetchone()[0]
            conn.commit()

    return jsonify({"id": user_id, "username": username, "email": email}), 201


# Login
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login a user
    ---
    tags:
      - Authentication
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - password
          properties:
            username:
              type: string
              example: "john_doe"
            password:
              type: string
              example: "StrongP@ssw0rd"
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            access_token:
              type: string
              example: "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
      400:
        description: Bad request (missing fields)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Username and password required"
      401:
        description: Unauthorized (invalid credentials)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Invalid credentials"
    """
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
