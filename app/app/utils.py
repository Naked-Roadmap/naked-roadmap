import bleach
from datetime import datetime
from flask import jsonify, request

# Define allowed HTML tags and attributes for rich text fields
ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'div', 'em', 
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 
    'pre', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul'
]

# Remove style from allowed attributes to prevent style-based XSS attacks
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'abbr': ['title'],
    'acronym': ['title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'table': ['width', 'border', 'cellspacing', 'cellpadding'],
    'td': ['colspan', 'rowspan', 'width'],
    'th': ['colspan', 'rowspan', 'width'],
    # Remove '*': ['class', 'id', 'style'] which allowed style on all elements
    '*': ['class', 'id']  # Only allow class and id on all elements
}

# Safe URL schemes for links
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'tel']

def clean_html(html_content):
    """
    Clean HTML content with bleach, removing potentially dangerous attributes
    """
    if html_content is None:
        return ""
        
    # Clean with allowed tags and attributes, explicitly restricting protocols
    cleaned_html = bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )
    return cleaned_html

# Helper function to sanitize text fields (no HTML allowed)
def sanitize_text(text):
    """
    Sanitize plain text fields by removing all HTML tags
    """
    if text is None:
        return ""
    return bleach.clean(text, tags=[], strip=True)

# Add a method to check user permissions (implement according to your authorization model)
def user_can_edit_project(self, project):
    # This is a placeholder - implement your own permission logic
    # For example, check if user is project owner, admin, or in allowed teams
    return True

# Add the method to the User model
from flask_login import UserMixin
UserMixin.can_edit_project = user_can_edit_project

def is_xhr_property(request_obj):
    """Check if the request is an AJAX/XHR request"""
    return request_obj.headers.get('X-Requested-With') == 'XMLHttpRequest'

# Attach the property to Flask's request object
setattr(request.__class__, 'is_xhr', property(lambda request_obj: is_xhr_property(request_obj)))

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

# #################################
# Roles Management
# #################################

def role_required(role_name):
    """
    Decorator for views that require a specific role.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login', next=request.url))
            
            if not current_user.has_role(role_name):
                flash(f'You need to have {role_name} privileges to access this page.', 'danger')
                return redirect(url_for('index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """
    Decorator for views that require admin privileges.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
            
        if not current_user.is_admin():
            flash('You need to have administrator privileges to access this page.', 'danger')
            return redirect(url_for('index'))
            
        return f(*args, **kwargs)
    return decorated_function

def project_access_required(view_func):
    """
    Decorator for views that require access to a specific project.
    Must be used on routes with project_id parameter.
    """
    @wraps(view_func)
    def decorated_function(project_id, *args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
            
        project = Project.query.get_or_404(project_id)
        
        if not current_user.can_view_project(project):
            flash('You do not have permission to access this project.', 'danger')
            return redirect(url_for('index'))
            
        return view_func(project_id, *args, **kwargs)
    return decorated_function

def project_edit_required(view_func):
    """
    Decorator for views that require edit access to a specific project.
    Must be used on routes with project_id parameter.
    """
    @wraps(view_func)
    def decorated_function(project_id, *args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
            
        project = Project.query.get_or_404(project_id)
        
        if not current_user.can_edit_project(project):
            flash('You do not have permission to edit this project.', 'danger')
            return redirect(url_for('project', project_id=project_id))
            
        return view_func(project_id, *args, **kwargs)
    return decorated_function