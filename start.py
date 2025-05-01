#!/usr/bin/env python
import os
import subprocess
import time
import sys
import sqlite3
from app import app, db
from app.models import User, Role, user_roles
import sqlalchemy as sa

def check_sqlite_db():
    """Check SQLite database connection directly"""
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    print(f"Checking SQLite database: {db_uri}")
    
    if db_uri.startswith('sqlite:///'):
        # Relative path SQLite URI
        if db_uri.startswith('sqlite:////'):  # Absolute path with 4 slashes
            db_path = db_uri[10:]
        else:  # Relative path with 3 slashes
            db_path = db_uri[10:]
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        
        print(f"Resolved database path: {db_path}")
        
        # Check if directory exists
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            print(f"Creating database directory: {db_dir}")
            os.makedirs(db_dir, exist_ok=True)
        
        # Try to connect directly with sqlite3
        try:
            print(f"Testing direct SQLite connection to: {db_path}")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("CREATE TABLE IF NOT EXISTS test_connection (id INTEGER PRIMARY KEY)")
            cursor.execute("SELECT 1 FROM test_connection LIMIT 1")
            conn.commit()
            conn.close()
            print("Direct SQLite connection successful")
            return True
        except Exception as e:
            print(f"Direct SQLite connection failed: {str(e)}")
            return False
    
    return True  # Not SQLite or can't check directly

def setup_database():
    """Ensure the database is ready to use"""
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    print(f"Setting up database: {db_uri}")
    
    if db_uri.startswith('sqlite:///'):
        # Extract database path
        if db_uri.startswith('sqlite:////'):  # Absolute path
            db_path = db_uri[10:]
        else:  # Relative path
            db_path = db_uri[10:]
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        
        db_dir = os.path.dirname(db_path)
        print(f"Database path: {db_path}")
        print(f"Database directory: {db_dir}")
        
        # Create directory if it doesn't exist
        if not os.path.exists(db_dir):
            print(f"Creating database directory: {db_dir}")
            os.makedirs(db_dir, exist_ok=True)
        
        # Set permissions
        try:
            print(f"Setting permissions on directory: {db_dir}")
            os.chmod(db_dir, 0o777)
        except Exception as e:
            print(f"Could not set permissions on {db_dir}: {str(e)}")
        
        # Initialize empty database file if it doesn't exist
        if not os.path.exists(db_path):
            try:
                print(f"Initializing empty database file: {db_path}")
                conn = sqlite3.connect(db_path)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.commit()
                conn.close()
                
                # Set permissions on the database file
                os.chmod(db_path, 0o666)
                print("Database file initialized successfully")
            except Exception as e:
                print(f"Error initializing database file: {str(e)}")
        else:
            print(f"Database file already exists: {db_path}")
            try:
                # Ensure permissions are correct even if file exists
                os.chmod(db_path, 0o666)
            except Exception as e:
                print(f"Could not set permissions on existing database: {str(e)}")
        
        # Print directory and file info
        print(f"Directory exists: {os.path.exists(db_dir)}")
        print(f"Directory writable: {os.access(db_dir, os.W_OK)}")
        print(f"Database exists: {os.path.exists(db_path)}")
        print(f"Database writable: {os.access(db_path, os.W_OK)}")
        
        # Test write to database directory
        test_file = os.path.join(db_dir, 'test_write.tmp')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print("Write test to directory successful")
        except Exception as e:
            print(f"Write test to directory failed: {str(e)}")
        
        # Try to connect directly to test the database
        check_sqlite_db()

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
        # First ensure the table exists
        db.create_all()
        
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
    # Setup the database structure and permissions
    setup_database()
    
    with app.app_context():
        print("Creating database tables directly...")
        db.create_all()
        print("Tables created")
    
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
                
                # Get the database directory
                db_uri = app.config['SQLALCHEMY_DATABASE_URI']
                if db_uri.startswith('sqlite:////'):  # Absolute path
                    db_path = db_uri[10:]
                    db_dir = os.path.dirname(db_path)
                elif db_uri.startswith('sqlite:///'):  # Relative path
                    db_path = db_uri[10:]
                    if not os.path.isabs(db_path):
                        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
                    db_dir = os.path.dirname(db_path)
                else:
                    db_dir = None
                
                if db_dir and os.path.exists(db_dir):
                    print(f"Database directory listing ({db_dir}):")
                    print(subprocess.check_output(['ls', '-la', db_dir]).decode())
                
                # Try to create database directly as a last resort
                if db_uri.startswith('sqlite:///'):
                    print("Attempting direct database creation as last resort...")
                    if not check_sqlite_db():
                        print("Direct database connection also failed")
                
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