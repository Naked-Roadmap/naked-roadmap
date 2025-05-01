from app import app, db
from app.models import AppConfig
from app.secure_email import encryptor

def encrypt_existing_credentials():
    with app.app_context():
        # Initialize the encryptor with the app
        encryptor.init_app(app)
        
        # List of sensitive keys to encrypt
        sensitive_keys = ['smtp_password', 'smtp_username', 'api_key']
        
        # Get all AppConfig entries with sensitive keys
        configs = AppConfig.query.filter(AppConfig.key.in_(sensitive_keys)).all()
        
        for config in configs:
            # Skip if already encrypted
            if config.value and not config.value.startswith('encrypted:'):
                # Encrypt the value
                encrypted_value = encryptor.encrypt(config.value)
                
                # Update with encrypted value
                config.value = f'encrypted:{encrypted_value}'
                
                print(f"Encrypted config: {config.key}")
        
        # Commit all changes
        db.session.commit()
        print("Migration of sensitive credentials complete")

if __name__ == "__main__":
    encrypt_existing_credentials()