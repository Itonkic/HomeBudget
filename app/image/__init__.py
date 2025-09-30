from flask import Blueprint

image_bp = Blueprint("auth", __name__)
from . import routes