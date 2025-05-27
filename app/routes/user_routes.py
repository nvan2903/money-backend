from flask import Blueprint, request, jsonify, current_app, send_file
from app.utils.auth import token_required
from app.utils.report_generator import ReportGenerator
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import pymongo
import pandas as pd
import json

user_bp = Blueprint('user', __name__, url_prefix='/api/user')

@user_bp.route('/profile', methods=['GET'])
@user_bp.route('/profile/', methods=['GET'])
@token_required
def get_profile(current_user):
    """Get the current user's profile."""
    user = current_app.mongo_db.users.find_one({'_id': ObjectId(current_user['sub'])})
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    user['_id'] = str(user['_id'])
    
    # Remove password
    if 'password' in user:
        del user['password']
    
    return jsonify(user), 200

@user_bp.route('/profile', methods=['PUT'])
@user_bp.route('/profile/', methods=['PUT'])
@token_required
def update_profile(current_user):
    """Update the current user's profile."""
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided'}), 400
    
    # Fields that can be updated
    allowed_fields = ['first_name', 'last_name', 'email']
    update_data = {}
    
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    # Email validation and uniqueness check
    if 'email' in update_data:
        # Check if email is already used by another user
        existing_user = current_app.mongo_db.users.find_one({
            'email': update_data['email'],
            '_id': {'$ne': ObjectId(current_user['sub'])}
        })
        
        if existing_user:
            return jsonify({'message': 'Email already in use'}), 409
    
    # Update user
    if update_data:
        current_app.mongo_db.users.update_one(
            {'_id': ObjectId(current_user['sub'])},
            {'$set': update_data}
        )
    
    return jsonify({'message': 'Profile updated successfully'}), 200

@user_bp.route('/change-password', methods=['PUT'])
@user_bp.route('/change-password/', methods=['PUT'])
@token_required
def change_password(current_user):
    """Change the current user's password."""
    data = request.get_json()
    
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({'message': 'Current password and new password are required'}), 400
    
    # Get user
    user = current_app.mongo_db.users.find_one({'_id': ObjectId(current_user['sub'])})
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    # Verify current password
    if not check_password_hash(user['password'], data['current_password']):
        return jsonify({'message': 'Current password is incorrect'}), 401
    
    # Validate new password strength
    if len(data['new_password']) < 8:
        return jsonify({'message': 'Password must be at least 8 characters long'}), 400
    
    # Update password
    hashed_password = generate_password_hash(data['new_password'])
    
    current_app.mongo_db.users.update_one(
        {'_id': ObjectId(current_user['sub'])},
        {'$set': {'password': hashed_password}}
    )
    
    return jsonify({'message': 'Password changed successfully'}), 200

@user_bp.route('/dashboard', methods=['GET'])
@user_bp.route('/dashboard/', methods=['GET'])
@token_required
def get_dashboard(current_user):
    """Get dashboard statistics for the current user."""
    # Get date range
    date_range = request.args.get('range', 'month')  # 'month', 'year', 'all'
    
    # Set date filter based on range
    date_filter = {}
    today = datetime.utcnow()
    
    if date_range == 'month':
        # Start of current month
        start_date = datetime(today.year, today.month, 1)
        # Starting from next month, then subtract 1 day to get last day of current month
        end_date = (datetime(today.year, today.month + 1, 1) 
                    if today.month < 12 
                    else datetime(today.year + 1, 1, 1)) - timedelta(days=1)
        date_filter = {'date': {'$gte': start_date, '$lte': end_date}}
    elif date_range == 'year':
        # Start of current year
        start_date = datetime(today.year, 1, 1)
        # End of current year
        end_date = datetime(today.year, 12, 31)
        date_filter = {'date': {'$gte': start_date, '$lte': end_date}}
    
    # Base query for user's transactions
    base_query = {'user_id': current_user['sub']}
    
    if date_filter:
        base_query.update(date_filter)
    
    # Total income
    income_query = base_query.copy()
    income_query['type'] = 'income'
    total_income = sum(t['amount'] for t in current_app.mongo_db.transactions.find(income_query))
    
    # Total expense
    expense_query = base_query.copy()
    expense_query['type'] = 'expense'
    total_expense = sum(t['amount'] for t in current_app.mongo_db.transactions.find(expense_query))
    
    # Balance
    balance = total_income - total_expense
    
    # Category breakdown
    pipeline = [
        {'$match': expense_query},
        {'$group': {
            '_id': '$category_name',
            'total': {'$sum': '$amount'}
        }},
        {'$sort': {'total': -1}}
    ]
    
    category_breakdown = list(current_app.mongo_db.transactions.aggregate(pipeline))
    
    # Daily average
    if date_range == 'month' or date_range == 'year':
        days_in_period = (end_date - start_date).days + 1
        daily_avg = total_expense / days_in_period if days_in_period > 0 else 0
    else:
        # For 'all' range, calculate actual days from first to last transaction
        first_transaction = current_app.mongo_db.transactions.find_one(
            {'user_id': current_user['sub']},
            sort=[('date', pymongo.ASCENDING)]
        )
        
        if first_transaction:
            days_span = (today - first_transaction['date']).days + 1
            daily_avg = total_expense / days_span if days_span > 0 else 0
        else:
            daily_avg = 0
    
    # Recent transactions
    recent_transactions = list(
        current_app.mongo_db.transactions.find(base_query)
        .sort('date', pymongo.DESCENDING)
        .limit(5)
    )
    
    for transaction in recent_transactions:
        transaction['_id'] = str(transaction['_id'])
    
    # Monthly comparison (for year view)
    monthly_data = []
    
    if date_range == 'year':
        # Group by month
        pipeline = [
            {'$match': base_query},
            {'$project': {
                'month': {'$month': '$date'},
                'amount': '$amount',
                'type': '$type'
            }},
            {'$group': {
                '_id': {'month': '$month', 'type': '$type'},
                'total': {'$sum': '$amount'}
            }},
            {'$sort': {'_id.month': 1}}
        ]
        
        monthly_results = list(current_app.mongo_db.transactions.aggregate(pipeline))
        
        # Organize results by month
        months = {}
        for item in monthly_results:
            month = item['_id']['month']
            if month not in months:
                months[month] = {'income': 0, 'expense': 0}
            
            months[month][item['_id']['type']] = item['total']
        
        # Convert to list for the response
        for month, data in months.items():
            monthly_data.append({
                'month': month,
                'income': data['income'],
                'expense': data['expense'],
                'balance': data['income'] - data['expense']
            })
    
    return jsonify({
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'category_breakdown': category_breakdown,
        'daily_average': daily_avg,
        'recent_transactions': recent_transactions,
        'monthly_comparison': monthly_data
    }), 200

@user_bp.route('/delete-account', methods=['DELETE'])
@user_bp.route('/delete-account/', methods=['DELETE'])
@token_required
def delete_account(current_user):
    """Delete the current user's account."""
    data = request.get_json()
    
    if not data or not data.get('password'):
        return jsonify({'message': 'Password is required to delete your account'}), 400
    
    # Get user
    user = current_app.mongo_db.users.find_one({'_id': ObjectId(current_user['sub'])})
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    # Verify password
    if not check_password_hash(user['password'], data['password']):
        return jsonify({'message': 'Password is incorrect'}), 401
    
    # Delete user's transactions
    current_app.mongo_db.transactions.delete_many({'user_id': current_user['sub']})
    
    # Delete user's custom categories
    current_app.mongo_db.categories.delete_many({
        'user_id': current_user['sub'],
        'is_default': False
    })
    
    # Delete user
    current_app.mongo_db.users.delete_one({'_id': ObjectId(current_user['sub'])})
    
    return jsonify({'message': 'Account deleted successfully'}), 200

@user_bp.route('/reports/generate', methods=['POST'])
@user_bp.route('/reports/generate/', methods=['POST'])
@token_required
def generate_report(current_user):
    """Generate and export user's transaction report."""
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided'}), 400
    
    # Parameters
    export_format = data.get('format', 'excel')  # 'excel', 'csv', 'pdf'
    date_from = data.get('date_from')
    date_to = data.get('date_to')
    transaction_type = data.get('type')  # 'income', 'expense', or None for all
    category_id = data.get('category_id')
    
    # Build query
    query = {'user_id': current_user['sub']}
    
    if date_from or date_to:
        query['date'] = {}
        if date_from:
            query['date']['$gte'] = datetime.fromisoformat(date_from)
        if date_to:
            query['date']['$lte'] = datetime.fromisoformat(date_to)
    
    if transaction_type:
        query['type'] = transaction_type
    
    if category_id:
        query['category_id'] = category_id
    
    # Get transactions
    transactions = list(current_app.mongo_db.transactions.find(query).sort('date', pymongo.DESCENDING))
    
    # Convert ObjectId to string
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
        transaction['date'] = transaction['date'].strftime('%Y-%m-%d')
        transaction['created_at'] = transaction['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    if not transactions:
        return jsonify({'message': 'No transactions found for the specified criteria'}), 404
    
    try:
        if export_format == 'excel':
            file_buffer, filename = ReportGenerator.generate_excel_report(transactions, "transactions")
            return send_file(
                file_buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        elif export_format == 'csv':
            file_buffer, filename = ReportGenerator.generate_csv_report(transactions)
            return send_file(
                file_buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='text/csv'
            )
        
        elif export_format == 'pdf':
            file_buffer, filename = ReportGenerator.generate_pdf_report(transactions, "transactions")
            return send_file(
                file_buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )
        
        else:
            return jsonify({'message': 'Invalid export format. Use excel, csv, or pdf'}), 400
    
    except Exception as e:
        return jsonify({'message': f'Error generating report: {str(e)}'}), 500

@user_bp.route('/statistics', methods=['GET'])
@user_bp.route('/statistics/', methods=['GET'])
@token_required
def get_statistics(current_user):
    """Get detailed statistics for the current user."""
    # Parameters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Build base query
    base_query = {'user_id': current_user['sub']}
    
    if date_from or date_to:
        base_query['date'] = {}
        if date_from:
            base_query['date']['$gte'] = datetime.fromisoformat(date_from)
        if date_to:
            base_query['date']['$lte'] = datetime.fromisoformat(date_to)
    
    # Income vs Expense totals
    income_total = sum(t['amount'] for t in current_app.mongo_db.transactions.find({**base_query, 'type': 'income'}))
    expense_total = sum(t['amount'] for t in current_app.mongo_db.transactions.find({**base_query, 'type': 'expense'}))
    
    # Category breakdown (expenses)
    expense_pipeline = [
        {'$match': {**base_query, 'type': 'expense'}},
        {'$group': {
            '_id': '$category_name',
            'total': {'$sum': '$amount'},
            'count': {'$sum': 1}
        }},
        {'$sort': {'total': -1}}
    ]
    expense_by_category = list(current_app.mongo_db.transactions.aggregate(expense_pipeline))
    
    # Category breakdown (income)
    income_pipeline = [
        {'$match': {**base_query, 'type': 'income'}},
        {'$group': {
            '_id': '$category_name',
            'total': {'$sum': '$amount'},
            'count': {'$sum': 1}
        }},
        {'$sort': {'total': -1}}
    ]
    income_by_category = list(current_app.mongo_db.transactions.aggregate(income_pipeline))
    
    # Monthly trend
    monthly_pipeline = [
        {'$match': base_query},
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
    
    # Organize monthly data
    monthly_trends = {}
    for item in monthly_data:
        key = f"{item['_id']['year']}-{item['_id']['month']:02d}"
        if key not in monthly_trends:
            monthly_trends[key] = {'income': 0, 'expense': 0}
        monthly_trends[key][item['_id']['type']] = item['total']
    
    # Convert to list
    monthly_list = []
    for month, data in sorted(monthly_trends.items()):
        monthly_list.append({
            'month': month,
            'income': data['income'],
            'expense': data['expense'],
            'balance': data['income'] - data['expense']
        })
    
    # Transaction count
    total_transactions = current_app.mongo_db.transactions.count_documents(base_query)
    
    # Average transaction amounts
    avg_income = income_total / max(1, len(list(current_app.mongo_db.transactions.find({**base_query, 'type': 'income'}))))
    avg_expense = expense_total / max(1, len(list(current_app.mongo_db.transactions.find({**base_query, 'type': 'expense'}))))
    
    return jsonify({
        'summary': {
            'total_income': income_total,
            'total_expense': expense_total,
            'balance': income_total - expense_total,
            'transaction_count': total_transactions,
            'average_income': avg_income,
            'average_expense': avg_expense
        },
        'expense_by_category': expense_by_category,
        'income_by_category': income_by_category,
        'monthly_trends': monthly_list
    }), 200

@user_bp.route('/charts/category-breakdown', methods=['GET'])
@user_bp.route('/charts/category-breakdown/', methods=['GET'])
@token_required
def get_category_chart(current_user):
    """Get category breakdown chart data."""
    transaction_type = request.args.get('type', 'expense')  # 'income' or 'expense'
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Build query
    query = {'user_id': current_user['sub'], 'type': transaction_type}
    
    if date_from or date_to:
        query['date'] = {}
        if date_from:
            query['date']['$gte'] = datetime.fromisoformat(date_from)
        if date_to:
            query['date']['$lte'] = datetime.fromisoformat(date_to)
    
    # Get category breakdown
    pipeline = [
        {'$match': query},
        {'$group': {
            '_id': '$category_name',
            'amount': {'$sum': '$amount'}
        }},
        {'$sort': {'amount': -1}}
    ]
    
    data = list(current_app.mongo_db.transactions.aggregate(pipeline))
    
    # Format for chart
    chart_data = [{'category': item['_id'], 'amount': item['amount']} for item in data]
    
    # Generate chart
    chart_base64 = ReportGenerator.generate_chart_base64(
        chart_data, 
        'pie', 
        f'{transaction_type.title()} by Category'
    )
    
    return jsonify({
        'data': chart_data,
        'chart': chart_base64
    }), 200

@user_bp.route('/charts/monthly-trend', methods=['GET'])
@user_bp.route('/charts/monthly-trend/', methods=['GET'])
@token_required
def get_monthly_trend_chart(current_user):
    """Get monthly trend chart data."""
    # Get last 12 months of data
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=365)
    
    query = {
        'user_id': current_user['sub'],
        'date': {'$gte': start_date, '$lte': end_date}
    }
    
    # Group by month and type
    pipeline = [
        {'$match': query},
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
    
    monthly_data = list(current_app.mongo_db.transactions.aggregate(pipeline))
    
    # Organize data
    trends = {}
    for item in monthly_data:
        key = f"{item['_id']['year']}-{item['_id']['month']:02d}"
        if key not in trends:
            trends[key] = {'income': 0, 'expense': 0}
        trends[key][item['_id']['type']] = item['total']
    
    # Format for chart
    chart_data = []
    for month in sorted(trends.keys()):
        chart_data.append({
            'date': month,
            'amount': trends[month]['expense']  # Show expense trend
        })
    
    # Generate chart
    chart_base64 = ReportGenerator.generate_chart_base64(
        chart_data, 
        'line', 
        'Monthly Expense Trend'
    )
    
    return jsonify({
        'data': trends,
        'chart': chart_base64
    }), 200
