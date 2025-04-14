from app import app, db, login
from app.forms import LoginForm, RegistrationForm, CreateProject, CreateGoal, CreateSprint
from app.models import User, Project, Goal, Sprint, SprintProjectMap
import sqlalchemy as sa
from flask import Flask, render_template, request, url_for, flash, redirect, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.exceptions import abort
from urllib.parse import urlsplit
from config import Config
from datetime import datetime


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
    submittedGoals = (
        Goal.query
        .order_by(Goal.created.desc())
        .all()
    )
    sprints = (
        Sprint.query
        .order_by(Sprint.date_start.desc())
        .all()
    )
    sprintlog = (
        SprintProjectMap.query
        .order_by(SprintProjectMap.order.asc())
        .all()
    )
    today = datetime.now()
    return render_template('index.html', title='Home', projects=projects, goals=submittedGoals, config=Config, sprints=sprints, sprintlog=sprintlog, datetime=datetime, today=today)

@app.route('/<int:project_id>')
def project(project_id):
    project = (
        Project.query
        .filter_by(id=project_id)
        .first()
    )
    return render_template('project.html', project=project)
    
@app.route('/create', methods=['GET', 'POST'])
def createProject():
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
    deleteProject = db.session.query(Project).filter(Project.id==project_id).first()
    db.session.delete(deleteProject)
    db.session.commit()
    # db.session.scalar(Project.query.filter_by(id=project_id).delete())
    flash('Project was successfully deleted!')
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
    
    

########################################################
### Managing Projects
########################################################

@app.route('/projects')
@login_required # If you want to toggle someone forced to log in to see roadmap, you can use this. 
def projectspage():
    # if not current_user.is_verified:
    #     return redirect(url_for("auth.verify"))
    projects = (
        Project.query
        .order_by(Project.created.desc())
        .all()
    )
    return render_template('projects.html', title='Projects', projects=projects)
    
    
########################################################
### Managing Goals
########################################################

@app.route('/goals', methods=['GET', 'POST'])
def submitGoal():
    form = CreateGoal()
    if request.method == 'POST':
        requestDetails = Goal(
            title=form.title.data,
            details=form.details.data,
            requested_by=form.requested_by.data,
            user_id=current_user.id
        )

        db.session.add(requestDetails)
        db.session.commit()
        
        flash('Congratulations, request captured!')
        return redirect(url_for('index'))
        
    return render_template('goals.html', form=form)
    
    
########################################################
### Managing Sprints
########################################################

@app.route('/sprint', methods=['GET', 'POST'])
def createSprint():
    form = CreateSprint()
    
    try:
        if request.method == 'POST':
            sprintDetails = Sprint(
                title=form.title.data,
                date_start=form.date_start.data,
                date_end=form.date_end.data
            )
    
            db.session.add(sprintDetails)
            db.session.commit()
            
            flash('Congratulations, sprint created!')
            return redirect(url_for('index'))
    except TypeError as e:
        print(f"Error: {e}")
        
    return render_template('sprint.html', form=form)
    
@app.route('/add-to-cycle/<int:project_id>/<int:sprint_id>/', methods=['GET','POST'])
def add_to_cycle(project_id, sprint_id):
    if request.method == 'GET':
        addToSprint = SprintProjectMap(
            sprint_id=sprint_id,
            project_id=project_id
        )

        db.session.add(addToSprint)
        db.session.commit()
        
        flash('Congratulations, added to cycle!')
        return redirect(url_for('index'))
    return redirect(url_for('index'))
    
    
    
########################################################
### APIs for Async Updates
########################################################

@app.route('/api/project/<int:project_id>', methods=['GET'])
def api_get_project(project_id):
    project = (
        Project.query
        .filter_by(id=project_id)
        .first()
    )
    
    if not project:
        return jsonify({"error": "Project not found"}), 404
    
    # Convert SQLAlchemy model to dictionary
    project_data = {
        'id': project.id,
        'name': project.name,
        'why': project.why,
        'context': project.context,
        'launch': project.launch,
        'requirements': project.requirements,
        'dri': project.dri,
        'created': project.created.strftime('%Y-%m-%d') if project.created else None,
        'team': project.team,
        # 'status': project.status,
        # 'priority': project.priority,
        'location': project.location
    }
    
    # Return the project data as JSON
    return jsonify(project_data)

@app.route('/api/project/move', methods=['POST'])
def api_move_project():
    """
    API endpoint to move a project to sprint or backlog
    """
    data = request.json
    project_id = data.get('projectId')
    new_location = data.get('location')
    sprint_goal = data.get('sprintGoal', '')
    
    # Validate the required fields
    if not project_id or not new_location:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
    
    # Check if project exists
    project = Project.query.get(project_id)
    if project is None:
        return jsonify({"success": False, "message": "Project not found"}), 404
    
    # Update the project location
    project.location = new_location
    
    # If moving to sprint, also handle sprint relationship
    if new_location == 'sprint':
        # Check if already in sprint
        existing_map = SprintProjectMap.query.filter_by(
            project_id=project_id,
            sprint_id=2
        ).first()
        
        if existing_map:
            # Update existing relationship
            existing_map.goal = sprint_goal
        else:
            # Create new sprint-project relationship
            sprint_project_map = SprintProjectMap(
                sprint_id=2,
                project_id=project_id,
                goal=sprint_goal
            )
            db.session.add(sprint_project_map)
    
    # Commit changes to the database
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Project moved to {new_location} successfully"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Database error: {str(e)}"
        }), 500