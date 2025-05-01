import os
import secrets
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))

# Ensure instance directory exists
instance_dir = os.path.join(basedir, 'instance')
os.makedirs(instance_dir, exist_ok=True)

# Create a .env file if it doesn't exist
env_file = Path(os.path.join(basedir, '.env'))
if not env_file.exists():
    # Generate a secure secret key
    generated_key = secrets.token_hex(32)
    
    # Create initial .env file with the generated key
    with open(env_file, 'w') as f:
        f.write(f"SECRET_KEY={generated_key}\n")
        f.write("# Add other environment variables below\n")
        f.write("# DATABASE_URL=sqlite:///instance/app.db\n")
        f.write("# SMTP_SERVER=smtp.example.com\n")
        f.write("# SMTP_PORT=587\n")
        f.write("# SMTP_USERNAME=your_username\n")
        f.write("# SMTP_PASSWORD=your_password\n")
    
    # Set permissions to restrict access (Linux/Mac only)
    try:
        os.chmod(env_file, 0o600)  # Only owner can read/write
    except Exception:
        # Skip on Windows or if permission setting fails
        pass
    
    print(f"Created .env file with generated secret key. Please review {env_file}")


# Function to load environment variables from .env file
def load_env_vars():
    """Load environment variables from .env file if it exists"""
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                # Skip comments and empty lines
                if line.startswith('#') or not line.strip():
                    continue
                    
                # Parse KEY=VALUE format
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    # Don't override existing environment variables
                    if key not in os.environ:
                        os.environ[key] = value

# Load environment variables if not already in a production environment
if 'FLASK_ENV' not in os.environ or os.environ['FLASK_ENV'] != 'production':
    load_env_vars()
    
class Config:
    # Use environment variable with a fallback to a randomly generated key
    # This ensures a new random key is used if env var is not set
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database configuration - Note the path is now explicitly in the instance folder
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(instance_dir, 'app.db')
    
    # Company customizations
    company_name = os.environ.get('COMPANY_NAME') or "Naked Roadmap"
    public = os.environ.get('PUBLIC_ROADMAP', 'true').lower() == 'true'
    
    # Email configuration - all pulled from environment variables
    MAIL_SERVER = os.environ.get('SMTP_SERVER')
    MAIL_PORT = int(os.environ.get('SMTP_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('SMTP_USERNAME')
    MAIL_PASSWORD = os.environ.get('SMTP_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_SENDER')