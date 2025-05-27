import secrets
import datetime
from flask import current_app
try:
    from flask_mail import Message
except ImportError:
    Message = None
import uuid

def get_mail():
    """Get mail instance from app."""
    from app import mail
    return mail

def generate_verification_token():
    """Generate a secure verification token."""
    return secrets.token_urlsafe(32)

def save_verification_token(user_id, token):
    """Save email verification token to database."""
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    
    verification_data = {
        'user_id': str(user_id),
        'token': token,
        'type': 'email_verification',
        'created_at': datetime.datetime.utcnow(),
        'expires_at': expires_at,
        'used': False
    }
    
    # Remove any existing verification tokens for this user
    current_app.mongo_db.email_verifications.delete_many({
        'user_id': str(user_id),
        'type': 'email_verification'
    })
    
    current_app.mongo_db.email_verifications.insert_one(verification_data)

def save_password_reset_token(user_id, token):
    """Save password reset token to database."""
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    
    reset_data = {
        'user_id': str(user_id),
        'token': token,
        'type': 'password_reset',
        'created_at': datetime.datetime.utcnow(),
        'expires_at': expires_at,
        'used': False
    }
    
    # Remove any existing reset tokens for this user
    current_app.mongo_db.password_resets.delete_many({
        'user_id': str(user_id)
    })
    
    current_app.mongo_db.password_resets.insert_one(reset_data)

def verify_token(token, token_type='email_verification'):
    """Verify and validate a token."""
    if token_type == 'email_verification':
        collection = current_app.mongo_db.email_verifications
    else:
        collection = current_app.mongo_db.password_resets
    
    token_data = collection.find_one({
        'token': token,
        'type': token_type,
        'expires_at': {'$gt': datetime.datetime.utcnow()},
        'used': False
    })
    
    return token_data

def delete_verification_token(token):
    """Delete or mark verification token as used."""
    current_app.mongo_db.email_verifications.update_one(
        {'token': token},
        {'$set': {'used': True}}
    )

def send_verification_email(email, username, token):
    """Send email verification email."""
    try:
        if Message is None:
            current_app.logger.error("Flask-Mail not installed")
            return False, "Flask-Mail not installed"
            
        mail = get_mail()
        if mail is None:
            current_app.logger.error("Mail instance not available")
            return False, "Mail service not configured"
            
        # Frontend URL - you may need to adjust this based on your frontend setup
        frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3000')
        verification_url = f"{frontend_url}/verify-email?token={token}"
        
        current_app.logger.info(f"Sending verification email to {email} with URL: {verification_url}")
        
        msg = Message(
            'Xác thực tài khoản - Money Management App',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email]
        )
        
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">Chào mừng đến với Money Management App!</h2>
            
            <p>Xin chào <strong>{username}</strong>,</p>
            
            <p>Cảm ơn bạn đã đăng ký tài khoản. Để hoàn tất quá trình đăng ký, vui lòng xác thực địa chỉ email của bạn bằng cách nhấp vào liên kết bên dưới:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{verification_url}" 
                   style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                   Xác thực email
                </a>
            </div>
            
            <p>Hoặc copy và dán liên kết sau vào trình duyệt của bạn:</p>
            <p style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; word-break: break-all;">
                {verification_url}
            </p>
            
            <p><strong>Lưu ý:</strong> Liên kết này sẽ hết hạn sau 24 giờ.</p>
            
            <p>Nếu bạn không tạo tài khoản này, vui lòng bỏ qua email này.</p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="color: #7f8c8d; font-size: 12px;">
                Email này được gửi tự động, vui lòng không trả lời.<br>
                © 2025 Money Management App. All rights reserved.
            </p>        </div>
        """
        
        mail.send(msg)
        current_app.logger.info(f"Email verification sent successfully to {email}")
        return True, "Email verification sent successfully"
        
    except Exception as e:
        current_app.logger.error(f"Error sending verification email to {email}: {str(e)}")
        return False, f"Error sending email: {str(e)}"

def send_password_reset_email(email, username, token):
    """Send password reset email."""
    try:
        if Message is None:
            return False, "Flask-Mail not installed"
            
        mail = get_mail()
        # Frontend URL - you may need to adjust this based on your frontend setup
        frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3000')
        reset_url = f"{frontend_url}/reset-password?token={token}"
        
        msg = Message(
            'Đặt lại mật khẩu - Money Management App',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email]
        )
        
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #e74c3c;">Đặt lại mật khẩu</h2>
            
            <p>Xin chào <strong>{username}</strong>,</p>
            
            <p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn. Để đặt lại mật khẩu, vui lòng nhấp vào liên kết bên dưới:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" 
                   style="background-color: #e74c3c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                   Đặt lại mật khẩu
                </a>
            </div>
            
            <p>Hoặc copy và dán liên kết sau vào trình duyệt của bạn:</p>
            <p style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; word-break: break-all;">
                {reset_url}
            </p>
            
            <p><strong>Lưu ý quan trọng:</strong></p>
            <ul>
                <li>Liên kết này sẽ hết hạn sau 1 giờ</li>
                <li>Liên kết chỉ có thể sử dụng một lần</li>
                <li>Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này</li>
            </ul>
            
            <p>Để bảo mật tài khoản, không chia sẻ liên kết này với bất kỳ ai.</p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="color: #7f8c8d; font-size: 12px;">
                Email này được gửi tự động, vui lòng không trả lời.<br>
                © 2025 Money Management App. All rights reserved.
            </p>
        </div>
        """
        
        mail.send(msg)
        return True, "Password reset email sent successfully"
        
    except Exception as e:
        current_app.logger.error(f"Error sending password reset email: {str(e)}")
        return False, f"Error sending email: {str(e)}"

def send_password_change_notification(email, username):
    """Send notification when password is successfully changed."""
    try:
        if Message is None:
            return False, "Flask-Mail not installed"
            
        mail = get_mail()
        msg = Message(
            'Mật khẩu đã được thay đổi - Money Management App',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email]
        )
        
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #27ae60;">Mật khẩu đã được thay đổi thành công</h2>
            
            <p>Xin chào <strong>{username}</strong>,</p>
            
            <p>Mật khẩu của tài khoản Money Management App đã được thay đổi thành công vào lúc:</p>
            <p><strong>{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</strong></p>
            
            <p>Nếu bạn không thực hiện thay đổi này, vui lòng liên hệ với chúng tôi ngay lập tức để bảo vệ tài khoản của bạn.</p>
            
            <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p style="margin: 0; color: #856404;">
                    <strong>Lời khuyên bảo mật:</strong><br>
                    • Sử dụng mật khẩu mạnh và duy nhất<br>
                    • Không chia sẻ thông tin đăng nhập với ai<br>
                    • Đăng xuất khỏi các thiết bị công cộng
                </p>
            </div>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="color: #7f8c8d; font-size: 12px;">
                Email này được gửi tự động, vui lòng không trả lời.<br>
                © 2025 Money Management App. All rights reserved.
            </p>
        </div>
        """
        
        mail.send(msg)
        return True, "Password change notification sent"
        
    except Exception as e:
        current_app.logger.error(f"Error sending password change notification: {str(e)}")
        return False, f"Error sending notification: {str(e)}"