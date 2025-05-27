from datetime import datetime
from bson import ObjectId

class User:
    """User model for MongoDB."""
    def __init__(self, username, email, password, first_name=None, last_name=None, 
                 role='user', created_at=None, is_active=True, email_verified=False, 
                 email_verification_token=None):
        self.username = username
        self.email = email
        self.password = password  # This should be hashed before storing
        self.first_name = first_name
        self.last_name = last_name
        self.role = role
        self.created_at = created_at or datetime.utcnow()
        self.is_active = is_active
        self.email_verified = email_verified
        self.email_verification_token = email_verification_token
    
    def to_dict(self):
        """Convert User object to dictionary."""
        return {
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role,
            'created_at': self.created_at,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'email_verification_token': self.email_verification_token
        }
    
    @staticmethod
    def from_dict(user_dict):
        """Create User object from dictionary."""
        return User(
            username=user_dict['username'],
            email=user_dict['email'],
            password=user_dict.get('password'),
            first_name=user_dict.get('first_name'),
            last_name=user_dict.get('last_name'),
            role=user_dict.get('role', 'user'),
            created_at=user_dict.get('created_at'),
            is_active=user_dict.get('is_active', True)
        )
