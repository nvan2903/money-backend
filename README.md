# Money Management Backend

This project serves as the backend for a money management application, built using Flask and MongoDB. It provides a RESTful API for the frontend to interact with.

## Features

- User authentication with JWT tokens
- Transaction management (income and expenses)
- Category management
- Statistical analysis of financial data
- Admin panel for user and system management

## Prerequisites

- Python 3.8+
- MongoDB

## Installation

1. Clone the repository
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Configure the environment variables in `.env` file:
   ```
   FLASK_APP=app
   FLASK_ENV=development
   SECRET_KEY=your_secret_key_here
   MONGO_URI=mongodb://localhost:27017
   DATABASE_NAME=money_management
   MAIL_SERVER=smtp.example.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=your_email@example.com
   MAIL_PASSWORD=your_email_password
   ```

## Running the Application

```
python run.py
```

The API will be available at http://127.0.0.1:5000/

## API Endpoints

### Authentication
- POST /api/auth/register - Register a new user
- POST /api/auth/login - Login a user
- POST /api/auth/forgot-password - Request password reset
- POST /api/auth/reset-password - Reset password with token

### User Profile
- GET /api/user/profile - Get user profile
- PUT /api/user/profile - Update user profile
- PUT /api/user/change-password - Change password
- DELETE /api/user/delete-account - Delete user account
- GET /api/user/dashboard - Get user dashboard statistics

### Transactions
- POST /api/transactions - Create a new transaction
- GET /api/transactions - Get all transactions
- GET /api/transactions/:id - Get a specific transaction
- PUT /api/transactions/:id - Update a transaction
- DELETE /api/transactions/:id - Delete a transaction

### Categories
- POST /api/categories - Create a new category
- GET /api/categories - Get all categories
- GET /api/categories/:id - Get a specific category
- PUT /api/categories/:id - Update a category
- DELETE /api/categories/:id - Delete a category

### Admin
- GET /api/admin/users - Get all users
- GET /api/admin/users/:id - Get a specific user
- PUT /api/admin/users/:id/toggle-status - Toggle user status
- DELETE /api/admin/users/:id - Delete a user
- GET /api/admin/transactions - Get all transactions
- GET /api/admin/stats - Get system statistics
