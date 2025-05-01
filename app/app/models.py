from datetime import datetime, timezone, date
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from colorama import Fore, Style
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import login

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

# User-Role association table with named constraints
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', name='fk_user_roles_user_id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id', name='fk_user_roles_role_id'), primary_key=True)
)

class Role(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(64), unique=True)
    description: so.Mapped[str] = so.mapped_column(sa.String(255))
    
    # Define permissions as a relationship to users
    # users: so.WriteOnlyMapped['User'] = so.relationship(
    #     secondary=user_roles,
    #     back_populates='roles'
    # )
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    # posts: so.WriteOnlyMapped['Post'] = so.relationship(back_populates='author')
    
    # Add roles relationship
    roles = db.relationship('Role', secondary=user_roles, lazy='dynamic',
                          backref=db.backref('users', lazy='dynamic'))
    
    def __repr__(self):
        return '<User {}>'.format(self.username)
    
    # def set_password(self, password):
    #     self.password_hash = generate_password_hash(password)
    
    def set_password(self, password):
        """
        Hash the user's password with PBKDF2, SHA-256, 50,000 iterations, and 16-byte salt
        """
        self.password_hash = generate_password_hash(
            password,
            method='pbkdf2:sha256:50000',  # PBKDF2 with SHA-256 and 50,000 iterations
            salt_length=16  # 16-byte salt
        )
    def validate_password_strength(password):
        """
        Validate password meets security requirements:
        - At least 10 characters long
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one digit
        - Contains at least one special character
        """
        import re
        
        if len(password) < 10:
            return False, "Password must be at least 10 characters long"
            
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
            
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
            
        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"
            
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
            
        return True, "Password meets requirements"
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    # Role-based authorization methods
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return self.roles.filter_by(name=role_name).first() is not None
    
    def is_admin(self):
        """Check if user is an admin"""
        return self.has_role('admin')
    
    # Permission checking methods
    def can_view_project(self, project):
        """Check if user can view a project"""
        # Admins can view all projects
        if self.is_admin():
            return True
        
        # Project owners can view their projects
        if project.user_id == self.id:
            return True
        
        # DRIs can view their projects
        if project.dri == self.username:
            return True
        
        return False
    
    def can_edit_project(self, project):
        """Check if user can edit a project"""
        # Admins can edit all projects
        if self.is_admin():
            return True
        
        # Project owners can edit their projects
        if project.user_id == self.id:
            return True
        
        # DRIs can edit their projects
        if project.dri == self.username:
            return True
        
        return False
    
    def can_delete_project(self, project):
        """Check if user can delete a project"""
        # Only admins and owners can delete projects
        if self.is_admin():
            return True
            
        if project.user_id == self.id:
            return True
        
        return False

class Project(db.Model):
    __tablename__ = "project"
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.TEXT())
    created: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    dri: so.Mapped[str] = so.mapped_column(sa.TEXT())
    team: so.Mapped[str] = so.mapped_column(sa.TEXT())
    context: so.Mapped[str] = so.mapped_column(sa.TEXT())
    why: so.Mapped[str] = so.mapped_column(sa.TEXT())
    requirements: so.Mapped[str] = so.mapped_column(sa.TEXT())
    launch: so.Mapped[str] = so.mapped_column(sa.TEXT())
    location: so.Mapped[str] = so.mapped_column(sa.TEXT(),  nullable=True, default="discussion")
    type: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True)
    status: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True, default="Active")
    # Add ownership and visibility fields
    # user_id: db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    user_id: so.Mapped[Optional[int]] = so.mapped_column(
        sa.ForeignKey('user.id', name='fk_project_user_id'), 
        index=True,
        nullable=True  # Make nullable for existing records
    )
    is_public: so.Mapped[bool] = so.mapped_column(default=True, nullable=True)  # Control visibility
    # Foreign keys
    objective_id = db.Column(db.Integer, db.ForeignKey('goal.id'), nullable=True)
    # Relationships
    objective = db.relationship('Goal', backref=db.backref('projects', lazy='dynamic'))
    # owner = db.relationship('User', foreign_keys=[user_id], backref='owned_projects')
    
    def __repr__(self):
        return '<Project {}>'.format(self.name)
        
# TODO: Rename to be Objectives
class Goal(db.Model):
    __tablename__ = "goal"
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    created: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    title: so.Mapped[str] = so.mapped_column(sa.TEXT())
    requested_by: so.Mapped[str] = so.mapped_column(sa.TEXT())
    details: so.Mapped[str] = so.mapped_column(sa.TEXT())
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    status: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True, default="Active")
    completed: so.Mapped[datetime] = so.mapped_column(nullable=True)
    
    def __repr__(self):
        return '<Goal {}>'.format(self.title)
    
    def __repr__(self):
        return '<Request {}>'.format(self.body)

class Sprint(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    created: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    title: so.Mapped[str] = so.mapped_column(sa.TEXT())
    date_start: so.Mapped[date] = so.mapped_column(index=True)
    date_end: so.Mapped[date] = so.mapped_column(index=True)
    goals: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True)
    status: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True)
    
    def __repr__(self):
        return '<Sprint {}>'.format(self.body)

# TODO: Rename to be commitments
# https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.rename_table
class SprintProjectMap(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    added: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    sprint_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Sprint.id), index=True)
    project_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Project.id), index=True)
    goal: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True)
    status: so.Mapped[str] = so.mapped_column(sa.TEXT(), default="Planned")
    order: so.Mapped[int] = so.mapped_column(nullable=True, autoincrement=True)
    project = db.relationship("Project", backref="sprint_mappings")
    sprint = db.relationship("Sprint", backref="project_mappings")
    critical: so.Mapped[bool] = so.mapped_column(default=False, nullable=True)
    status_comment: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True)
    status_updated: so.Mapped[datetime] = so.mapped_column(nullable=True)
    status_updated_by: so.Mapped[int] = so.mapped_column(sa.Integer(), nullable=True)
    
    # Relationship defined without foreign key constraint
    # This avoids migration issues but still provides the ORM relationship
    status_user = db.relationship(
        "User", 
        primaryjoin="SprintProjectMap.status_updated_by == User.id",
        foreign_keys=[status_updated_by],
        post_update=True,  # Use post_update to avoid circular dependency issues
        uselist=False
    )
    
    def __repr__(self):
        return f'<Sprint/Project Map {self.id}: {self.project.name} - {self.status}>'

class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    project = db.relationship('Project', backref=db.backref('comments', lazy='dynamic', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('comments', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Comment {self.id} by User {self.user_id} on Project {self.project_id}>'

class Changelog(db.Model):
    __tablename__ = 'changelogs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    change_type = db.Column(db.String(50), nullable=False)  # 'create', 'edit', 'sprint_assignment', etc.
    content = db.Column(db.Text, nullable=False)  # Description of what changed
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    project = db.relationship('Project', backref=db.backref('changelogs', lazy='dynamic', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('changelogs', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Changelog {self.id}: {self.change_type} by User {self.user_id} on Project {self.project_id}>'
        
        
class AppConfig(db.Model):
    """
    Configuration settings for the application stored as key-value pairs
    """
    __tablename__ = 'app_config'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    key: so.Mapped[str] = so.mapped_column(sa.String(100), index=True, unique=True)
    value: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True)
    description: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True)
    created: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    updated: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc), 
                                                   onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<AppConfig {self.key}>'
    
# Helper functions to get and set configuration values
def get_config(key, default=None):
    """Get a configuration value by key"""
    config = db.session.query(AppConfig).filter(AppConfig.key == key).first()
    return config.value if config else default

def set_config(key, value, description=None):
    """Set a configuration value"""
    config = db.session.query(AppConfig).filter(AppConfig.key == key).first()
    if config:
        config.value = value
        config.updated = datetime.now(timezone.utc)
        if description and not config.description:
            config.description = description
    else:
        config = AppConfig(key=key, value=value, description=description)
        db.session.add(config)
    db.session.commit()
    return config