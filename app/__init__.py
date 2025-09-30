# app/__init__.py
import os
from flask import Flask, redirect
from flask_jwt_extended import JWTManager
from flasgger import Swagger

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # ----------------- CONFIG -----------------
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-secret")

    # ----------------- JWT -----------------
    JWTManager(app)

    # ----------------- SWAGGER -----------------
    Swagger(app, template={
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Authorization header using the Bearer scheme. Example: 'Bearer {token}'"
            }
        }
    })

    # ----------------- IMPORT BLUEPRINTS -----------------
    from app.auth.routes import auth_bp
    from app.users.routes import users_bp
    from app.expenses.routes import expenses_bp
    from app.categories.routes import categories_bp
    from app.aggregation.routes import aggregation_bp
    from app.tba_sio.routes import sio_bp
    from app.image.routes import image_bp

    # ----------------- REGISTER BLUEPRINTS -----------------
    app.register_blueprint(expenses_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(aggregation_bp)
    app.register_blueprint(sio_bp)
    app.register_blueprint(image_bp)

    # ----------------- ROUTES -----------------
    @app.route("/")
    def index():
        return redirect("/apidocs")

    return app
