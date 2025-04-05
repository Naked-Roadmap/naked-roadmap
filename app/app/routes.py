from app import app, db, login
from app.forms import LoginForm, RegistrationForm, CreateProject, CreateRequest
from app.models import User, Project, Request
import sqlalchemy as sa
from flask import Flask, render_template, request, url_for, flash, redirect
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.exceptions import abort
from urllib.parse import urlsplit

@app.route('/')
@app.route('/index')
@login_required # If you want to toggle someone forced to log in to see roadmap, you can use this. 
def index():
    # if not current_user.is_verified:
    #     return redirect(url_for("auth.verify"))
    projects = (
        Project.query
        .order_by(Project.created.desc())
        .all()
    )
    return render_template('index.html', title='Home', projects=projects)

@app.route('/<int:project_id>')
def project(project_id):
    project = (
        Project.query
        .filter_by(id=project_id)
        .first()
    )
    return render_template('project.html', project=project)
    
@app.route('/create', methods=['GET', 'POST'])
def create():
    form = CreateProject()
    if request.method == 'POST':
        projectDetails = Project(
            name=form.name.data,
            dri=form.dri.data,
            team=form.team.data,
            context=form.context.data,
            why=form.why.data,
            requirements=form.requirements.data,
            launch=form.launch.data, 
        )

        db.session.add(projectDetails)
        db.session.commit()
        
        flash('Congratulations, project created!')
        return redirect(url_for('index'))
        
    return render_template('create.html', form=form)

@app.route('/<int:project_id>/edit', methods=('GET', 'POST'))
def edit(project_id):
    project = (
        Project.query
        .filter_by(id=project_id)
        .first()
    )
    form = CreateProject()
    if request.method == 'POST':
        Project.query.filter_by(id=project_id).update(dict( 
            name=form.name.data,
            dri=form.dri.data,
            team=form.team.data,
            context=form.context.data,
            why=form.why.data,
            requirements=form.requirements.data,
            launch=form.launch.data
        )
        )
        db.session.commit()
        
        flash('Congratulations, project edited!')
        return redirect(url_for('index'))

    return render_template('edit.html', project=project, form=form)

@app.route('/<int:project_id>/delete', methods=('POST',))
def delete(project_id):
    # project = (
    #     Project.query
    #     .filter_by(id=project_id)
    # )
    db.session.delete(Project.query.filter_by(id=project_id))
    flash('"{}" was successfully deleted!'.format(project['name']))
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)
    
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)
    
    
    
    
############################
### Managing Requests
############################

@app.route('/request', methods=['GET', 'POST'])
def submitrequest():
    form = CreateRequest()
    if request.method == 'POST':
        requestDetails = Request(
            title=form.title.data,
            details=form.details.data,
            requested_by=form.requested_by.data,
            user_id=current_user.id
        )

        db.session.add(requestDetails)
        db.session.commit()
        
        flash('Congratulations, request captured!')
        return redirect(url_for('index'))
        
    return render_template('request.html', form=form)