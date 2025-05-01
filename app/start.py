#!/usr/bin/env python
import os
import subprocess
import time
import sys
from app import app, db
from app.models import User, Role, user_roles
import sqlalchemy as sa

def setup_instance_directory():
    """Ensure the instance directory exists and has proper permissions"""
    print("Setting up instance directory...")
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    
    # Create the directory if it doesn't exist
    if not os.path.exists(instance_dir):
        print(f"Creating instance directory: {instance_dir}")
        os.makedirs(instance_dir, exist_ok=True)
    
    # Set permissions
    try:
        print(f"Setting permissions on {instance_dir}")
        os.chmod(instance_dir, 0o777)  # Ensure it's writable
    except Exception as e:
        print(f"Warning: Could not set permissions on instance directory: {str(e)}")
    
    # Print directory status for debugging
    print(f"Instance directory: {instance_dir}")
    print(f"Exists: {os.path.exists(instance_dir)}")
    print(f"Writable: {os.access(instance_dir, os.W_OK)}")
    
    # Print database URI for debugging
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    print(f"Database URI: {db_uri}")
    
    # Extract database path from URI
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri[10:]
        if not db_path.startswith('/'):  # Relative path
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        
        db_dir = os.path.dirname(db_path)
        print(f"Database directory: {db_dir}")
        print(f"Database file: {db_path}")
        print(f"Database directory exists: {os.path.exists(db_dir)}")
        print(f"Database directory writable: {os.access(db_dir, os.W_OK)}")
        
        # Ensure database directory exists
        if not os.path.exists(db_dir):
            print(f"Creating database directory: {db_dir}")
            os.makedirs(db_dir, exist_ok=True)
        
        # Try to create an empty file to test write permissions
        test_file = os.path.join(db_dir, 'test_write.tmp')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print("Write test successful")
        except Exception as e:
            print(f"Write test failed: {str(e)}")
            print("Warning: The application may not be able to write to the database directory")

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
    # Set up the instance directory and ensure it's writable
    setup_instance_directory()
    
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
                print("CRITICAL ERROR: Could not connect to database after maximum retries")
                print("Database connection information:")
                print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
                print(f"Current working directory: {os.getcwd()}")
                print("Directory listing:")
                print(subprocess.check_output(['ls', '-la']).decode())
                print("Instance directory listing:")
                instance_dir = os.path.join(os.getcwd(), 'instance')
                if os.path.exists(instance_dir):
                    print(subprocess.check_output(['ls', '-la', instance_dir]).decode())
                else:
                    print(f"Instance directory {instance_dir} does not exist")
                
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
    try:
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
    except Exception as e:
        print(f"Critical error during startup: {str(e)}")
        sys.exit(1)