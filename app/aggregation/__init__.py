from flask import Blueprint

aggregation_bp = Blueprint("aggregation", __name__)
from app.aggregation import routes  # noqa: F401
