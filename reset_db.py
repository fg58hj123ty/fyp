from web_app import db, create_app, bcrypt 
from web_app.models.models import User, UserVoiceProfile
from datetime import datetime

app = create_app(db_reset=True)

with app.app_context():
    
    # Drop and recreate all tables
    db.drop_all()
    db.create_all()
    
    # Create admin user with specific details
    admin = User(
        username='admin',
        email='admin@voicepass.com',
        password=bcrypt.generate_password_hash('admin').decode('utf-8'),
        date_join=datetime.utcnow(),
        is_admin=True
    )
    
    # Add to database
    db.session.add(admin)
    db.session.commit()
    
    # Log the first admin activity
    admin.log_activity(
        activity_type='account_creation',
        status='success',
        details='Administrator account created'
    )
    
    print("\nAdmin account created successfully!")
    print("---------------------------------")
    print(f"Username: {admin.username}")
    print(f"Password: admin123")
    print(f"Email: {admin.email}")
    print(f"Admin Status: {admin.is_admin}")
    