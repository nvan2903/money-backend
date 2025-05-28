from flask import Blueprint, request, jsonify, current_app, send_file
from app.utils.auth import token_required
from app.models.transaction import Transaction
from bson.objectid import ObjectId
from datetime import datetime
import pymongo

transaction_bp = Blueprint('transaction', __name__, url_prefix='/api/transactions')

@transaction_bp.route('/', methods=['POST'])
@token_required
def add_transaction(current_user):
    """Add a new transaction."""
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided'}), 400
    
    # Validate required fields
    required_fields = ['amount', 'type', 'category_id']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Missing required field: {field}'}), 400
    
    # Validate transaction type
    if data['type'] not in ['income', 'expense']:
        return jsonify({'message': 'Transaction type must be either income or expense'}), 400
    
    # Check if category exists
    category = current_app.mongo_db.categories.find_one({'_id': ObjectId(data['category_id'])})
    if not category:
        return jsonify({'message': 'Category not found'}), 404
    
    # Create transaction object
    transaction = Transaction(
        user_id=current_user['sub'],
        amount=data['amount'],
        type=data['type'],
        category_id=data['category_id'],
        category_name=category['name'],
        date=datetime.fromisoformat(data['date']) if 'date' in data else datetime.utcnow(),
        note=data.get('note')
    )
    
    # Save transaction to database
    result = current_app.mongo_db.transactions.insert_one(transaction.to_dict())
    
    return jsonify({
        'message': 'Transaction added successfully',
        'transaction_id': str(result.inserted_id)
    }), 201

@transaction_bp.route('/', methods=['GET'])
@token_required
def get_transactions(current_user):
    """Get all transactions for the current user with enhanced multi-field search."""
    # Parse query parameters - Enhanced like admin routes
    search = request.args.get('search', '')  # General search query
    type_filter = request.args.get('type')
    category_id = request.args.get('category_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')
    
    # Enhanced search parameters
    date_from = request.args.get('date_from') or start_date
    date_to = request.args.get('date_to') or end_date
    amount_min = request.args.get('amount_min') or min_amount
    amount_max = request.args.get('amount_max') or max_amount
    
    # Pagination and sorting
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    sort_by = request.args.get('sort_by', 'date')  # 'date', 'amount', 'category'
    sort_order = request.args.get('sort_order', 'desc')  # 'asc', 'desc'
    
    # Build query
    query = {'user_id': current_user['sub']}
    
    # Enhanced text search in multiple fields
    if search:
        query['$or'] = [
            {'note': {'$regex': search, '$options': 'i'}},
            {'category_name': {'$regex': search, '$options': 'i'}}
        ]
    
    # Type filter
    if type_filter:
        query['type'] = type_filter
        
    # Category filter
    if category_id:
        query['category_id'] = category_id
    
    # Date range filter
    if date_from or date_to:
        query['date'] = {}
        if date_from:
            query['date']['$gte'] = datetime.fromisoformat(date_from)
        if date_to:
            query['date']['$lte'] = datetime.fromisoformat(date_to)
    
    # Amount range filter
    if amount_min or amount_max:
        query['amount'] = {}
        if amount_min:
            query['amount']['$gte'] = float(amount_min)
        if amount_max:
            query['amount']['$lte'] = float(amount_max)
    
    # Sort configuration
    sort_field = sort_by
    sort_direction = pymongo.DESCENDING if sort_order == 'desc' else pymongo.ASCENDING
    
    # Query database with pagination
    total = current_app.mongo_db.transactions.count_documents(query)
    transactions = current_app.mongo_db.transactions.find(query) \
        .sort(sort_field, sort_direction) \
        .skip((page - 1) * per_page) \
        .limit(per_page)
    
    # Convert to list of dictionaries
    transactions_list = []
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
        transactions_list.append(transaction)
    
    return jsonify({
        'transactions': transactions_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }), 200

@transaction_bp.route('/search-suggestions', methods=['GET'])
@transaction_bp.route('/search-suggestions/', methods=['GET'])
@token_required
def get_search_suggestions(current_user):
    """Get search suggestions for autocomplete."""
    try:
        # Get unique notes and category names from user's transactions
        pipeline = [
            {'$match': {'user_id': current_user['sub']}},
            {'$group': {
                '_id': None,
                'notes': {'$addToSet': '$note'},
                'categories': {'$addToSet': '$category_name'}
            }}
        ]
        
        result = list(current_app.mongo_db.transactions.aggregate(pipeline))
        
        suggestions = []
        if result:
            # Add non-empty notes
            if result[0].get('notes'):
                suggestions.extend([note for note in result[0]['notes'] if note and note.strip()])
            
            # Add category names
            if result[0].get('categories'):
                suggestions.extend([cat for cat in result[0]['categories'] if cat and cat.strip()])
        
        # Remove duplicates and limit
        unique_suggestions = list(set(suggestions))[:20]
        
        return jsonify({'suggestions': unique_suggestions}), 200
    except Exception as e:
        current_app.logger.error(f"Error getting search suggestions: {str(e)}")
        return jsonify({'suggestions': [], 'error': str(e)}), 200

@transaction_bp.route('/<transaction_id>', methods=['GET'])
@transaction_bp.route('/<transaction_id>/', methods=['GET'])
@token_required
def get_transaction(current_user, transaction_id):
    """Get a specific transaction."""
    try:
        transaction = current_app.mongo_db.transactions.find_one({
            '_id': ObjectId(transaction_id),
            'user_id': current_user['sub']
        })
    except:
        return jsonify({'message': 'Invalid transaction ID'}), 400
    
    if not transaction:
        return jsonify({'message': 'Transaction not found'}), 404
    
    transaction['_id'] = str(transaction['_id'])
    
    return jsonify(transaction), 200

@transaction_bp.route('/<transaction_id>', methods=['PUT'])
@transaction_bp.route('/<transaction_id>/', methods=['PUT'])
@token_required
def update_transaction(current_user, transaction_id):
    """Update a transaction."""
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided'}), 400
    
    # Check if transaction exists and belongs to user
    try:
        transaction = current_app.mongo_db.transactions.find_one({
            '_id': ObjectId(transaction_id),
            'user_id': current_user['sub']
        })
    except:
        return jsonify({'message': 'Invalid transaction ID'}), 400
    
    if not transaction:
        return jsonify({'message': 'Transaction not found or access denied'}), 404
    
    # Update fields
    update_data = {}
    
    if 'amount' in data:
        update_data['amount'] = float(data['amount'])
    
    if 'type' in data:
        if data['type'] not in ['income', 'expense']:
            return jsonify({'message': 'Transaction type must be either income or expense'}), 400
        update_data['type'] = data['type']
    
    if 'category_id' in data:
        # Check if category exists
        category = current_app.mongo_db.categories.find_one({'_id': ObjectId(data['category_id'])})
        if not category:
            return jsonify({'message': 'Category not found'}), 404
        
        update_data['category_id'] = data['category_id']
        update_data['category_name'] = category['name']
    
    if 'date' in data:
        try:
            update_data['date'] = datetime.fromisoformat(data['date'])
        except ValueError:
            return jsonify({'message': 'Invalid date format'}), 400
    
    if 'note' in data:
        update_data['note'] = data['note']
    
    # Update transaction
    current_app.mongo_db.transactions.update_one(
        {'_id': ObjectId(transaction_id)},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Transaction updated successfully'}), 200

@transaction_bp.route('/<transaction_id>', methods=['DELETE'])
@transaction_bp.route('/<transaction_id>/', methods=['DELETE'])
@token_required
def delete_transaction(current_user, transaction_id):
    """Delete a transaction."""
    # Check if transaction exists and belongs to user
    try:
        result = current_app.mongo_db.transactions.delete_one({
            '_id': ObjectId(transaction_id),
            'user_id': current_user['sub']
        })
    except:
        return jsonify({'message': 'Invalid transaction ID'}), 400
    
    if result.deleted_count == 0:
        return jsonify({'message': 'Transaction not found or access denied'}), 404
    
    return jsonify({'message': 'Transaction deleted successfully'}), 200

@transaction_bp.route('/search', methods=['GET'])
@transaction_bp.route('/search/', methods=['GET'])
@token_required
def search_transactions(current_user):
    """Advanced search for transactions with enhanced multi-field search."""
    # Search parameters
    query_text = request.args.get('q', '')  # General search query
    search = request.args.get('search', '') or query_text  # Support both parameters
    amount_min = request.args.get('amount_min')
    amount_max = request.args.get('amount_max')
    type_filter = request.args.get('type')
    category_id = request.args.get('category_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    sort_by = request.args.get('sort_by', 'date')  # 'date', 'amount', 'category'
    sort_order = request.args.get('sort_order', 'desc')  # 'asc', 'desc'
    
    # Build base query
    query = {'user_id': current_user['sub']}
    
    # Enhanced text search in note and category name
    if search:
        query['$or'] = [
            {'note': {'$regex': search, '$options': 'i'}},
            {'category_name': {'$regex': search, '$options': 'i'}}
        ]
    
    # Amount range filter
    if amount_min or amount_max:
        query['amount'] = {}
        if amount_min:
            query['amount']['$gte'] = float(amount_min)
        if amount_max:
            query['amount']['$lte'] = float(amount_max)
    
    # Type filter
    if type_filter and type_filter in ['income', 'expense']:
        query['type'] = type_filter
    
    # Category filter
    if category_id:
        query['category_id'] = category_id
    
    # Date range filter
    if date_from or date_to:
        query['date'] = {}
        if date_from:
            query['date']['$gte'] = datetime.fromisoformat(date_from)
        if date_to:
            query['date']['$lte'] = datetime.fromisoformat(date_to)
    
    # Sort configuration
    sort_field = sort_by
    sort_direction = pymongo.DESCENDING if sort_order == 'desc' else pymongo.ASCENDING
    
    # Execute query
    total = current_app.mongo_db.transactions.count_documents(query)
    transactions = current_app.mongo_db.transactions.find(query) \
        .sort(sort_field, sort_direction) \
        .skip((page - 1) * per_page) \
        .limit(per_page)
    
    # Convert to list
    transactions_list = []
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
        transactions_list.append(transaction)
    
    return jsonify({
        'transactions': transactions_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'query': {
            'text': search,
            'amount_min': amount_min,
            'amount_max': amount_max,
            'type': type_filter,
            'category_id': category_id,
            'date_from': date_from,
            'date_to': date_to
        }
    }), 200

@transaction_bp.route('/bulk-delete', methods=['POST'])
@token_required
def bulk_delete_transactions(current_user):
    """Delete multiple transactions at once."""
    data = request.get_json()
    
    if not data or 'transaction_ids' not in data:
        return jsonify({'message': 'Transaction IDs are required'}), 400
    
    transaction_ids = data['transaction_ids']
    
    if not isinstance(transaction_ids, list) or not transaction_ids:
        return jsonify({'message': 'Invalid transaction IDs format'}), 400
    
    try:
        # Convert to ObjectIds and validate they belong to the user
        object_ids = [ObjectId(tid) for tid in transaction_ids]
        
        # Delete transactions
        result = current_app.mongo_db.transactions.delete_many({
            '_id': {'$in': object_ids},
            'user_id': current_user['sub']
        })
        
        return jsonify({
            'message': f'{result.deleted_count} transactions deleted successfully',
            'deleted_count': result.deleted_count
        }), 200
    
    except Exception as e:
        return jsonify({'message': 'Error deleting transactions'}), 400

@transaction_bp.route('/export', methods=['GET'])
@transaction_bp.route('/export/', methods=['GET'])
@token_required
def export_transactions(current_user):
    """Export user's transactions in various formats."""
    from app.utils.report_generator import ReportGenerator
    
    # Get format from query params
    export_format = request.args.get('format', 'csv').lower()
    
    if export_format not in ['csv', 'excel', 'pdf']:
        return jsonify({'message': 'Unsupported export format. Use csv, excel, or pdf'}), 400
    
    # Parse filters
    type_filter = request.args.get('type')
    category_id = request.args.get('category_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')
    search = request.args.get('search')
    
    # Build query
    query = {'user_id': current_user['sub']}
    
    if type_filter:
        query['type'] = type_filter
    
    if category_id:
        query['category_id'] = category_id
    
    if date_from or date_to:
        query['date'] = {}
        if date_from:
            query['date']['$gte'] = datetime.fromisoformat(date_from)
        if date_to:
            query['date']['$lte'] = datetime.fromisoformat(date_to)
    
    if min_amount or max_amount:
        query['amount'] = {}
        if min_amount:
            query['amount']['$gte'] = float(min_amount)
        if max_amount:
            query['amount']['$lte'] = float(max_amount)
    
    if search:
        query['$or'] = [
            {'note': {'$regex': search, '$options': 'i'}},
            {'category_name': {'$regex': search, '$options': 'i'}}
        ]
    
    # Fetch transactions
    transactions = list(current_app.mongo_db.transactions.find(query).sort('date', pymongo.DESCENDING))
    
    # Convert ObjectId to string
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
    
    try:
        # Generate report
        report_generator = ReportGenerator()
        
        if export_format == 'csv':
            file_path = report_generator.generate_transactions_csv(transactions, current_user['sub'])
            mimetype = 'text/csv'
            filename = f'transactions_{current_user["sub"]}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        elif export_format == 'excel':
            file_path = report_generator.generate_transactions_excel(transactions, current_user['sub'])
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f'transactions_{current_user["sub"]}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
        elif export_format == 'pdf':
            file_path = report_generator.generate_transactions_pdf(transactions, current_user['sub'])
            mimetype = 'application/pdf'
            filename = f'transactions_{current_user["sub"]}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({'message': f'Failed to generate report: {str(e)}'}), 500

@transaction_bp.route('/duplicate/<transaction_id>', methods=['POST'])
@token_required
def duplicate_transaction(current_user, transaction_id):
    """Duplicate an existing transaction."""
    try:
        # Find the original transaction
        original = current_app.mongo_db.transactions.find_one({
            '_id': ObjectId(transaction_id),
            'user_id': current_user['sub']
        })
        
        if not original:
            return jsonify({'message': 'Transaction not found'}), 404
        
        # Create new transaction data
        new_transaction = Transaction(
            user_id=current_user['sub'],
            amount=original['amount'],
            type=original['type'],
            category_id=original['category_id'],
            category_name=original['category_name'],
            date=datetime.utcnow(),  # Use current date
            note=f"Copy of: {original.get('note', '')}"
        )
        
        # Save new transaction
        result = current_app.mongo_db.transactions.insert_one(new_transaction.to_dict())
        
        return jsonify({
            'message': 'Transaction duplicated successfully',
            'transaction_id': str(result.inserted_id)
        }), 201
    
    except Exception as e:
        return jsonify({'message': 'Error duplicating transaction'}), 400
