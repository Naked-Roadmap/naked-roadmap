from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, DateField, HiddenField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length
import sqlalchemy as sa
from app import db
from app.models import User, Project, Goal, Sprint, Comment
import re

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')
    
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(
            User.email == email.data))
        if user is not None:
            raise ValidationError('Please use a different email address.')
            
class CreateProject(FlaskForm):
    # CSRF token is automatically included by Flask-WTF
    
    name = StringField('Project Name', validators=[
        DataRequired(message="Project name is required"),
        Length(min=3, max=100, message="Project name must be between 3 and 100 characters")
    ])
    
    dri = StringField('Directly Responsible Individual', validators=[
        DataRequired(message="DRI is required"),
        Length(max=100, message="DRI name must be less than 100 characters")
    ])
    
    team = StringField('Assigned Team', validators=[
        DataRequired(message="Team name is required"),
        Length(max=100, message="Team name must be less than 100 characters")
    ])
    
    context = TextAreaField('Context and Background Information', validators=[
        Length(max=10000, message="Context information is too long")
    ])
    
    why = TextAreaField('Reason for Prioritization', validators=[
        Length(max=10000, message="Prioritization rationale is too long")
    ])
    
    requirements = TextAreaField('Requirements', validators=[
        Length(max=10000, message="Requirements are too long")
    ])
    
    launch = TextAreaField('Launch Plan', validators=[
        Length(max=10000, message="Launch plan is too long")
    ])
    
    submit = SubmitField('Save Changes')
    
    # Custom validators
    def validate_name(self, field):
        # Prevent XSS in project name
        if re.search(r'<[^>]*script', field.data, re.IGNORECASE):
            raise ValidationError("Project name contains invalid characters")
        
        # Prevent SQL injection in project name
        if re.search(r'(\b(select|insert|update|delete|drop|union|exec)\b|[;\'"])', field.data, re.IGNORECASE):
            raise ValidationError("Project name contains invalid characters")
    
class CreateGoal(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    details = TextAreaField('Additional Details and Context', validators=[DataRequired()])
    requested_by = StringField('Requested by')
    submit = SubmitField('submit')
    
class CreateSprint(FlaskForm):
    title = StringField('Sprint Name', validators=[DataRequired()])
    date_start = DateField('Start of Sprint', format='%Y-%m-%d', validators=[DataRequired()] )
    date_end = DateField('End of Sprint', format='%Y-%m-%d', validators=[DataRequired()] )
    submit = SubmitField('submit')
    
class CommentForm(FlaskForm):
    content = TextAreaField('Add a New Comment', validators=[
        DataRequired(message='Comment cannot be empty'),
        Length(min=1, max=1000, message='Comment must be between 1 and 1000 characters')
    ])
    submit = SubmitField('Submit Comment')