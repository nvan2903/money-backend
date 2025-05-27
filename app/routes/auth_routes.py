from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.user import User
from app.utils.auth import generate_token
from app.utils.email_service import (
    generate_verification_token, send_verification_email, send_password_reset_email,
    save_verification_token, save_password_reset_token, verify_token, delete_verification_token
)
try:
    from bson import ObjectId
except ImportError:
    from pymongo.objectid import ObjectId
import re
import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def is_valid_email(email):
    """Check if email is valid."""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))

def is_strong_password(password):
    """Check if password meets strength requirements."""
    if len(password) < 8:
        return False
    return any(c.isdigit() for c in password) and any(c.isalpha() for c in password)

@auth_bp.route('/register', methods=['POST'])
@auth_bp.route('/register/', methods=['POST'])
def register():
    """Register a new user."""
    data = request.get_json()
    
    # Validate input
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Validate email format
    if not is_valid_email(data.get('email')):
        return jsonify({'message': 'Invalid email format'}), 400
    
    # Check if username already exists
    if current_app.mongo_db.users.find_one({'username': data.get('username')}):
        return jsonify({'message': 'Username already exists'}), 409
    
    # Check if email already exists
    if current_app.mongo_db.users.find_one({'email': data.get('email')}):
        return jsonify({'message': 'Email already exists'}), 409
    
    # Validate password strength
    if not is_strong_password(data.get('password')):
        return jsonify({'message': 'Password must be at least 8 characters and include both letters and numbers'}), 400
    
    # Hash the password
    hashed_password = generate_password_hash(data.get('password'))
    
    # Generate email verification token
    verification_token = generate_verification_token()
    
    # Create user object
    user = User(
        username=data.get('username'),
        email=data.get('email'),
        password=hashed_password,
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        email_verified=False,
        email_verification_token=verification_token
    )
    
    # Save user to database
    user_dict = user.to_dict()
    user_dict['password'] = hashed_password
    result = current_app.mongo_db.users.insert_one(user_dict)
    
    # Save verification token
    save_verification_token(result.inserted_id, verification_token)
    
    # Send verification email
    success, message = send_verification_email(
        data.get('email'), 
        data.get('username'), 
        verification_token
    )
    
    if not success:
        # Delete the user if email sending fails
        current_app.mongo_db.users.delete_one({'_id': result.inserted_id})
        return jsonify({'message': 'Failed to send verification email. Please try again.'}), 500
    
    # Create default categories for the user
    default_categories = [
        {'name': 'Salary', 'type': 'income', 'user_id': str(result.inserted_id), 'is_default': True},
        {'name': 'Bonus', 'type': 'income', 'user_id': str(result.inserted_id), 'is_default': True},
        {'name': 'Food', 'type': 'expense', 'user_id': str(result.inserted_id), 'is_default': True},
        {'name': 'Transportation', 'type': 'expense', 'user_id': str(result.inserted_id), 'is_default': True},
        {'name': 'Housing', 'type': 'expense', 'user_id': str(result.inserted_id), 'is_default': True},
        {'name': 'Entertainment', 'type': 'expense', 'user_id': str(result.inserted_id), 'is_default': True},
        {'name': 'Utilities', 'type': 'expense', 'user_id': str(result.inserted_id), 'is_default': True},
    ]
    
    if default_categories:
        current_app.mongo_db.categories.insert_many(default_categories)
    
    return jsonify({
        'message': 'User registered successfully. Please check your email to verify your account.',
        'user_id': str(result.inserted_id),
        'email_verification_required': True
    }), 201

@auth_bp.route('/login', methods=['POST'])
@auth_bp.route('/login/', methods=['POST'])
def login():
    """Log in a user."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'message': 'No data provided'}), 400
        
        # Check if username/email and password are provided
        username_or_email = data.get('username') or data.get('email')
        password = data.get('password')
        
        if not username_or_email or not password:
            return jsonify({'message': 'Username/email and password are required'}), 400
        
        username_or_email = username_or_email.strip()
        
        # Find user by username or email
        user = None
        if '@' in username_or_email:
            # Search by email (case insensitive)
            user = current_app.mongo_db.users.find_one({'email': username_or_email.lower()})
        else:
            # Search by username (case insensitive)
            user = current_app.mongo_db.users.find_one({'username': {'$regex': f'^{username_or_email}$', '$options': 'i'}})
        
        if not user:
            return jsonify({'message': 'Invalid username/email or password'}), 401
        
        # Check if user is active
        if not user.get('is_active', True):
            return jsonify({'message': 'Account is deactivated. Please contact support.'}), 403
        
        # Verify password first
        if not check_password_hash(user['password'], password):
            return jsonify({'message': 'Invalid username/email or password'}), 401
        
        # Check if email is verified
        if not user.get('email_verified', False):
            return jsonify({
                'message': 'Please verify your email address before logging in. Check your email inbox for the verification link.',
                'email_verification_required': True,
                'email': user['email']
            }), 403
        
        # Generate token
        token = generate_token(user['_id'], user.get('role', 'user'))
        
        current_app.logger.info(f"User {user['username']} logged in successfully")
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': str(user['_id']),
                'username': user['username'],
                'email': user['email'],
                'first_name': user.get('first_name'),
                'last_name': user.get('last_name'),
                'role': user.get('role', 'user')
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in login: {str(e)}")
        return jsonify({'message': 'An error occurred during login'}), 500

@auth_bp.route('/forgot-password', methods=['POST'])
@auth_bp.route('/forgot-password/', methods=['POST'])
def forgot_password():
    """Send password reset email."""
    try:
        data = request.get_json()
        current_app.logger.info(f"Forgot password request: {data}")
        
        if not data or not data.get('email'):
            current_app.logger.warning("Forgot password request missing email")
            return jsonify({'message': 'Email is required'}), 400
        
        email = data.get('email').strip().lower()
        
        # Validate email format
        if not is_valid_email(email):
            return jsonify({'message': 'Invalid email format'}), 400
        
        # Find user by email
        user = current_app.mongo_db.users.find_one({'email': email})
        
        if not user:
            current_app.logger.warning(f"Forgot password request for non-existent email: {email}")
            # Return success message for security (don't reveal if email exists)
            return jsonify({'message': 'If the email exists, a password reset link has been sent'}), 200
        
        # Check if email is verified
        if not user.get('email_verified', False):
            return jsonify({'message': 'Please verify your email address first. Check your inbox for verification email.'}), 400
        
        # Generate reset token
        reset_token = generate_verification_token()
        
        # Save reset token
        save_password_reset_token(user['_id'], reset_token)
        
        # Send reset email
        success, message = send_password_reset_email(
            email, 
            user.get('username', 'User'), 
            reset_token
        )
        
        if success:
            current_app.logger.info(f"Password reset email sent successfully to: {email}")
            return jsonify({'message': 'Password reset link sent to email'}), 200
        else:
            current_app.logger.error(f"Failed to send password reset email to {email}: {message}")
            return jsonify({'message': 'Error sending email', 'error': message}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error in forgot_password: {str(e)}")
        return jsonify({'message': 'An error occurred while processing your request'}), 500

@auth_bp.route('/reset-password', methods=['POST'])
@auth_bp.route('/reset-password/', methods=['POST'])
def reset_password():
    """Reset password with token."""
    data = request.get_json()
    
    if not data or not data.get('token') or not data.get('password'):
        return jsonify({'message': 'Token and password are required'}), 400
    
    token = data.get('token')
    password = data.get('password')
    
    # Validate password strength
    if not is_strong_password(password):
        return jsonify({'message': 'Password must be at least 8 characters and include both letters and numbers'}), 400
    
    # Find reset token
    reset_data = current_app.mongo_db.password_resets.find_one({
        'token': token,
        'expires_at': {'$gt': datetime.datetime.utcnow()}
    })
    
    if not reset_data:
        return jsonify({'message': 'Invalid or expired token'}), 400
      # Update user password
    user_id = reset_data['user_id']
    hashed_password = generate_password_hash(password)
    
    # Get user info for notification
    user = current_app.mongo_db.users.find_one({'_id': ObjectId(user_id)})
    
    current_app.mongo_db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {'password': hashed_password}}
    )
    
    # Delete used token
    current_app.mongo_db.password_resets.delete_one({'_id': reset_data['_id']})
    
    # Send password change notification
    if user:
        from app.utils.email_service import send_password_change_notification
        send_password_change_notification(
            user['email'], 
            user.get('username', 'User')
        )
    
    return jsonify({'message': 'Password reset successful'}), 200

@auth_bp.route('/verify-email', methods=['GET'])
def verify_email():
    """Verify email with token."""
    try:
        token = request.args.get('token')
        current_app.logger.info(f"Email verification attempt with token: {token[:20]}..." if token else "No token provided")
        
        if not token:
            return jsonify({'message': 'Verification token is required'}), 400
        
        # First, check if token exists and get its status
        token_exists = current_app.mongo_db.email_verifications.find_one({
            'token': token,
            'type': 'email_verification'
        })
        
        if not token_exists:
            current_app.logger.warning(f"Token not found: {token[:20]}...")
            return jsonify({'message': 'Invalid verification token'}), 400
        
        # Check if token is already used
        if token_exists.get('used', False):
            current_app.logger.warning(f"Token already used: {token[:20]}...")
            # Check if user is already verified
            user = current_app.mongo_db.users.find_one({'_id': ObjectId(token_exists['user_id'])})
            if user and user.get('email_verified', False):
                return jsonify({'message': 'Email is already verified. You can now log in.'}), 200
            else:
                return jsonify({'message': 'This verification link has already been used'}), 400
        
        # Check if token is expired
        if token_exists.get('expires_at', datetime.datetime.utcnow()) <= datetime.datetime.utcnow():
            current_app.logger.warning(f"Token expired: {token[:20]}...")
            return jsonify({'message': 'Verification link has expired. Please request a new one.'}), 400
        
        # Token is valid, mark as used first to prevent race conditions
        mark_result = current_app.mongo_db.email_verifications.update_one(
            {
                '_id': token_exists['_id'],
                'used': False  # Only update if not already used
            },
            {'$set': {'used': True}}
        )
        
        if mark_result.modified_count == 0:
            current_app.logger.warning(f"Token was already used by another request: {token[:20]}...")
            return jsonify({'message': 'This verification link has already been used'}), 400
        
        # Update user email verification status
        user_id = token_exists['user_id']
        result = current_app.mongo_db.users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {'email_verified': True},
                '$unset': {'email_verification_token': 1}
            }
        )
        
        if result.modified_count == 0:
            # Check if user exists and is already verified
            user = current_app.mongo_db.users.find_one({'_id': ObjectId(user_id)})
            if user and user.get('email_verified', False):
                current_app.logger.info(f"User already verified: {user_id}")
                return jsonify({'message': 'Email is already verified. You can now log in.'}), 200
            else:
                current_app.logger.error(f"User not found: {user_id}")
                return jsonify({'message': 'User not found'}), 404
        
        current_app.logger.info(f"Email verified successfully for user: {user_id}")
        return jsonify({'message': 'Email verified successfully. You can now log in.'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in verify_email: {str(e)}")
        return jsonify({'message': 'An error occurred during email verification'}), 500

@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend email verification."""
    try:
        data = request.get_json()
        
        if not data or not data.get('email'):
            return jsonify({'message': 'Email is required'}), 400
        
        email = data.get('email').strip().lower()
        
        # Validate email format
        if not is_valid_email(email):
            return jsonify({'message': 'Invalid email format'}), 400
        
        # Find user by email
        user = current_app.mongo_db.users.find_one({'email': email})
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Check if already verified
        if user.get('email_verified', False):
            return jsonify({'message': 'Email is already verified. You can now log in.'}), 400
        
        # Check rate limiting (optional: prevent spam)
        # This could be enhanced with a proper rate limiting mechanism
        
        # Generate new verification token
        verification_token = generate_verification_token()
        
        # Update user with new token
        current_app.mongo_db.users.update_one(
            {'_id': user['_id']},
            {'$set': {'email_verification_token': verification_token}}
        )
        
        # Save verification token
        save_verification_token(user['_id'], verification_token)
        
        # Send verification email
        success, message = send_verification_email(
            email, 
            user.get('username', 'User'), 
            verification_token
        )
        
        if success:
            current_app.logger.info(f"Verification email resent successfully to: {email}")
            return jsonify({'message': 'Verification email sent successfully. Please check your inbox.'}), 200
        else:
            current_app.logger.error(f"Failed to resend verification email to {email}: {message}")
            return jsonify({'message': 'Error sending email', 'error': message}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error in resend_verification: {str(e)}")
        return jsonify({'message': 'An error occurred while sending verification email'}), 500
