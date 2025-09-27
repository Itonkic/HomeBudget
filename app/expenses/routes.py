from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal
from datetime import date
from ..db import get_db_connection  # helper function from app package
from . import expenses_bp

@expenses_bp.route("", methods=["POST"])
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
    expense_date = data.get("date", str(date.today()))

    if not all([amount, description, category_id]):
        return jsonify({"error": "Amount, description, and categoryId are required"}), 400

    try:
        amount = Decimal(str(amount))
    except:
        return jsonify({"error": "Amount must be a number"}), 400

    try:
        expense_date = date.fromisoformat(expense_date)
    except:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    with get_db_connection() as conn:
        with conn.cursor() as cur:
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

    return jsonify({
        "id": expense_id,
        "description": description,
        "amount": float(amount),
        "date": str(expense_date),
        "category": {"id": cat[0], "name": cat[1]},
        "balance": float(balance)
    }), 201

@expenses_bp.route("", methods=["GET"])
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

    # Using context managers
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            expenses = [{
                "id": r[0],
                "description": r[1],
                "amount": float(r[2]),
                "date": r[3].isoformat(),
                "category": {"id": r[4], "name": r[5]}
            } for r in cur.fetchall()]

    return jsonify(expenses)

 
# ---------- EXPENSES ROUTES ----------
@expenses_bp.route("/<int:expense_id>", methods=["PUT"])
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

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Fetch existing expense
            cur.execute(
                "SELECT amount FROM expenses WHERE id = %s AND user_id = %s",
                (expense_id, user_id)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Expense not found"}), 404

            old_amount = Decimal(row[0])

            # Build update query
            fields, values = [], []
            if description:
                fields.append("description = %s")
                values.append(description)
            if amount is not None:
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
                    expense_date = date.fromisoformat(expense_date)
                except:
                    return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400
                fields.append("date = %s")
                values.append(expense_date)

            if not fields:
                return jsonify({"error": "Nothing to update"}), 400

            values.extend([expense_id, user_id])
            cur.execute(
                f"UPDATE expenses SET {', '.join(fields)} WHERE id = %s AND user_id = %s RETURNING id",
                tuple(values)
            )
            updated = cur.fetchone()
            if not updated:
                return jsonify({"error": "Expense not found"}), 404

            # Adjust user's balance if amount changed
            if amount is not None:
                cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
                balance = Decimal(cur.fetchone()[0] or 0)
                balance = balance + old_amount - amount
                cur.execute("UPDATE users SET balance = %s WHERE id = %s", (balance, user_id))

        conn.commit()

    return jsonify({"message": "Expense updated", "id": expense_id, "balance": float(balance) if amount is not None else None}), 200

@expenses_bp.route("/<int:expense_id>", methods=["DELETE"])
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

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Fetch amount before deletion
            cur.execute(
                "SELECT amount FROM expenses WHERE id = %s AND user_id = %s",
                (expense_id, user_id)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Expense not found"}), 404

            amount = Decimal(row[0])

            # Delete expense
            cur.execute(
                "DELETE FROM expenses WHERE id = %s AND user_id = %s RETURNING id",
                (expense_id, user_id)
            )
            deleted = cur.fetchone()
            if not deleted:
                return jsonify({"error": "Expense not found"}), 404

            # Restore user's balance
            cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
            balance = Decimal(cur.fetchone()[0] or 0)
            balance += amount
            cur.execute("UPDATE users SET balance = %s WHERE id = %s", (balance, user_id))

        conn.commit()

    return jsonify({
        "message": "Expense deleted",
        "id": expense_id,
        "balance": float(balance)
    }), 200
   


