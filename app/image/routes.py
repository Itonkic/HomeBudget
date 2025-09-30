from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.utils import get_db_connection  # absolute import
import cv2
import numpy as np

image_bp = Blueprint("image", __name__, url_prefix="/image")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "tiff"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_amount_opencv(img):
    """Extract largest numeric-like region in lower-right quadrant using OpenCV."""
    h, w = img.shape[:2]
    quadrant = img[h//2:, w//2:]

    gray = cv2.cvtColor(quadrant, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    max_val = 0.0

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        roi = quadrant[y:y+ch, x:x+cw]
        text_like = cv2.resize(roi, (100, 30))
        # Simple numeric detection: count white pixels as proxy for digits
        white_pixels = cv2.countNonZero(cv2.cvtColor(text_like, cv2.COLOR_BGR2GRAY))
        if white_pixels > max_val:
            max_val = white_pixels
            # We could extract the number via image processing here if needed
    return None  # Placeholder: without OCR we can't get exact number


def extract_store_opencv(img):
    """Detect top third region and find store name-like line (ends with d.o.o or d.d)"""
    h, w = img.shape[:2]
    top_strip = img[:h//3]

    gray = cv2.cvtColor(top_strip, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5),0)
    _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    possible_names = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw > 50 and ch > 10:  # heuristic to ignore small blobs
            possible_names.append((x, y, cw, ch))

    # Sort top to bottom
    possible_names.sort(key=lambda b: b[1])

    # Placeholder: return bounding box of top-most blob containing text
    for x, y, cw, ch in possible_names:
        roi_text = top_strip[y:y+ch, x:x+cw]
        # Fake detection: return rectangle string
        return f"ROI at x:{x}, y:{y}, w:{cw}, h:{ch}" 
    return None


@image_bp.route("/upload-receipt", methods=["POST"])
@jwt_required()
def upload_receipt():
    user_id = get_jwt_identity()
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file"}), 400

    folder_name = request.form.get("folder_name", "receipts")
    upload_folder = os.path.join(r"C:\inetpub\wwwroot\FlaskApp\static\image", folder_name)
    os.makedirs(upload_folder, exist_ok=True)

    filename = file.filename
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    try:
        img = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_COLOR)

        amount = extract_amount_opencv(img)
        store_name = extract_store_opencv(img)

    except Exception as e:
        return jsonify({"error": f"Image processing failed: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "filename": filename,
        "store_name": store_name,
        "amount": amount
    }), 200
