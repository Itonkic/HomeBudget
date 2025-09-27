# app/app.py

from flask import Flask, redirect
from flask_jwt_extended import JWTManager
from flasgger import Swagger
import os

# ----------------- BLUEPRINTS -----------------
from app.auth import auth_bp
from app.users import users_bp
from app.expenses import expenses_bp
from app.categories import categories_bp
from app.aggregation import aggregation_bp

# ----------------- UTILS -----------------
from app.utils import validate_password, get_db_connection, admin_required, send_email, apply_monthly_payday

# ----------------- FLASK APP -----------------
app = Flask(__name__, static_folder="static", template_folder="templates")

# JWT
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-secret")
jwt = JWTManager(app)

# Swagger
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

# ----------------- REGISTER BLUEPRINTS -----------------
app.register_blueprint(expenses_bp)
app.register_blueprint(users_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(categories_bp)
app.register_blueprint(aggregation_bp)

# ----------------- ROUTES -----------------
@app.route("/")
def index():
    return redirect("/apidocs")  # or render_template("index.html") if you want UI

# ----------------- MAIN -----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
