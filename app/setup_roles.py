from app import app, db
from app.models import User, Role
from werkzeug.security import generate_password_hash
import sqlalchemy as sa

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
            role = db.session.scalar(sa.select(Role).where(Role.name == role_data['name']))
            if role is None:
                role = Role(name=role_data['name'], description=role_data['description'])
                db.session.add(role)
        
        db.session.commit()
        print("Default roles initialized")

def create_admin_user(username, email, password):
    """Create an admin user if it doesn't exist"""
    with app.app_context():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            # Assign admin role - using SQLAlchemy association
            admin_role = db.session.scalar(sa.select(Role).where(Role.name == 'admin'))
            if admin_role:
                # Create association between user and role
                stmt = sa.insert(user_roles).values(user_id=user.id, role_id=admin_role.id)
                db.session.execute(stmt)
                db.session.commit()
                
            print(f"Admin user '{username}' created")
        else:
            print(f"User '{username}' already exists")

if __name__ == '__main__':
    # Initialize roles
    init_roles()
    
    # Create admin user
    create_admin_user('admin', 'admin@example.com', 'change_me_immediately')