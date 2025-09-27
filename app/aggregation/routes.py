from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.aggregation import aggregation_bp
from app.utils import get_db_connection
from datetime import date

@aggregation_bp.route("/", methods=["GET"])
@jwt_required()
def aggregation():
    """
    Aggregate user finances over a period: month, quarter, year
    """
    user_id = get_jwt_identity()
    period = request.args.get("period", "month")
    today = date.today()

    # ---- Determine start date ----
    if period == "month":
        start_date = today.replace(day=1)
    elif period == "quarter":
        quarter = (today.month - 1) // 3 + 1
        start_month = 3 * (quarter - 1) + 1
        start_date = date(today.year, start_month, 1)
    elif period == "year":
        start_date = date(today.year, 1, 1)
    else:
        return jsonify({"error": "Invalid period, use month|quarter|year"}), 400

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # ---- User balance ----
            cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
            user_balance = float(cur.fetchone()[0] or 0)

            # ---- Expenses by category ----
            cur.execute("""
                SELECT c.name, COALESCE(SUM(e.amount),0)
                FROM expenses e
                JOIN categories c ON e.category_id = c.id
                WHERE e.user_id=%s AND e.date >= %s AND e.date <= %s
                GROUP BY c.name
            """, (user_id, start_date, today))
            expenses_by_category = {row[0]: float(row[1]) for row in cur.fetchall()}

    # ---- KPIs ----
    spent = sum(expenses_by_category.values())
    earned = user_balance + spent
    housing = expenses_by_category.get("Rent / Mortgage", 0)
    utilities = expenses_by_category.get("Utilities", 0)
    insurance = expenses_by_category.get("Insurance", 0)
    subscriptions = expenses_by_category.get("Subscriptions", 0)
    discretionary = expenses_by_category.get("Entertainment", 0) + expenses_by_category.get("Dining Out", 0)
    savings = earned - spent
    savings_rate = (savings / earned * 100) if earned else 0
    fixed_expenses = housing + utilities + insurance + subscriptions
    fixed_expense_ratio = (fixed_expenses / earned * 100) if earned else 0

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
            "discretionary_ratio_percent": round((discretionary / earned * 100) if earned else 0, 2),
            "housing_cost_ratio_percent": round((housing / earned * 100) if earned else 0, 2)
        }
    })
