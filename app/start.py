#!/usr/bin/env python
import os
import subprocess
import time
from app import app, db
from app.models import User, Role, user_roles
import sqlalchemy as sa

def run_migrations():
    """Run database migrations"""
    print("Running database migrations...")
    try:
        subprocess.run(["flask", "db", "upgrade"], check=True)
        print("Migrations completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error running migrations: {e}")
        raise

def init_roles():
    """Initialize default roles if they don't exist"""
    print("Initializing default roles...")
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

def create_admin_user():
    """Create an admin user if it doesn't exist and ADMIN_* env vars are set"""
    username = os.environ.get('ADMIN_USERNAME')
    email = os.environ.get('ADMIN_EMAIL')
    password = os.environ.get('ADMIN_PASSWORD')
    
    if not all([username, email, password]):
        print("Admin user environment variables not set. Skipping admin user creation.")
        return
    
    print(f"Creating admin user {username}...")
    with app.app_context():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            # Assign admin role
            admin_role = db.session.scalar(sa.select(Role).where(Role.name == 'admin'))
            if admin_role:
                # Create association between user and role
                stmt = sa.insert(user_roles).values(user_id=user.id, role_id=admin_role.id)
                db.session.execute(stmt)
                db.session.commit()
                
            print(f"Admin user '{username}' created")
        else:
            print(f"User '{username}' already exists")

def init_app():
    """Initialize the application on first run"""
    # Wait for database to be ready
    max_retries = 30
    retries = 0
    
    while retries < max_retries:
        try:
            # Try to connect to the database
            with app.app_context():
                db.session.execute(sa.text("SELECT 1"))
                print("Database connection successful")
                break
        except Exception as e:
            retries += 1
            print(f"Database connection attempt {retries}/{max_retries} failed: {e}")
            if retries >= max_retries:
                raise Exception("Could not connect to database after maximum retries")
            time.sleep(2)
    
    # Run database migrations
    run_migrations()
    
    # Initialize default roles
    init_roles()
    
    # Create admin user if env vars are set
    create_admin_user()
    
    print("Application initialization completed")

if __name__ == "__main__":
    # Initialize the application
    init_app()
    
    # Get gunicorn command parameters from environment or use defaults
    workers = os.environ.get("GUNICORN_WORKERS", "3")
    host = os.environ.get("HOST", "0.0.0.0")
    port = os.environ.get("PORT", "5000")
    
    # Start gunicorn
    cmd = [
        "gunicorn", 
        "--workers", workers,
        "--bind", f"{host}:{port}",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "wsgi:app"
    ]
    
    print(f"Starting Gunicorn with command: {' '.join(cmd)}")
    subprocess.run(cmd)