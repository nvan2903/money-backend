import jwt
import datetime
from functools import wraps
from flask import request, jsonify, current_app
from bson.objectid import ObjectId

def generate_token(user_id, role='user'):
    """Generate a JWT token for authentication."""
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
        'iat': datetime.datetime.utcnow(),
        'sub': str(user_id),
        'role': role
    }
    return jwt.encode(
        payload,
        current_app.config.get('SECRET_KEY'),
        algorithm='HS256'
    )

def decode_token(token):
    """Decode a JWT token."""
    try:
        payload = jwt.decode(
            token,
            current_app.config.get('SECRET_KEY'),
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return {'error': 'Token expired. Please log in again.'}
    except jwt.InvalidTokenError:
        return {'error': 'Invalid token. Please log in again.'}

def token_required(f):
    """Decorator for views that require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Token is missing'}), 401
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            payload = decode_token(token)
            if 'error' in payload:
                return jsonify({'message': payload['error']}), 401
            
            # Get user from database
            user_id = payload['sub']
            user = current_app.mongo_db.users.find_one({'_id': ObjectId(user_id)})
            
            if not user:
                return jsonify({'message': 'User not found'}), 401
                
            if not user.get('is_active', True):
                return jsonify({'message': 'Account is deactivated'}), 401
            
        except Exception as e:
            return jsonify({'message': str(e)}), 401
            
        return f(payload, *args, **kwargs)
    
    return decorated

def admin_required(f):
    """Decorator for views that require admin privileges."""
    @wraps(f)
    def decorated(payload, *args, **kwargs):
        if payload.get('role') != 'admin':
            return jsonify({'message': 'Admin privilege required'}), 403
        return f(payload, *args, **kwargs)
    
    return decorated
