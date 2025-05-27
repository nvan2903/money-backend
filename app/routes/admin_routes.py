from flask import Blueprint, request, jsonify, current_app, send_file
from app.utils.auth import token_required, admin_required
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId
from datetime import datetime
import pymongo

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@admin_bp.route('/users', methods=['GET'])
@admin_bp.route('/users/', methods=['GET'])
@token_required
@admin_required
def get_users(current_user):
    """Get all users (admin only)."""
    # Parse query parameters
    search = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    
    # Build query for search
    query = {}
    if search:
        query['$or'] = [
            {'username': {'$regex': search, '$options': 'i'}},
            {'email': {'$regex': search, '$options': 'i'}},
            {'first_name': {'$regex': search, '$options': 'i'}},
            {'last_name': {'$regex': search, '$options': 'i'}}
        ]
    
    # Count total users
    total = current_app.mongo_db.users.count_documents(query)
    
    # Get users with pagination
    users = current_app.mongo_db.users.find(query) \
        .sort('created_at', pymongo.DESCENDING) \
        .skip((page - 1) * per_page) \
        .limit(per_page)
    
    # Prepare response
    users_list = []
    for user in users:
        user['_id'] = str(user['_id'])
        # Remove password
        if 'password' in user:
            del user['password']
        users_list.append(user)
    
    return jsonify({
        'users': users_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }), 200

@admin_bp.route('/users/<user_id>', methods=['GET'])
@admin_bp.route('/users/<user_id>/', methods=['GET'])
@token_required
@admin_required
def get_user(current_user, user_id):
    """Get a specific user (admin only)."""
    try:
        user = current_app.mongo_db.users.find_one({'_id': ObjectId(user_id)})
    except:
        return jsonify({'message': 'Invalid user ID'}), 400
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    user['_id'] = str(user['_id'])
    
    # Remove password
    if 'password' in user:
        del user['password']
    
    return jsonify(user), 200

@admin_bp.route('/users/<user_id>/toggle-status', methods=['PUT'])
@admin_bp.route('/users/<user_id>/toggle-status/', methods=['PUT'])
@token_required
@admin_required
def toggle_user_status(current_user, user_id):
    """Toggle user active status (admin only)."""
    try:
        # Check if user exists
        user = current_app.mongo_db.users.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Cannot deactivate own admin account
        if str(user['_id']) == current_user['sub'] and user.get('role') == 'admin':
            return jsonify({'message': 'Cannot deactivate your own admin account'}), 400
        
        # Toggle is_active status
        new_status = not user.get('is_active', True)
        
        current_app.mongo_db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'is_active': new_status}}
        )
        
        status_text = "activated" if new_status else "deactivated"
        
        return jsonify({
            'message': f'User {status_text} successfully',
            'is_active': new_status
        }), 200
    except:
        return jsonify({'message': 'Invalid user ID'}), 400

@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@admin_bp.route('/users/<user_id>/', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    """Delete a user (admin only)."""
    try:
        # Check if user exists
        user = current_app.mongo_db.users.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Cannot delete own admin account
        if str(user['_id']) == current_user['sub'] and user.get('role') == 'admin':
            return jsonify({'message': 'Cannot delete your own admin account'}), 400
        
        # Delete user's transactions
        current_app.mongo_db.transactions.delete_many({'user_id': user_id})
        
        # Delete user's custom categories
        current_app.mongo_db.categories.delete_many({
            'user_id': user_id,
            'is_default': False
        })
        
        # Delete user
        current_app.mongo_db.users.delete_one({'_id': ObjectId(user_id)})
        
        return jsonify({'message': 'User and all associated data deleted successfully'}), 200
    except:
        return jsonify({'message': 'Invalid user ID'}), 400

@admin_bp.route('/transactions', methods=['GET'])
@admin_bp.route('/transactions/', methods=['GET'])
@token_required
@admin_required
def get_all_transactions(current_user):
    """Get all transactions from all users (admin only)."""
    # Parse query parameters
    user_id = request.args.get('user_id')
    type_filter = request.args.get('type')
    category_id = request.args.get('category_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    
    # Build query
    query = {}
    
    if user_id:
        query['user_id'] = user_id
    
    if type_filter:
        query['type'] = type_filter
    
    if category_id:
        query['category_id'] = category_id
    
    if start_date or end_date:
        query['date'] = {}
        if start_date:
            query['date']['$gte'] = datetime.fromisoformat(start_date)
        if end_date:
            query['date']['$lte'] = datetime.fromisoformat(end_date)
    
    if min_amount or max_amount:
        query['amount'] = {}
        if min_amount:
            query['amount']['$gte'] = float(min_amount)
        if max_amount:
            query['amount']['$lte'] = float(max_amount)
    
    # Query database with pagination
    total = current_app.mongo_db.transactions.count_documents(query)
    transactions = current_app.mongo_db.transactions.find(query) \
        .sort('date', pymongo.DESCENDING) \
        .skip((page - 1) * per_page) \
        .limit(per_page)
    
    # Get user information for each transaction
    transactions_list = []
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
        
        # Add user info
        user = current_app.mongo_db.users.find_one({'_id': ObjectId(transaction['user_id'])})
        if user:
            transaction['user_info'] = {
                'username': user['username'],
                'email': user['email']
            }
        
        transactions_list.append(transaction)
    
    return jsonify({
        'transactions': transactions_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }), 200

@admin_bp.route('/stats', methods=['GET'])
@admin_bp.route('/stats/', methods=['GET'])
@token_required
@admin_required
def get_system_stats(current_user):
    """Get system statistics (admin only)."""
    # Total users
    total_users = current_app.mongo_db.users.count_documents({})
    
    # Total transactions
    total_transactions = current_app.mongo_db.transactions.count_documents({})
    
    # Total income and expense
    pipeline = [
        {'$group': {
            '_id': '$type',
            'total': {'$sum': '$amount'}
        }}
    ]
    
    transaction_totals = list(current_app.mongo_db.transactions.aggregate(pipeline))
    
    total_income = next((item['total'] for item in transaction_totals if item['_id'] == 'income'), 0)
    total_expense = next((item['total'] for item in transaction_totals if item['_id'] == 'expense'), 0)
    
    # Users with high spending (top 5)
    pipeline = [
        {'$match': {'type': 'expense'}},
        {'$group': {
            '_id': '$user_id',
            'total_expense': {'$sum': '$amount'}
        }},
        {'$sort': {'total_expense': -1}},
        {'$limit': 5}
    ]
    
    high_spenders = list(current_app.mongo_db.transactions.aggregate(pipeline))
    
    # Add user info
    for spender in high_spenders:
        user = current_app.mongo_db.users.find_one({'_id': ObjectId(spender['_id'])})
        if user:
            spender['user_info'] = {
                'username': user['username'],
                'email': user['email']
            }
        spender['user_id'] = spender.pop('_id')
    
    return jsonify({
        'user_count': total_users,
        'transaction_count': total_transactions,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': total_income - total_expense,
        'high_spenders': high_spenders
    }), 200

@admin_bp.route('/reports/generate', methods=['POST'])
@admin_bp.route('/reports/generate/', methods=['POST'])
@token_required
@admin_required
def generate_system_report(current_user):
    """Generate and export system-wide reports (admin only)."""
    from app.utils.report_generator import ReportGenerator
    
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided'}), 400
    
    # Parameters
    export_format = data.get('format', 'excel')  # 'excel', 'csv', 'pdf'
    report_type = data.get('type', 'overview')  # 'overview', 'financial', 'user-activity', 'transaction-details'
    date_from = data.get('start_date')
    date_to = data.get('end_date')
    period = data.get('period', 'month')  # 'month', 'quarter', 'year'
    
    if export_format not in ['csv', 'excel', 'pdf']:
        return jsonify({'message': 'Invalid export format. Use csv, excel, or pdf'}), 400
    
    try:
        # Build date query
        date_query = {}
        if date_from or date_to:
            date_query['date'] = {}
            if date_from:
                date_query['date']['$gte'] = datetime.fromisoformat(date_from)
            if date_to:
                date_query['date']['$lte'] = datetime.fromisoformat(date_to)
        
        # Get system statistics
        system_stats = {}
        
        # Total users
        system_stats['total_users'] = current_app.mongo_db.users.count_documents({})
        system_stats['active_users'] = current_app.mongo_db.users.count_documents({'is_active': True})
        
        # Transaction totals
        transaction_pipeline = [
            {'$match': date_query} if date_query else {'$match': {}},
            {'$group': {
                '_id': '$type',
                'total': {'$sum': '$amount'},
                'count': {'$sum': 1}
            }}
        ]
        
        transaction_totals = list(current_app.mongo_db.transactions.aggregate(transaction_pipeline))
        system_stats['total_income'] = next((item['total'] for item in transaction_totals if item['_id'] == 'income'), 0)
        system_stats['total_expense'] = next((item['total'] for item in transaction_totals if item['_id'] == 'expense'), 0)
        system_stats['transaction_count'] = sum(item['count'] for item in transaction_totals)
        
        # Get transactions based on report type
        if report_type == 'transaction-details':
            # Get detailed transactions
            query = date_query.copy()
            transactions = list(current_app.mongo_db.transactions.find(query)
                              .sort('date', pymongo.DESCENDING)
                              .limit(1000))  # Limit for performance
            
            # Add user information
            for transaction in transactions:
                transaction['_id'] = str(transaction['_id'])
                user = current_app.mongo_db.users.find_one({'_id': ObjectId(transaction['user_id'])})
                if user:
                    transaction['user_info'] = {
                        'username': user['username'],
                        'email': user['email']
                    }
                transaction['date'] = transaction['date'].strftime('%Y-%m-%d')
                transaction['created_at'] = transaction['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            report_data = {
                'system_stats': system_stats,
                'transactions': transactions,
                'report_type': report_type,
                'period': period
            }
            
        elif report_type == 'user-activity':
            # Get user activity data
            user_activity_pipeline = [
                {'$match': date_query} if date_query else {'$match': {}},
                {'$group': {
                    '_id': '$user_id',
                    'total_income': {'$sum': {'$cond': [{'$eq': ['$type', 'income']}, '$amount', 0]}},
                    'total_expense': {'$sum': {'$cond': [{'$eq': ['$type', 'expense']}, '$amount', 0]}},
                    'transaction_count': {'$sum': 1}
                }},
                {'$sort': {'total_expense': -1}},
                {'$limit': 50}
            ]
            
            user_activities = list(current_app.mongo_db.transactions.aggregate(user_activity_pipeline))
            
            # Add user information
            for activity in user_activities:
                user = current_app.mongo_db.users.find_one({'_id': ObjectId(activity['_id'])})
                if user:
                    activity['user_info'] = {
                        'username': user['username'],
                        'email': user['email']
                    }
                activity['user_id'] = activity.pop('_id')
                activity['net_balance'] = activity['total_income'] - activity['total_expense']
            
            report_data = {
                'system_stats': system_stats,
                'user_activities': user_activities,
                'report_type': report_type,
                'period': period
            }
            
        else:  # overview or financial
            # Get category breakdown
            category_pipeline = [
                {'$match': date_query} if date_query else {'$match': {}},
                {'$match': {'type': 'expense'}},
                {'$group': {
                    '_id': '$category_name',
                    'total': {'$sum': '$amount'},
                    'count': {'$sum': 1}
                }},
                {'$sort': {'total': -1}},
                {'$limit': 20}
            ]
            
            categories = list(current_app.mongo_db.transactions.aggregate(category_pipeline))
            
            # Monthly trend data
            monthly_pipeline = [
                {'$match': date_query} if date_query else {'$match': {}},
                {'$group': {
                    '_id': {
                        'year': {'$year': '$date'},
                        'month': {'$month': '$date'},
                        'type': '$type'
                    },
                    'total': {'$sum': '$amount'}
                }},
                {'$sort': {'_id.year': 1, '_id.month': 1}}
            ]
            
            monthly_data = list(current_app.mongo_db.transactions.aggregate(monthly_pipeline))
            
            report_data = {
                'system_stats': system_stats,
                'categories': categories,
                'monthly_data': monthly_data,
                'report_type': report_type,
                'period': period
            }
        
        # Generate report based on format
        if export_format == 'csv':
            file_buffer, filename = ReportGenerator.generate_admin_csv_report(report_data)
            return send_file(
                file_buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='text/csv'
            )
        elif export_format == 'excel':
            file_buffer, filename = ReportGenerator.generate_admin_excel_report(report_data)
            return send_file(
                file_buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'pdf':
            file_buffer, filename = ReportGenerator.generate_admin_pdf_report(report_data)
            return send_file(
                file_buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )
    
    except Exception as e:
        return jsonify({'message': f'Error generating system report: {str(e)}'}), 500

@admin_bp.route('/transactions/export', methods=['GET'])
@admin_bp.route('/transactions/export/', methods=['GET'])
@token_required
@admin_required
def export_all_transactions(current_user):
    """Export all system transactions in various formats (admin only)."""
    from app.utils.report_generator import ReportGenerator
    
    # Get format from query params
    export_format = request.args.get('format', 'csv').lower()
    
    if export_format not in ['csv', 'excel', 'pdf']:
        return jsonify({'message': 'Unsupported export format. Use csv, excel, or pdf'}), 400
    
    # Parse filters
    user_id = request.args.get('user_id')
    type_filter = request.args.get('type')
    category_id = request.args.get('category_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')
    search = request.args.get('search')
    
    # Build query
    query = {}
    
    if user_id:
        query['user_id'] = user_id
    
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
    transactions = list(current_app.mongo_db.transactions.find(query).sort('date', pymongo.DESCENDING).limit(5000))
    
    # Add user information and convert ObjectId to string
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
        user = current_app.mongo_db.users.find_one({'_id': ObjectId(transaction['user_id'])})
        if user:
            transaction['user_info'] = {
                'username': user['username'],
                'email': user['email']
            }
    
    try:
        # Generate report
        report_generator = ReportGenerator()
        
        if export_format == 'csv':
            file_path = report_generator.generate_admin_transactions_csv(transactions)
            mimetype = 'text/csv'
            filename = f'admin_transactions_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        elif export_format == 'excel':
            file_path = report_generator.generate_admin_transactions_excel(transactions)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f'admin_transactions_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
        elif export_format == 'pdf':
            file_path = report_generator.generate_admin_transactions_pdf(transactions)
            mimetype = 'application/pdf'
            filename = f'admin_transactions_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({'message': f'Failed to generate report: {str(e)}'}), 500
