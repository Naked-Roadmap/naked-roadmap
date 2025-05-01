from app import app, db
from app.models import User, Role
import os

def init_roles():
    """Initialize default roles if they don't exist"""
    with app.app_context():
        default_roles = [
            {'name': 'admin', 'description': 'Administrator with full access'},
            {'name': 'manager', 'description': 'Manager with project oversight'},
            {'name': 'team_lead', 'description': 'Team leader with team management access'},
            {'name': 'team_member', 'description': 'Regular team member'}
        ]
        
        for role_data in default_roles:
            role = Role.query.filter_by(name=role_data['name']).first()
            if role is None:
                role = Role(name=role_data['name'], description=role_data['description'])
                db.session.add(role)
        
        db.session.commit()
        print("Default roles initialized")

def create_admin_user(username, email, password):
    """Create an admin user if it doesn't exist"""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            # Assign admin role
            admin_role = Role.query.filter_by(name='admin').first()
            if admin_role:
                user.roles.append(admin_role)
                db.session.commit()
                
            print(f"Admin user '{username}' created")
        else:
            print(f"User '{username}' already exists")

if __name__ == '__main__':
    # Initialize roles
    init_roles()
    
    # Create admin user
    create_admin_user('admin', 'admin@example.com', 'change_me_immediately')