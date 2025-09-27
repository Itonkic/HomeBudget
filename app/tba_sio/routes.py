from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.utils import get_db_connection, admin_required  # absolute import

sio_bp = Blueprint("tba_sio", __name__, url_prefix="/tba_sio")

@sio_bp.route("", methods=["POST"])
@jwt_required()
@admin_required
def create_tba_sio():
    """
    Create a new tba_sio entry
    ---
    tags:
      - TBA_SIO
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
            - key
            - value
          properties:
            key:
              type: string
              example: "Rent"
            value:
              type: number
              format: float
              example: 1000.00
    responses:
      201:
        description: tba_sio entry created successfully
        schema:
          type: object
          properties:
            key:
              type: string
              example: "Rent"
            value:
              type: number
              format: float
              example: 1000.00
      400:
        description: Bad request (missing key/value or key exists)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Key already exists"
    """
    data = request.get_json() or {}
    key = data.get("key")
    value = data.get("value")

    if not key or value is None:
        return jsonify({"error": "Key and value are required"}), 400

    try:
        value = float(value)
    except:
        return jsonify({"error": "Value must be a number"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM tba_sio WHERE key = %s", (key,))
        if cur.fetchone():
            return jsonify({"error": "Key already exists"}), 400

        cur.execute("INSERT INTO tba_sio (key, value) VALUES (%s, %s)", (key, value))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return jsonify({"key": key, "value": value}), 201

@sio_bp.route("", methods=["GET"])
@jwt_required()
@admin_required
def get_all_tba_sio():
    """
    Get all tba_sio entries
    ---
    tags:
      - TBA_SIO
    security:
      - Bearer: []
    produces:
      - application/json
    responses:
      200:
        description: List of all tba_sio entries
        schema:
          type: array
          items:
            type: object
            properties:
              key:
                type: string
                example: "Rent"
              value:
                type: number
                format: float
                example: 1000.00
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM tba_sio ORDER BY key")
    entries = [{"key": row[0], "value": float(row[1])} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(entries)

@sio_bp.route("/<string:key>", methods=["GET"])
@jwt_required()
@admin_required
def get_tba_sio(key):
    """
    Get a tba_sio entry by key
    ---
    tags:
      - TBA_SIO
    security:
      - Bearer: []
    parameters:
      - name: key
        in: path
        type: string
        required: true
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM tba_sio WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"error": "Key not found"}), 404
    return jsonify({"key": row[0], "value": float(row[1])})

@sio_bp.route("/<string:key>", methods=["PUT"])
@jwt_required()
@admin_required
def update_tba_sio(key):
    """
    Update an existing tba_sio entry
    ---
    tags:
      - TBA_SIO
    security:
      - Bearer: []
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - name: key
        in: path
        type: string
        required: true
        description: Key of the entry to update
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - value
          properties:
            value:
              type: number
              format: float
              example: 1200.00
    responses:
      200:
        description: Entry updated successfully
        schema:
          type: object
          properties:
            key:
              type: string
              example: "Rent"
            value:
              type: number
              format: float
              example: 1200.00
      404:
        description: Entry not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Entry not found"
    """
    data = request.get_json() or {}
    value = data.get("value")
    if value is None:
        return jsonify({"error": "Value is required"}), 400
    try:
        value = float(value)
    except:
        return jsonify({"error": "Value must be a number"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE tba_sio SET value = %s WHERE key = %s RETURNING key", (value, key))
    updated = cur.fetchone()
    if not updated:
        cur.close()
        conn.close()
        return jsonify({"error": "Key not found"}), 404
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"key": key, "value": value})

@sio_bp.route("/<string:key>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_tba_sio(key):
    """
    Delete a tba_sio entry
    ---
    tags:
      - TBA_SIO
    security:
      - Bearer: []
    produces:
      - application/json
    parameters:
      - name: key
        in: path
        type: string
        required: true
        description: Key of the entry to delete
    responses:
      200:
        description: Entry deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Entry deleted"
            key:
              type: string
              example: "Rent"
      404:
        description: Entry not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Entry not found"
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tba_sio WHERE key = %s RETURNING key", (key,))
    deleted = cur.fetchone()
    if not deleted:
        cur.close()
        conn.close()
        return jsonify({"error": "Key not found"}), 404
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Deleted", "key": key})

