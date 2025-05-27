from datetime import datetime
from bson import ObjectId

class Transaction:
    """Transaction model for MongoDB."""
    
    def __init__(self, user_id, amount, type, category_id, category_name=None, 
                 date=None, note=None, created_at=None):
        self.user_id = user_id
        self.amount = float(amount)
        self.type = type  # 'income' or 'expense'
        self.category_id = category_id
        self.category_name = category_name
        self.date = date or datetime.utcnow()
        self.note = note
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self):
        """Convert Transaction object to dictionary."""
        return {
            'user_id': self.user_id,
            'amount': self.amount,
            'type': self.type,
            'category_id': self.category_id,
            'category_name': self.category_name,
            'date': self.date,
            'note': self.note,
            'created_at': self.created_at
        }
    
    @staticmethod
    def from_dict(transaction_dict):
        """Create Transaction object from dictionary."""
        return Transaction(
            user_id=transaction_dict['user_id'],
            amount=transaction_dict['amount'],
            type=transaction_dict['type'],
            category_id=transaction_dict['category_id'],
            category_name=transaction_dict.get('category_name'),
            date=transaction_dict.get('date'),
            note=transaction_dict.get('note'),
            created_at=transaction_dict.get('created_at')
        )
