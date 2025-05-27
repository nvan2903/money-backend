from datetime import datetime
from bson import ObjectId

class Category:
    """Category model for MongoDB."""
    
    def __init__(self, name, type, user_id=None, is_default=False, created_at=None):
        self.name = name
        self.type = type  # 'income' or 'expense'
        self.user_id = user_id  # None for default categories
        self.is_default = is_default
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self):
        """Convert Category object to dictionary."""
        return {
            'name': self.name,
            'type': self.type,
            'user_id': self.user_id,
            'is_default': self.is_default,
            'created_at': self.created_at
        }
    
    @staticmethod
    def from_dict(category_dict):
        """Create Category object from dictionary."""
        return Category(
            name=category_dict['name'],
            type=category_dict['type'],
            user_id=category_dict.get('user_id'),
            is_default=category_dict.get('is_default', False),
            created_at=category_dict.get('created_at')
        )
