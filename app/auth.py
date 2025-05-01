from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user
from app.models import Project

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

def project_access_required(f):
    """
    Decorator for views that require access to a specific project.
    Must be used on routes with project_id parameter.
    """
    @wraps(f)
    def decorated_function(project_id, *args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
            
        project = Project.query.get_or_404(project_id)
        
        if not current_user.can_view_project(project):
            flash('You do not have permission to access this project.', 'danger')
            return redirect(url_for('index'))
            
        return f(project_id, *args, **kwargs)
    return decorated_function

def project_edit_required(f):
    """
    Decorator for views that require edit access to a specific project.
    Must be used on routes with project_id parameter.
    """
    @wraps(f)
    def decorated_function(project_id, *args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
            
        project = Project.query.get_or_404(project_id)
        
        if not current_user.can_edit_project(project):
            flash('You do not have permission to edit this project.', 'danger')
            return redirect(url_for('project', project_id=project_id))
            
        return f(project_id, *args, **kwargs)
    return decorated_function