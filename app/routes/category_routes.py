from flask import Blueprint, request, jsonify, current_app
from app.utils.auth import token_required
from app.models.category import Category
from bson.objectid import ObjectId

category_bp = Blueprint('category', __name__, url_prefix='/api/categories')

@category_bp.route('/', methods=['POST'])
@token_required
def add_category(current_user):
    """Add a new category."""
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided'}), 400
    
    # Validate required fields
    required_fields = ['name', 'type']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Missing required field: {field}'}), 400
    
    # Validate category type
    if data['type'] not in ['income', 'expense']:
        return jsonify({'message': 'Category type must be either income or expense'}), 400
    
    # Check if category with the same name already exists for this user
    existing_category = current_app.mongo_db.categories.find_one({
        'name': data['name'],
        'type': data['type'],
        'user_id': current_user['sub']
    })
    
    if existing_category:
        return jsonify({'message': 'Category with this name already exists'}), 409
    
    # Create category object
    category = Category(
        name=data['name'],
        type=data['type'],
        user_id=current_user['sub']
    )
    
    # Save category to database
    result = current_app.mongo_db.categories.insert_one(category.to_dict())
    
    return jsonify({
        'message': 'Category added successfully',
        'category_id': str(result.inserted_id)
    }), 201

@category_bp.route('/', methods=['GET'])
@token_required
def get_categories(current_user):
    """Get all categories for the current user."""
    # Parse query parameters
    type_filter = request.args.get('type')  # 'income' or 'expense'
    
    # Build query - get both default categories and user's custom categories
    query = {
        '$or': [
            {'user_id': current_user['sub']},
            {'is_default': True, 'user_id': current_user['sub']}
        ]
    }
    
    if type_filter:
        query['type'] = type_filter
    
    # Query database
    categories = current_app.mongo_db.categories.find(query).sort('name', 1)
    
    # Convert to list of dictionaries
    categories_list = []
    for category in categories:
        category['_id'] = str(category['_id'])
        categories_list.append(category)
    
    return jsonify(categories_list), 200

@category_bp.route('/<category_id>', methods=['GET'])
@category_bp.route('/<category_id>/', methods=['GET'])  # Also support trailing slash
@token_required
def get_category(current_user, category_id):
    """Get a specific category."""
    try:
        # Query includes user's custom categories and default categories
        query = {
            '_id': ObjectId(category_id),
            '$or': [
                {'user_id': current_user['sub']},
                {'is_default': True, 'user_id': current_user['sub']}
            ]
        }
        
        category = current_app.mongo_db.categories.find_one(query)
    except:
        return jsonify({'message': 'Invalid category ID'}), 400
    
    if not category:
        return jsonify({'message': 'Category not found or access denied'}), 404
    
    category['_id'] = str(category['_id'])
    
    return jsonify(category), 200

@category_bp.route('/<category_id>', methods=['PUT'])
@category_bp.route('/<category_id>/', methods=['PUT'])  # Also support trailing slash
@token_required
def update_category(current_user, category_id):
    """Update a category."""
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided'}), 400
    
    # Check if category exists and belongs to user (not a default category)
    try:
        category = current_app.mongo_db.categories.find_one({
            '_id': ObjectId(category_id),
            'user_id': current_user['sub'],
            'is_default': {'$ne': True}  # Ensure it's not a default category
        })
    except:
        return jsonify({'message': 'Invalid category ID'}), 400
    
    if not category:
        return jsonify({'message': 'Category not found, access denied, or cannot modify default category'}), 404
    
    # Update fields
    update_data = {}
    
    if 'name' in data:
        # Check if another category with this name exists for this user
        existing_category = current_app.mongo_db.categories.find_one({
            'name': data['name'],
            'type': category['type'],
            'user_id': current_user['sub'],
            '_id': {'$ne': ObjectId(category_id)}
        })
        
        if existing_category:
            return jsonify({'message': 'Another category with this name already exists'}), 409
        
        update_data['name'] = data['name']
    
    if 'type' in data:
        if data['type'] not in ['income', 'expense']:
            return jsonify({'message': 'Category type must be either income or expense'}), 400
        update_data['type'] = data['type']
    
    # Update category
    if update_data:
        current_app.mongo_db.categories.update_one(
            {'_id': ObjectId(category_id)},
            {'$set': update_data}
        )
        
        # Update category name in transactions
        if 'name' in update_data:
            current_app.mongo_db.transactions.update_many(
                {'category_id': category_id},
                {'$set': {'category_name': update_data['name']}}
            )
    
    return jsonify({'message': 'Category updated successfully'}), 200

@category_bp.route('/<category_id>', methods=['DELETE'])
@category_bp.route('/<category_id>/', methods=['DELETE'])  # Also support trailing slash
@token_required
def delete_category(current_user, category_id):
    """Delete a category."""
    try:
        # Check if it's a default category (cannot be deleted)
        category = current_app.mongo_db.categories.find_one({
            '_id': ObjectId(category_id)
        })
        
        if not category:
            return jsonify({'message': 'Category not found'}), 404
        
        if category.get('is_default'):
            return jsonify({'message': 'Cannot delete default categories'}), 403
        
        if category.get('user_id') != current_user['sub']:
            return jsonify({'message': 'Access denied'}), 403
        
        # Check if category is used in any transactions
        transactions_count = current_app.mongo_db.transactions.count_documents({
            'category_id': category_id,
            'user_id': current_user['sub']
        })
        
        if transactions_count > 0:
            return jsonify({
                'message': 'Category is used in transactions and cannot be deleted',
                'transactions_count': transactions_count
            }), 400
        
        # Delete category
        result = current_app.mongo_db.categories.delete_one({
            '_id': ObjectId(category_id),
            'user_id': current_user['sub']
        })
        
        if result.deleted_count == 0:
            return jsonify({'message': 'Category not found or access denied'}), 404
        
        return jsonify({'message': 'Category deleted successfully'}), 200
    except:
        return jsonify({'message': 'Invalid category ID'}), 400
