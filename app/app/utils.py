import bleach
from datetime import datetime
from flask import jsonify, request

# Define allowed HTML tags and attributes for rich text fields
ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'div', 'em', 
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 
    'pre', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'abbr': ['title'],
    'acronym': ['title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'table': ['width', 'border', 'cellspacing', 'cellpadding'],
    'td': ['colspan', 'rowspan', 'width'],
    'th': ['colspan', 'rowspan', 'width'],
    '*': ['class', 'id', 'style']  # Still allow style as an attribute
}

# For backward compatibility - create a function to clean HTML with style support
def clean_html(html_content):
    """
    Clean HTML content with bleach, maintaining style attributes
    """
    # First clean with allowed tags and attributes (which includes style attr)
    cleaned_html = bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )
    return cleaned_html

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