from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, DateField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length
import sqlalchemy as sa
from app import db
from app.models import User, Project, Goal, Sprint, Comment

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
    name = StringField('Project Name', validators=[DataRequired()])
    dri = StringField('Directly Responsible Individual', validators=[DataRequired()])
    team = StringField('Assigned Team', validators=[DataRequired()])
    context = TextAreaField('Context and Background Information')
    why = TextAreaField('Reason for Prioritization')
    requirements = TextAreaField('Requirements')
    launch = TextAreaField('Launch Plan')
    submit = SubmitField('submit')
    
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