from flask import Flask, request, jsonify, render_template
import psycopg2
import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
import datetime

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-secret")  
jwt = JWTManager(app)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        database=os.environ.get("POSTGRES_DB", "home_budget"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres")
    )
    return conn
    
    
    
    
def apply_monthly_payday(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Get current balance and last_payday
    cur.execute("SELECT balance, last_payday FROM users WHERE id = %s", (user_id,))
    result = cur.fetchone()
    balance, last_payday = result

    today = datetime.date.today()
    first_of_month = today.replace(day=1)

    # Apply payday if last_payday is None or before this month
    if not last_payday or last_payday < first_of_month:
        balance += 2000
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
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    hashed_pw = generate_password_hash(password)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "User registered successfully"}), 201


@app.route("/login", methods=["POST"])
def login():
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



@app.route("/categories")
def categories_page():
    return render_template("categories.html")


# API route (JWT required)
@app.route("/api/categories", methods=['POST'])
@jwt_required()
def api_create_category():
    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"error": "Name is required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "Category already exists"}), 400

    cur.execute("INSERT INTO categories (name) VALUES (%s) RETURNING id", (name,))
    category_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"id": category_id, "name": name}), 201


@app.route("/api/categories", methods=["GET"])
@jwt_required()
def api_get_categories():
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
    """Create an expense for a user with a category (balance can go negative)"""
    user_id = get_jwt_identity()
    data = request.get_json()
    amount = data.get("amount")
    description = data.get("description")
    category_id = data.get("categoryId")
    expense_date = data.get("date", str(datetime.date.today()))
    print("ADKLGHLKJHLKJHLKJIH")
    # Validate input
    if not all([amount, description, category_id]):
        return jsonify({"error": "Amount, description, and categoryId are required"}), 400

    # Convert amount to Decimal
    try:
        amount = Decimal(str(amount))
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a number"}), 400

    # Parse date
    try:
        expense_date = datetime.date.fromisoformat(expense_date)
    except ValueError:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Apply monthly payday first
        balance = apply_monthly_payday(user_id)  # should return Decimal

        # Check if category exists
        cur.execute("SELECT id, name FROM categories WHERE id = %s", (category_id,))
        cat = cur.fetchone()
        if not cat:
            return jsonify({"error": "Category not found"}), 404

        # Deduct expense from balance (can go negative)
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
        "amount": float(amount),  # convert for JSON
        "date": str(expense_date),
        "category": {"id": cat[0], "name": cat[1]},
        "balance": float(balance)
    }), 201

@app.route('/expenses', methods=['GET'])
@jwt_required()
def get_expenses():
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
    user_id = get_jwt_identity()

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get current user balance and last_payday
    cur.execute("SELECT balance, last_payday FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    balance = row[0] or 0
    last_payday = row[1]

    today = datetime.date.today()

    # Apply monthly payday if needed
    if not last_payday or last_payday.month < today.month or last_payday.year < today.year:
        balance += 2000
        cur.execute("UPDATE users SET balance = %s, last_payday = %s WHERE id = %s",
                    (balance, today.replace(day=1), user_id))
        conn.commit()

    cur.close()
    conn.close()

    return jsonify({
        "user_id": user_id,
        "balance": float(balance),
        "message": "You are authenticated!"
    })

# ---------- EXPENSES UPDATE ----------
@app.route('/expenses/<int:expense_id>', methods=['PUT'])
@jwt_required()
def update_expense(expense_id):
    """Update an existing expense (only description, amount, category, date)"""
    user_id = get_jwt_identity()
    data = request.get_json()

    amount = data.get("amount")
    description = data.get("description")
    category_id = data.get("categoryId")
    expense_date = data.get("date")

    # Validate at least one field is present
    if not any([amount, description, category_id, expense_date]):
        return jsonify({"error": "At least one field is required to update"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    # Make sure expense belongs to this user
    cur.execute("SELECT id FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        return jsonify({"error": "Expense not found"}), 404

    # Build update query dynamically
    fields, values = [], []
    if description:
        fields.append("description = %s")
        values.append(description)
    if amount:
        fields.append("amount = %s")
        values.append(amount)
    if category_id:
        fields.append("category_id = %s")
        values.append(category_id)
    if expense_date:
        try:
            expense_date = datetime.date.fromisoformat(expense_date)
        except ValueError:
            return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400
        fields.append("date = %s")
        values.append(expense_date)

    values.append(expense_id)
    values.append(user_id)

    cur.execute(
        f"UPDATE expenses SET {', '.join(fields)} WHERE id = %s AND user_id = %s RETURNING id",
        tuple(values)
    )
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not updated:
        return jsonify({"error": "Expense not found"}), 404

    return jsonify({"message": "Expense updated", "id": expense_id}), 200


# ---------- EXPENSES DELETE ----------
@app.route('/expenses/<int:expense_id>', methods=['DELETE'])
@jwt_required()
def delete_expense(expense_id):
    """Delete an expense"""
    user_id = get_jwt_identity()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s RETURNING id", (expense_id, user_id))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not deleted:
        return jsonify({"error": "Expense not found"}), 404

    return jsonify({"message": "Expense deleted", "id": expense_id}), 200
    
    
    
    
    
# ---------- DEFAULT ----------
@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


