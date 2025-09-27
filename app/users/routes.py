from flask import request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta, datetime
import random, string

from . import users_bp  # import the blueprint
from ..db import get_db_connection  # adjust import to your DB helper
from ..utils import validate_password, apply_monthly_payday, send_email  # adjust imports
from ..config import PASSWORD_RULES



@users_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """
    Get authenticated user info (current balance includes all expenses)
    ---
    tags:
      - Users
    security:
      - Bearer: []
    produces:
      - application/json
    responses:
      200:
        description: Returns current user balance, reflecting all recorded expenses, and a placeholder value
        schema:
          type: object
          properties:
            user_id:
              type: integer
              example: 1
            balance:
              type: number
              format: float
              example: 1974.50  # updated to reflect deductions from recorded expenses
            placeholder_value:
              type: number
              format: float
              example: 0.0
            message:
              type: string
              example: "You are authenticated!"
      401:
        description: Unauthorized (JWT missing or invalid)
        schema:
          type: object
          properties:
            msg:
              type: string
              example: "Missing Authorization Header"
    """
  
    """Get authenticated user info with balance and placeholder value, applying monthly payday"""
    user_id = get_jwt_identity()

    # Apply monthly payday
    balance = apply_monthly_payday(user_id)
    if balance is None:
        return jsonify({"error": "User not found"}), 404

    # Use context managers to safely handle DB connection and cursor
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT salary FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "User not found"}), 404
            salary = float(row[0])

    return jsonify({
        "user_id": user_id,
        "balance": float(balance),
        "salary": salary,
        "message": "You are authenticated!"
    })
 
@users_bp.route("/request-password-reset", methods=["POST"])
def request_password_reset():
    """
    Request a password reset code
    ---
    tags:
      - Authentication
    produces:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              format: email
              example: "user@example.com"
              description: Email of the user requesting a password reset
    responses:
      200:
        description: Reset code sent successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Reset code sent to your email"
      400:
        description: Email not provided
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Email required"
      404:
        description: Email not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Email not found"
    """

    data = request.get_json() or {}
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email required"}), 400

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if user exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user:
                return jsonify({"error": "Email not found"}), 404

            # Generate a 6-digit code
            code = ''.join(random.choices(string.digits, k=6))
            expires_at = datetime.utcnow() + timedelta(minutes=10)

            # Store code in password_resets table
            cur.execute("""
                INSERT INTO password_resets (email, code, expires_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE
                SET code = EXCLUDED.code, expires_at = EXCLUDED.expires_at, created_at = CURRENT_TIMESTAMP
            """, (email, code, expires_at))

            conn.commit()

    # Send email with code
    send_email(email, "Password Reset Code", f"Your password reset code is: {code}")

    return jsonify({"message": "Reset code sent to your email"}), 200

@users_bp.route("/verify-reset-code", methods=["POST"])
def verify_reset_code():
    """
    Verify password reset code and set new password
    ---
    tags:
      - Authentication
    produces:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              format: email
              example: "user@example.com"
              description: Email of the user
            code:
              type: string
              example: "123456"
              description: 6-digit password reset code sent via email
            new_password:
              type: string
              example: "NewStrongPass123!"
              description: New password for the user
    responses:
      200:
        description: Password reset successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Password reset successfully"
      400:
        description: Bad request due to missing fields, invalid code, expired code, or password strength issues
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Reset code expired"
            details:
              type: array
              items:
                type: string
              example: ["Password must contain at least one uppercase letter"]
            password_rules:
              type: array
              items:
                type: string
              example: ["Minimum 8 characters", "At least 1 uppercase letter", "At least 1 number"]
    """

    data = request.get_json() or {}
    email = data.get("email")
    code = data.get("code")
    new_password = data.get("new_password")

    if not email or not code or not new_password:
        return jsonify({"error": "Email, code, and new_password are required"}), 400

    # Validate password strength
    password_errors = validate_password(new_password)
    if password_errors:
        return jsonify({
            "error": "Password does not meet requirements",
            "details": password_errors,
            "password_rules": PASSWORD_RULES
        }), 400

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Fetch reset code from DB
            cur.execute("""
                SELECT code, expires_at 
                FROM password_resets 
                WHERE email = %s
            """, (email,))
            entry = cur.fetchone()

            if not entry:
                return jsonify({"error": "No reset request found"}), 400

            stored_code, expires_at = entry

            if datetime.utcnow() > expires_at:
                return jsonify({"error": "Reset code expired"}), 400

            if stored_code != code:
                return jsonify({"error": "Invalid reset code"}), 400

            # Update user password
            hashed_pw = generate_password_hash(new_password)
            cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_pw, email))

            # Delete used reset code
            cur.execute("DELETE FROM password_resets WHERE email = %s", (email,))

            conn.commit()

    return jsonify({"message": "Password reset successfully"}), 200




@users_bp.route("", methods=["GET"])
@jwt_required()
@admin_required
def get_users():
    """
    Get all users
    ---
    tags:
      - Users
    security:
      - Bearer: []
    produces:
      - application/json
    responses:
      200:
        description: List of all users
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                example: 1
              username:
                type: string
                example: "admin"
              balance:
                type: number
                example: 100.5
              created_at:
                type: string
                example: "2025-09-26T12:00:00"
              last_payday:
                type: string
                example: "2025-09-20"
      401:
        description: Unauthorized (JWT missing or invalid)
      403:
        description: Access denied (requires admin rights)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, balance, created_at, last_payday FROM users ORDER BY id")
            users = [
                {
                    "id": row[0],
                    "username": row[1],
                    "balance": float(row[2]) if row[2] is not None else 0,
                    "created_at": row[3].isoformat() if row[3] else None,
                    "last_payday": row[4].isoformat() if row[4] else None
                }
                for row in cur.fetchall()
            ]

    return jsonify(users)

@users_bp.route("/<int:user_id>", methods=["GET"])
@jwt_required()
@admin_required
def get_user(user_id):
    """
    Get a user by ID
    ---
    tags:
      - Users
    security:
      - Bearer: []
    produces:
      - application/json
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: ID of the user to fetch
    responses:
      200:
        description: User object
        schema:
          type: object
          properties:
            id:
              type: integer
              example: 1
            username:
              type: string
              example: "admin"
            balance:
              type: number
              example: 100.5
            created_at:
              type: string
              example: "2025-09-26T12:00:00"
            last_payday:
              type: string
              example: "2025-09-20"
      401:
        description: Unauthorized (JWT missing or invalid)
      403:
        description: Access denied (requires admin rights)
      404:
        description: User not found
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, balance, created_at, last_payday FROM users WHERE id = %s",
                (user_id,)
            )
            row = cur.fetchone()

    if not row:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": row[0],
        "username": row[1],
        "balance": float(row[2]) if row[2] else 0,
        "created_at": row[3].isoformat() if row[3] else None,
        "last_payday": row[4].isoformat() if row[4] else None
    })

@users_bp.route("/<int:user_id>", methods=["PUT"])
@jwt_required()
@admin_required
def update_user(user_id):
    """
    Update user details (balance, password, last_payday)
    ---
    tags:
      - Users
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: ID of the user to update
      - in: body
        name: body
        schema:
          type: object
          properties:
            balance:
              type: number
              example: 200.75
            password:
              type: string
              example: "new_secure_password"
            last_payday:
              type: string
              example: "2025-09-21"
    responses:
      200:
        description: User updated successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "User updated"
            id:
              type: integer
              example: 1
      400:
        description: Invalid input (bad date format or empty body)
      401:
        description: Unauthorized (JWT missing or invalid)
      403:
        description: Access denied (requires admin rights)
      404:
        description: User not found
    """
    data = request.get_json() or {}
    fields, values = [], []

    if "balance" in data:
        fields.append("balance = %s")
        values.append(data["balance"])

    if "password" in data:
        hashed_pw = generate_password_hash(data["password"])
        fields.append("password = %s")
        values.append(hashed_pw)

    if "last_payday" in data:
        try:
            last_payday = date.fromisoformat(data["last_payday"])
            fields.append("last_payday = %s")
            values.append(last_payday)
        except ValueError:
            return jsonify({"error": "Invalid date format (use YYYY-MM-DD)"}), 400

    if not fields:
        return jsonify({"error": "No valid fields provided"}), 400

    values.append(user_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = %s RETURNING id",
                tuple(values)
            )
            updated = cur.fetchone()
            if not updated:
                conn.rollback()
                return jsonify({"error": "User not found"}), 404

        conn.commit()

    return jsonify({"message": "User updated", "id": user_id})

@users_bp.route("/<int:user_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_user(user_id):
    """
    Delete a user by ID
    ---
    tags:
      - Users
    security:
      - Bearer: []
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: ID of the user to delete
    responses:
      200:
        description: User deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "User deleted"
            id:
              type: integer
              example: 1
      401:
        description: Unauthorized (JWT missing or invalid)
      403:
        description: Access denied (requires admin rights)
      404:
        description: User not found
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
    deleted = cur.fetchone()
    if not deleted:
        cur.close()
        conn.close()
        return jsonify({"error": "User not found"}), 404
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "User deleted", "id": user_id})
