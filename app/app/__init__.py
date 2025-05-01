from flask import Flask, request, abort, flash, redirect, url_for
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

def add_security_headers(response):
    """Add security headers to all responses"""
    # Content Security Policy to prevent XSS attacks
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com https://code.jquery.com https://stackpath.bootstrapcdn.com https://cdn.jsdelivr.net 'unsafe-inline'; "
        "style-src 'self' https://stackpath.bootstrapcdn.com https://fonts.googleapis.com 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "frame-src 'none'; "
        "object-src 'none'; "
        "base-uri 'self'"
    )
    
    # Prevent browsers from incorrectly detecting non-scripts as scripts
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    
    # Enable the XSS filter built into most recent web browsers
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Add Referrer Policy header
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    return response

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login' # If you want to toggle someone forced to log in to see roadmap, you can use this. 
app.after_request(add_security_headers)

from app import routes, models
