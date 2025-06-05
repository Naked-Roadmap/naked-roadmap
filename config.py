import os
import secrets
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))

def setup_data_directory():
    """Setup data directory based on environment"""
    # Check if we're running in Docker
    if os.path.exists('/.dockerenv') or os.environ.get('RUNNING_IN_DOCKER'):
        data_dir = '/data'
    else:
        # Local development - use a local data directory
        data_dir = os.path.join(basedir, 'instance')
    
    # Create data directory if it doesn't exist
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
            print(f"Created data directory: {data_dir}")
        except Exception as e:
            print(f"Warning: Could not create {data_dir}: {e}")
    
    return data_dir

# Setup data directory
data_dir = setup_data_directory()

# Create a .env file if it doesn't exist
env_file = Path(os.path.join(basedir, '.env'))
if not env_file.exists():
    # Generate a secure secret key
    generated_key = secrets.token_hex(32)
    
    # Create initial .env file with the generated key
    with open(env_file, 'w') as f:
        f.write(f"SECRET_KEY={generated_key}\n")
        f.write("# Add other environment variables below\n")
        f.write("# For local development, database will be in instance/ directory\n")
        f.write("# For Docker, database will be in /data/ directory\n")
        f.write("# DATABASE_URL=sqlite:////data/app.db  # Docker\n")
        f.write("# DATABASE_URL=sqlite:///instance/app.db  # Local\n")
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
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database configuration - Smart path selection
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        # Auto-detect environment and set appropriate database path
        if os.path.exists('/.dockerenv') or os.environ.get('RUNNING_IN_DOCKER'):
            # Running in Docker container
            db_url = 'sqlite:////data/app.db'
        else:
            # Running locally
            db_url = f'sqlite:///{os.path.join(data_dir, "app.db")}'
    
    print(f"Environment detection:")
    print(f"  Docker environment: {os.path.exists('/.dockerenv') or bool(os.environ.get('RUNNING_IN_DOCKER'))}")
    print(f"  Data directory: {data_dir}")
    print(f"  Database URL: {db_url}")
    
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
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