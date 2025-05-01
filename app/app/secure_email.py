import os
import base64
import hashlib
import re
import hmac
from datetime import datetime

class SimpleEncryptor:
    """
    Simple credential encryptor using built-in Python cryptography.
    Not as secure as Fernet but doesn't require additional packages.
    """
    
    def __init__(self, app=None):
        self.secret_key = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app to get secret key"""
        # Use the app's secret key to derive an encryption key
        app_secret = app.config['SECRET_KEY']
        
        # Generate a salt and store it in the app config
        if 'ENCRYPTION_SALT' not in app.config:
            try:
                # Use secrets module if available (Python 3.6+)
                import secrets
                salt = secrets.token_bytes(16)
            except ImportError:
                # Fallback for older Python versions
                salt = os.urandom(16)
            app.config['ENCRYPTION_SALT'] = salt
        else:
            salt = app.config['ENCRYPTION_SALT']
        
        # Create a derived key using HMAC
        self.secret_key = hashlib.pbkdf2_hmac(
            'sha256', 
            app_secret.encode() if isinstance(app_secret, str) else app_secret,
            salt,
            100000,  # Iterations
            dklen=32  # Key length
        )
    
    def encrypt(self, data):
        """Simple encryption for sensitive data"""
        if not data:
            return None
            
        if not self.secret_key:
            raise ValueError("Encryptor not initialized with an app")
            
        # Convert data to bytes if it's a string
        if isinstance(data, str):
            data = data.encode()
        
        # Generate a random IV (initialization vector)
        try:
            # Use secrets module if available (Python 3.6+)
            import secrets
            iv = secrets.token_bytes(16)
        except ImportError:
            # Fallback for older Python versions
            iv = os.urandom(16)
        
        # Create HMAC for authentication
        h = hmac.new(self.secret_key, data + iv, hashlib.sha256).digest()
        
        # Basic XOR encryption with key derived from secret and IV
        key_stream = hashlib.pbkdf2_hmac('sha256', self.secret_key, iv, 1, len(data))
        encrypted = bytes(a ^ b for a, b in zip(data, key_stream))
        
        # Combine IV + HMAC + Encrypted data
        result = iv + h + encrypted
        
        # Return as a base64 string for storage
        return base64.b64encode(result).decode('utf-8')
    
    def decrypt(self, encrypted_data):
        """Decrypt data encrypted with this class"""
        if not encrypted_data:
            return None
            
        if not self.secret_key:
            raise ValueError("Encryptor not initialized with an app")
        
        try:
            # Convert from base64 string to bytes
            data = base64.b64decode(encrypted_data)
            
            # Extract IV, HMAC and encrypted data
            iv = data[:16]
            hmac_digest = data[16:48]  # SHA-256 digest is 32 bytes
            encrypted = data[48:]
            
            # Verify HMAC
            key_stream = hashlib.pbkdf2_hmac('sha256', self.secret_key, iv, 1, len(encrypted))
            decrypted = bytes(a ^ b for a, b in zip(encrypted, key_stream))
            
            computed_hmac = hmac.new(self.secret_key, decrypted + iv, hashlib.sha256).digest()
            if not hmac.compare_digest(computed_hmac, hmac_digest):
                return None  # Authentication failed
            
            # Return decrypted data
            return decrypted.decode('utf-8')
            
        except Exception as e:
            # Log the error but don't expose details
            print(f"Decryption error: {type(e).__name__}")
            return None

# Initialize the encryptor
encryptor = SimpleEncryptor()