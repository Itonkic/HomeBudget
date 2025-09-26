from flask import Flask, request, jsonify, render_template, redirect
import psycopg2
import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
import datetime
from flasgger import Swagger
from psycopg2.errors import UniqueViolation
from functools import wraps
import re
from datetime import date




app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-secret")  
swagger = Swagger(app, template={
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header using the Bearer scheme. Example: 'Bearer {token}'"
        }
    }
})
jwt = JWTManager(app)





PASSWORD_RULES = {
    "min_length": 8,
    "uppercase": True,
    "lowercase": True,
    "digit": True,
    "special_char": True
}

def validate_password(password: str):
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

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        database=os.environ.get("POSTGRES_DB", "home_budget"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres")
    )
    return conn
    

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user = get_jwt_identity()  # this is the username from the token
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM tba_sio WHERE key = %s", (current_user,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row or row[0] != 1:
            return jsonify({"error": "Access denied. Admin rights required."}), 403

        return fn(*args, **kwargs)
    return wrapper
    
    
def apply_monthly_payday(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT balance, last_payday, salary FROM users WHERE id = %s", (user_id,))
    result = cur.fetchone()
    if not result:
        cur.close()
        conn.close()
        return None  # user not found
    cur.execute("SELECT key, value FROM tba_sio WHERE key IN ('Rent')")
    sio_values = dict(cur.fetchall())


    rent = sio_values.get("Rent", 0)
    
    cur.execute("SELECT count(distinct(username)) FROM public.users")
    usercount = cur.fetchone()[0]  
    rent = rent / usercount
    balance, last_payday, salary = result
    today = datetime.date.today()

    # Convert last_payday to date if it's datetime
    if last_payday and isinstance(last_payday, datetime.datetime):
        last_payday = last_payday.date()

    # Apply salary only if last_payday is None or not in current month/year
    if not last_payday or (last_payday.year < today.year or last_payday.month < today.month):
        balance += salary
        balance -= rent
        cur.execute(
            "UPDATE users SET balance = %s, last_payday = %s WHERE id = %s",
            (balance, today, user_id)
        )
        conn.commit()

    cur.close()
    conn.close()
    return balance

# ---------- AUTH ROUTES ----------



@app.route("/register", methods=["POST"])
def register():
    """
    Register a new user
    ---
    tags:
      - Auth
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
              example: john_doe
            password:
              type: string
              example: MyPassword123!
    responses:
      201:
        description: User registered successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: User registered successfully
            initial_balance:
              type: integer
              example: 2000
      400:
        description: Bad request (missing fields, username exists, or weak password)
        schema:
          type: object
          properties:
            error:
              type: string
              example: Password does not meet requirements
            details:
              type: array
              items:
                type: string
              example:
                - Must be at least 8 characters long.
                - Must contain at least one uppercase letter.
                - Must contain at least one lowercase letter.
                - Must contain at least one digit.
                - Must contain at least one special character (!@#$%^&* etc.).
            password_rules:
              type: object
              properties:
                min_length:
                  type: integer
                  example: 8
                uppercase:
                  type: boolean
                  example: true
                lowercase:
                  type: boolean
                  example: true
                digit:
                  type: boolean
                  example: true
                special_char:
                  type: boolean
                  example: true
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Database error
    """

    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    MONTHLY_INCOME = 2000

    if not username or not password:
        return jsonify({
            "error": "Missing username or password",
            "password_rules": PASSWORD_RULES
        }), 400

    # Validate password strength
    password_errors = validate_password(password)
    if password_errors:
        return jsonify({
            "error": "Password does not meet requirements",
            "details": password_errors,
            "password_rules": PASSWORD_RULES
        }), 400

    hashed_pw = generate_password_hash(password)
    today = date.today()
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Check if user already exists
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            return jsonify({"error": "Username already exists"}), 400

        # Insert new user with initial balance
        cur.execute(
            "INSERT INTO users (username, password, balance, salary, last_payday) VALUES (%s, %s, %s, %s, %s)",
            (username, hashed_pw, MONTHLY_INCOME, MONTHLY_INCOME, today)
        )
        conn.commit()

        # Check if this is the first user
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        if total_users == 1:
            cur.execute("INSERT INTO TBA_SIO (key, value) VALUES (%s, %s)", (username, 1))
            conn.commit()

    except UniqueViolation:
        conn.rollback()
        return jsonify({"error": "Username already exists"}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({
        "message": "User registered successfully",
        "initial_balance": MONTHLY_INCOME
    }), 201



@app.route("/login", methods=["POST"])
def login():
    """
    User login
    ---
    tags:
      - Auth
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
              example: alice
            password:
              type: string
              example: mypassword
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            access_token:
              type: string
      400:
        description: Missing username or password
      401:
        description: Invalid credentials
    """

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and check_password_hash(user[1], password):
        access_token = create_access_token(identity=str(user[0]), expires_delta=datetime.timedelta(hours=1))
        return jsonify({"access_token": access_token}), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401





@app.route("/api/categories", methods=['POST'])
@jwt_required()
def api_create_category():
    """
    Create a new category
    ---
    tags:
      - Categories
    security:
      - Bearer: []
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
            - name
          properties:
            name:
              type: string
              example: "Groceries"
    responses:
      201:
        description: Category created successfully
        schema:
          type: object
          properties:
            id:
              type: integer
              example: 1
            name:
              type: string
              example: "Groceries"
      400:
        description: Bad request (missing name or category exists)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Category already exists"
    """

    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"error": "Name is required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Check if category already exists
        cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
        if cur.fetchone():
            return jsonify({"error": "Category already exists"}), 400

        # Ensure sequence is in sync
        cur.execute(
            "SELECT setval('categories_id_seq', COALESCE((SELECT MAX(id) FROM categories), 0))"
        )

        # Insert new category
        cur.execute("INSERT INTO categories (name) VALUES (%s) RETURNING id", (name,))
        category_id = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return jsonify({"id": category_id, "name": name}), 201


@app.route("/api/categories", methods=["GET"])
@jwt_required()
def api_get_categories():
    """
    Get all categories
    ---
    tags:
      - Categories
    security:
      - Bearer: []
    produces:
      - application/json
    responses:
      200:
        description: List of all categories
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                example: 1
              name:
                type: string
                example: "Groceries"
      401:
        description: Unauthorized (JWT missing or invalid)
        schema:
          type: object
          properties:
            msg:
              type: string
              example: "Missing Authorization Header"
    """

    """Get all global categories"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(categories)

@app.route('/categories/<int:id>', methods=['PUT'])
@jwt_required()
def update_category(id):
    """
    Update a category
    ---
    tags:
      - Categories
    security:
      - Bearer: []
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: ID of the category to update
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
              example: "Updated Category Name"
    responses:
      200:
        description: Category updated successfully
        schema:
          type: object
          properties:
            id:
              type: integer
              example: 1
            name:
              type: string
              example: "Updated Category Name"
      400:
        description: Bad request (missing name)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Name is required"
      404:
        description: Category not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Category not found"
      401:
        description: Unauthorized (JWT missing or invalid)
        schema:
          type: object
          properties:
            msg:
              type: string
              example: "Missing Authorization Header"
    """

    """Update global category name"""
    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"error": "Name is required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE categories SET name = %s WHERE id = %s RETURNING id", (name, id))
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        return jsonify({"error": "Category not found"}), 404

    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"id": id, "name": name})

@app.route('/categories/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_category(id):
    """
    Delete a category
    ---
    tags:
      - Categories
    security:
      - Bearer: []
    produces:
      - application/json
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: ID of the category to delete
    responses:
      200:
        description: Category deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Category deleted"
      404:
        description: Category not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Category not found"
      401:
        description: Unauthorized (JWT missing or invalid)
        schema:
          type: object
          properties:
            msg:
              type: string
              example: "Missing Authorization Header"
    """

    """Delete a global category"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM categories WHERE id = %s RETURNING id", (id,))
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        return jsonify({"error": "Category not found"}), 404
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Category deleted"})
    
    
    
from decimal import Decimal

@app.route('/expenses', methods=['POST'])
@jwt_required()
def create_expense():
    """
    Create a new expense (updates user balance)
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
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
            - amount
            - description
            - categoryId
          properties:
            amount:
              type: number
              format: float
              example: 25.50
            description:
              type: string
              example: "Lunch at restaurant"
            categoryId:
              type: integer
              example: 1
            date:
              type: string
              format: date
              example: "2025-09-24"
    responses:
      201:
        description: Expense created successfully (balance updated)
        schema:
          type: object
          properties:
            id:
              type: integer
              example: 10
            description:
              type: string
              example: "Lunch at restaurant"
            amount:
              type: number
              format: float
              example: 25.50
            date:
              type: string
              format: date
              example: "2025-09-24"
            category:
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                name:
                  type: string
                  example: "Food"
            balance:
              type: number
              format: float
              example: 1974.50
      400:
        description: Bad request (missing fields or invalid values)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Amount, description, and categoryId are required"
      404:
        description: Category not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Category not found"
      401:
        description: Unauthorized (JWT missing or invalid)
        schema:
          type: object
          properties:
            msg:
              type: string
              example: "Missing Authorization Header"
    """

    """Create an expense and update user's balance"""
    user_id = get_jwt_identity()
    data = request.get_json()

    amount = data.get("amount")
    description = data.get("description")
    category_id = data.get("categoryId")
    expense_date = data.get("date", str(datetime.date.today()))

    if not all([amount, description, category_id]):
        return jsonify({"error": "Amount, description, and categoryId are required"}), 400

    try:
        amount = Decimal(str(amount))
    except:
        return jsonify({"error": "Amount must be a number"}), 400

    try:
        expense_date = datetime.date.fromisoformat(expense_date)
    except:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Check category exists
        cur.execute("SELECT id, name FROM categories WHERE id = %s", (category_id,))
        cat = cur.fetchone()
        if not cat:
            return jsonify({"error": "Category not found"}), 404

        # Deduct expense from balance
        cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
        balance = Decimal(cur.fetchone()[0] or 0)
        balance -= amount
        cur.execute("UPDATE users SET balance = %s WHERE id = %s", (balance, user_id))

        # Insert expense
        cur.execute(
            "INSERT INTO expenses (description, amount, category_id, user_id, date) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (description, amount, category_id, user_id, expense_date)
        )
        expense_id = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return jsonify({
        "id": expense_id,
        "description": description,
        "amount": float(amount),
        "date": str(expense_date),
        "category": {"id": cat[0], "name": cat[1]},
        "balance": float(balance)
    }), 201

@app.route('/expenses', methods=['GET'])
@jwt_required()
def get_expenses():
    """
    Get user expenses
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    produces:
      - application/json
    parameters:
      - name: categoryId
        in: query
        type: integer
        required: false
        description: Filter by category ID
        example: 1
      - name: minAmount
        in: query
        type: number
        format: float
        required: false
        description: Minimum expense amount
        example: 10.5
      - name: maxAmount
        in: query
        type: number
        format: float
        required: false
        description: Maximum expense amount
        example: 100
      - name: startDate
        in: query
        type: string
        format: date
        required: false
        description: Start date for filtering (YYYY-MM-DD)
        example: "2025-01-01"
      - name: endDate
        in: query
        type: string
        format: date
        required: false
        description: End date for filtering (YYYY-MM-DD)
        example: "2025-12-31"
    responses:
      200:
        description: List of expenses
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                example: 10
              description:
                type: string
                example: "Lunch at restaurant"
              amount:
                type: number
                format: float
                example: 25.50
              date:
                type: string
                format: date
                example: "2025-09-24"
              category:
                type: object
                properties:
                  id:
                    type: integer
                    example: 1
                  name:
                    type: string
                    example: "Food"
      401:
        description: Unauthorized (JWT missing or invalid)
        schema:
          type: object
          properties:
            msg:
              type: string
              example: "Missing Authorization Header"
    """

    user_id = get_jwt_identity()
    
    # Convert and validate parameters
    category_id = request.args.get('categoryId', type=int)
    min_amount = request.args.get('minAmount', type=float)
    max_amount = request.args.get('maxAmount', type=float)
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')

    query = """
        SELECT e.id, e.description, e.amount, e.date, c.id, c.name
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s
    """
    params = [user_id]

    if category_id is not None:
        query += " AND e.category_id = %s"
        params.append(category_id)
    if min_amount is not None:
        query += " AND e.amount >= %s"
        params.append(min_amount)
    if max_amount is not None:
        query += " AND e.amount <= %s"
        params.append(max_amount)
    if start_date:
        query += " AND e.date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND e.date <= %s"
        params.append(end_date)

    query += " ORDER BY e.date DESC"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, tuple(params))
    expenses = [{
        "id": r[0], "description": r[1], "amount": float(r[2]),
        "date": r[3].isoformat(), "category": {"id": r[4], "name": r[5]}
    } for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(expenses)

@app.route("/me", methods=["GET"])
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

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT salary FROM users WHERE id = %s", (user_id,))
    salary = float(cur.fetchone()[0])
    cur.close()
    conn.close()

    return jsonify({
        "user_id": user_id,
        "balance": float(balance),
        "salary": salary,
        "message": "You are authenticated!"
    })
    

# ---------- EXPENSES UPDATE ----------
@app.route('/expenses/<int:expense_id>', methods=['PUT'])
@jwt_required()
def update_expense(expense_id):
    """
    Update an existing expense (updates user balance)
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - name: expense_id
        in: path
        type: integer
        required: true
        description: ID of the expense to update
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            amount:
              type: number
              format: float
              example: 30.0
            description:
              type: string
              example: "Dinner at restaurant"
            categoryId:
              type: integer
              example: 2
            date:
              type: string
              format: date
              example: "2025-09-24"
          description: At least one field must be provided
    responses:
      200:
        description: Expense updated successfully (balance updated)
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Expense updated"
            id:
              type: integer
              example: 10
            balance:
              type: number
              format: float
              example: 1975.00
      400:
        description: Bad request (no fields provided or invalid date)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "At least one field is required to update"
      404:
        description: Expense not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Expense not found"
      401:
        description: Unauthorized (JWT missing or invalid)
        schema:
          type: object
          properties:
            msg:
              type: string
              example: "Missing Authorization Header"
    """

    """Update an expense and adjust user's balance"""
    user_id = get_jwt_identity()
    data = request.get_json()

    amount = data.get("amount")
    description = data.get("description")
    category_id = data.get("categoryId")
    expense_date = data.get("date")

    if not any([amount, description, category_id, expense_date]):
        return jsonify({"error": "At least one field is required to update"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch existing expense
    cur.execute("SELECT amount FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"error": "Expense not found"}), 404

    old_amount = Decimal(row[0])

    # Build update query
    fields, values = [], []
    if description:
        fields.append("description = %s")
        values.append(description)
    if amount:
        try:
            amount = Decimal(str(amount))
        except:
            return jsonify({"error": "Amount must be a number"}), 400
        fields.append("amount = %s")
        values.append(amount)
    if category_id:
        fields.append("category_id = %s")
        values.append(category_id)
    if expense_date:
        try:
            expense_date = datetime.date.fromisoformat(expense_date)
        except:
            return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400
        fields.append("date = %s")
        values.append(expense_date)

    values.extend([expense_id, user_id])
    cur.execute(
        f"UPDATE expenses SET {', '.join(fields)} WHERE id = %s AND user_id = %s RETURNING id",
        tuple(values)
    )
    updated = cur.fetchone()
    if not updated:
        cur.close()
        conn.close()
        return jsonify({"error": "Expense not found"}), 404

    # Adjust user's balance
    if amount is not None:
        cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
        balance = Decimal(cur.fetchone()[0] or 0)
        balance = balance + old_amount - amount
        cur.execute("UPDATE users SET balance = %s WHERE id = %s", (balance, user_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Expense updated", "id": expense_id}), 200

# ---------- EXPENSES DELETE ----------
@app.route('/expenses/<int:expense_id>', methods=['DELETE'])
@jwt_required()
def delete_expense(expense_id):
    """
    Delete an expense (updates user balance)
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    produces:
      - application/json
    parameters:
      - name: expense_id
        in: path
        type: integer
        required: true
        description: ID of the expense to delete
    responses:
      200:
        description: Expense deleted successfully (balance updated)
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Expense deleted"
            id:
              type: integer
              example: 10
            balance:
              type: number
              format: float
              example: 2000.00
      404:
        description: Expense not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Expense not found"
      401:
        description: Unauthorized (JWT missing or invalid)
        schema:
          type: object
          properties:
            msg:
              type: string
              example: "Missing Authorization Header"
    """

    """Delete an expense and restore user's balance"""
    user_id = get_jwt_identity()

    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch amount before deletion
    cur.execute("SELECT amount FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"error": "Expense not found"}), 404

    amount = Decimal(row[0])

    # Delete expense
    cur.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s RETURNING id", (expense_id, user_id))
    deleted = cur.fetchone()
    if not deleted:
        cur.close()
        conn.close()
        return jsonify({"error": "Expense not found"}), 404

    # Restore user's balance
    cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
    balance = Decimal(cur.fetchone()[0] or 0)
    balance += amount
    cur.execute("UPDATE users SET balance = %s WHERE id = %s", (balance, user_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Expense deleted", "id": expense_id, "balance": float(balance)}), 200
    
    
@app.route('/aggregation', methods=['GET'])
@jwt_required()
def aggregation():
    """
    Aggregate user finances over a given period based on expenses & categories
    ---
    tags:
      - Aggregation
    security:
      - Bearer: []
    produces:
      - application/json
    parameters:
      - name: period
        in: query
        type: string
        enum: [month, quarter, year]
        required: false
        default: month
        description: "Period to aggregate (month, quarter, or year). Defaults to month."
    responses:
      200:
        description: Aggregated user finances and KPIs
    """
    user_id = get_jwt_identity()
    period = request.args.get("period", "month")
    today = datetime.date.today()

    # ---- Period range ----
    if period == "month":
        start_date = today.replace(day=1)
    elif period == "quarter":
        quarter = (today.month - 1) // 3 + 1
        start_month = 3 * (quarter - 1) + 1
        start_date = datetime.date(today.year, start_month, 1)
    elif period == "year":
        start_date = datetime.date(today.year, 1, 1)
    else:
        return jsonify({"error": "Invalid period, use month|quarter|year"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    # ---- Get income (earned) ----
    cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
    user_balance = float(cur.fetchone()[0] or 0)

    # ---- Get expenses by category ----
    cur.execute("""
        SELECT c.name, COALESCE(SUM(e.amount),0) 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s AND e.date >= %s AND e.date <= %s
        GROUP BY c.name
    """, (user_id, start_date, today))
    expenses_by_category = {row[0]: float(row[1]) for row in cur.fetchall()}

    # ---- Totals ----
    spent = sum(expenses_by_category.values())
    earned = user_balance + spent  # optional: if you track paydays elsewhere, adjust this

    # ---- KPI mappings ----
    housing = expenses_by_category.get("Rent / Mortgage", 0)
    utilities = expenses_by_category.get("Utilities", 0)
    insurance = expenses_by_category.get("Insurance", 0)
    subscriptions = expenses_by_category.get("Subscriptions", 0)

    health_edu = expenses_by_category.get("Health / Medical", 0) + expenses_by_category.get("Education / Courses", 0)
    discretionary = expenses_by_category.get("Entertainment", 0) + expenses_by_category.get("Dining Out", 0) + expenses_by_category.get("Travel / Vacation", 0)
    debt = expenses_by_category.get("Debt Payments", 0) if "Debt Payments" in expenses_by_category else 0
    fun = expenses_by_category.get("Entertainment", 0)

    # ---- KPIs ----
    savings = earned - spent
    savings_rate = (savings / earned * 100) if earned else 0
    fixed_expenses = housing + utilities + insurance + subscriptions
    fixed_expense_ratio = (fixed_expenses / earned * 100) if earned else 0
    debt_to_income = (debt / earned * 100) if earned else 0
    discretionary_ratio = (discretionary / earned * 100) if earned else 0
    housing_cost_ratio = (housing / earned * 100) if earned else 0
    health_edu_ratio = (health_edu / earned * 100) if earned else 0
    fun_ratio = (fun / earned * 100) if earned else 0

    cur.close()
    conn.close()

    return jsonify({
        "period": period,
        "start_date": str(start_date),
        "end_date": str(today),
        "earned": earned,
        "spent": spent,
        "balance": earned - spent,
        "expenses_by_category": expenses_by_category,
        "kpis": {
            "savings": savings,
            "savings_rate_percent": round(savings_rate, 2),
            "fixed_expense_ratio_percent": round(fixed_expense_ratio, 2),
            "debt_to_income_percent": round(debt_to_income, 2),
            "discretionary_ratio_percent": round(discretionary_ratio, 2),
            "housing_cost_ratio_percent": round(housing_cost_ratio, 2),
            "health_education_ratio_percent": round(health_edu_ratio, 2),
            "fun_ratio_percent": round(fun_ratio, 2)
        }
    })


# ---------- USERS CRUD ----------
@app.route("/api/users", methods=["GET"])
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    cur.close()
    conn.close()
    return jsonify(users)


@app.route("/api/users/<int:user_id>", methods=["GET"])
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
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, balance, created_at, last_payday FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "id": row[0],
        "username": row[1],
        "balance": float(row[2]) if row[2] else 0,
        "created_at": row[3].isoformat() if row[3] else None,
        "last_payday": row[4].isoformat() if row[4] else None
    })


@app.route("/api/users/<int:user_id>", methods=["PUT"])
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
            last_payday = datetime.date.fromisoformat(data["last_payday"])
            fields.append("last_payday = %s")
            values.append(last_payday)
        except:
            return jsonify({"error": "Invalid date format (use YYYY-MM-DD)"}), 400

    if not fields:
        return jsonify({"error": "No valid fields provided"}), 400

    values.append(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE id = %s RETURNING id",
        tuple(values)
    )
    updated = cur.fetchone()
    if not updated:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": "User not found"}), 404

    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "User updated", "id": user_id})


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
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



# ---------- DEFAULT ----------
@app.route("/")
def index():
    return redirect("/apidocs")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


