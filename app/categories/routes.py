from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.utils import get_db_connection  # absolute import

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")
 


@categories_bp.route("", methods=['POST'])
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

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if category already exists
            cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
            if cur.fetchone():
                return jsonify({"error": "Category already exists"}), 400

            # Ensure sequence is in sync
            cur.execute(
                "SELECT setval('categories_id_seq', COALESCE((SELECT MAX(id) FROM categories), 0))"
            )

            # Insert new category
            cur.execute(
                "INSERT INTO categories (name) VALUES (%s) RETURNING id", (name,)
            )
            category_id = cur.fetchone()[0]
            conn.commit()

    return jsonify({"id": category_id, "name": name}), 201

@categories_bp.route("", methods=["GET"])
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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM categories ORDER BY name")
            categories = [{"id": row[0], "name": row[1]} for row in cur.fetchall()]

    return jsonify(categories)

@categories_bp.route("/<int:id>", methods=['PUT'])
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

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE categories SET name = %s WHERE id = %s RETURNING id", (name, id)
            )
            updated = cur.fetchone()
            if updated is None:
                return jsonify({"error": "Category not found"}), 404
            conn.commit()

    return jsonify({"id": id, "name": name})

@categories_bp.route("/<int:id>", methods=['DELETE'])
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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM categories WHERE id = %s RETURNING id", (id,)
            )
            deleted = cur.fetchone()
            if deleted is None:
                return jsonify({"error": "Category not found"}), 404
            conn.commit()

    return jsonify({"message": "Category deleted"})

  

