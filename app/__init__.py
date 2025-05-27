from flask import Flask
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_mail import Mail
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# Initialize Flask extensions
bcrypt = Bcrypt()
mail = Mail()

def create_app():
    """Initialize the core application."""
    app = Flask(__name__, instance_relative_config=False)
    
    # Configure the app
    app.config.from_object('app.config.Config')
    
    # Initialize plugins
    CORS(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    
    # Initialize MongoDB connection
    mongo_uri = os.getenv('MONGO_URI')
    db_name = os.getenv('DATABASE_NAME')
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    # Make db accessible to the app
    app.mongo_db = db
    
    with app.app_context():
        # Include routes
        from app.routes import auth_routes, transaction_routes, category_routes, admin_routes, user_routes
        
        # Register blueprints
        app.register_blueprint(auth_routes.auth_bp)
        app.register_blueprint(transaction_routes.transaction_bp)
        app.register_blueprint(category_routes.category_bp)
        app.register_blueprint(admin_routes.admin_bp)
        app.register_blueprint(user_routes.user_bp)
        
        return app
