#!/usr/bin/env python
"""
Local development setup script
Run this before using 'flask run' for local development
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_local_environment():
    """Setup the local development environment"""
    
    # Get the base directory
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    
    print("Setting up local development environment...")
    
    # Create instance directory if it doesn't exist
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir, exist_ok=True)
        print(f"Created instance directory: {instance_dir}")
    
    # Set environment variables for local development
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'development'
    
    # Make sure we're not using Docker paths locally
    if 'DATABASE_URL' in os.environ and '/data/' in os.environ['DATABASE_URL']:
        del os.environ['DATABASE_URL']
        print("Removed Docker DATABASE_URL from environment")
    
    # Initialize the database
    print("Initializing database...")
    try:
        # Set the Flask app environment variable
        os.environ['FLASK_APP'] = 'app.py'
        
        # Try to run flask db upgrade
        result = subprocess.run(['flask', 'db', 'upgrade'], 
                              capture_output=True, text=True, cwd=basedir)
        
        if result.returncode == 0:
            print("Database migrations completed successfully")
        else:
            print("Migration failed, trying to initialize database...")
            # If migrations fail, try to create all tables
            from app import app, db
            with app.app_context():
                db.create_all()
                print("Database tables created")
                
    except Exception as e:
        print(f"Error setting up database: {e}")
        print("You may need to run database initialization manually")
    
    # Create admin user if needed
    try:
        from app.models import User, Role
        from app import app, db
        import sqlalchemy as sa
        
        with app.app_context():
            # Check if admin user exists
            admin_user = db.session.scalar(sa.select(User).where(User.username == 'admin'))
            if not admin_user:
                # Create roles first
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
                
                # Create admin user
                admin_user = User(username='admin', email='admin@example.com')
                admin_user.set_password('admin123')  # Change this!
                db.session.add(admin_user)
                db.session.commit()
                
                # Assign admin role
                admin_role = db.session.scalar(sa.select(Role).where(Role.name == 'admin'))
                if admin_role:
                    admin_user.roles.append(admin_role)
                    db.session.commit()
                
                print("Created admin user (username: admin, password: admin123)")
                print("⚠️  IMPORTANT: Change the admin password after first login!")
            else:
                print("Admin user already exists")
                
    except Exception as e:
        print(f"Error creating admin user: {e}")
    
    print("\n✅ Local environment setup complete!")
    print("\nYou can now run:")
    print("  flask run")
    print("\nOr for development with auto-reload:")
    print("  flask run --debug")
    print("\nAccess the app at: http://localhost:5000")
    print("Default login: admin / admin123")

if __name__ == '__main__':
    setup_local_environment()