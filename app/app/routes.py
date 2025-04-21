from app import app, db, login
from app.forms import LoginForm, RegistrationForm, CreateProject, CreateGoal, CreateSprint, CommentForm
from app.models import User, Project, Goal, Sprint, SprintProjectMap, Comment, Changelog, AppConfig, get_config, set_config
import sqlalchemy as sa
from flask import Flask, render_template, request, url_for, flash, redirect, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.exceptions import abort
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlsplit
from config import Config
from datetime import datetime, timedelta
from flask_wtf.csrf import generate_csrf
from . import utils
from .utils import ALLOWED_TAGS, ALLOWED_ATTRIBUTES, clean_html, sanitize_text 
import bleach
from sqlalchemy import func
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import os
from jinja2 import Template
import json

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())

@app.route('/')
@app.route('/index')
@login_required # If you want to toggle someone forced to log in to see roadmap, you can use this. 
def index():
    # if not current_user.is_verified:
    #     return redirect(url_for("auth.verify"))
    projects = (
        Project.query
        .order_by(Project.created.desc())
        .limit(5)
    )
    goals = (
        db.session.query(
            Goal,
            func.count(Project.id).label('active_project_count')
        )
        .outerjoin(Project, (Project.objective_id == Goal.id) & (Project.status == 'Active'))
        .group_by(Goal.id)
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
    comments = (
        Comment.query
        .order_by(Comment.created_at.desc())
        .limit(5)
    )
    changes = (
        Changelog.query
        .order_by(Changelog.timestamp.desc())
        .limit(5)
    )
    today = datetime.now()
    return render_template('index.html', title='Home', projects=projects, goals=goals, config=Config, sprints=sprints, sprintlog=sprintlog, datetime=datetime, today=today, comments=comments, changes=changes)
    
@app.route('/project/<int:project_id>')
def project(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    
    # Get comments for this project
    comments = Comment.query.filter_by(project_id=project_id).order_by(Comment.created_at.desc()).all()
    
    # Get changelog entries for this project
    changelogs = Changelog.query.filter_by(project_id=project_id).order_by(Changelog.timestamp.desc()).all()
    
    # Get cycle commitment entries for this project
    cycles = SprintProjectMap.query.filter_by(project_id=project_id).order_by(SprintProjectMap.added.desc()).all()
    
    active_goals = Goal.query.filter_by(status='Active').all()
    
    # Initialize comment form
    form = CommentForm()
    
    return render_template('project.html', project=project, comments=comments, changelogs=changelogs, form=form, cycles=cycles, active_goals=active_goals)
    
@app.route('/project/<int:project_id>/edit/', methods=('GET', 'POST'))
@login_required
def edit_project(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    
    # Check if user has permission to edit the project
    if not current_user.can_edit_project(project):
        flash('You do not have permission to edit this project.', 'error')
        return redirect(url_for('index'))
    
    form = CreateProject()
    
    if request.method == 'POST' and form.validate_on_submit():
        # Track what changed
        changes = []
        if project.name != form.name.data:
            changes.append(f"Name: '{project.name}' → '{form.name.data}'")
        if project.dri != form.dri.data:
            changes.append(f"DRI: '{project.dri}' → '{form.dri.data}'")
        if project.team != form.team.data:
            changes.append(f"Team: '{project.team}' → '{form.team.data}'")
        
        # For text fields, just note that they were updated (to avoid storing large diffs)
        if project.context != form.context.data:
            changes.append(f"Context updated")
        if project.why != form.why.data:
            changes.append(f"Why updated")
        if project.requirements != form.requirements.data:
            changes.append(f"Requirements updated")
        if project.launch != form.launch.data:
            changes.append(f"Launch updated")
        
        # Sanitize all inputs consistently
        sanitized_data = {
            'name': sanitize_text(form.name.data),
            'dri': sanitize_text(form.dri.data),
            'team': sanitize_text(form.team.data),
            'context': clean_html(form.context.data),
            'why': clean_html(form.why.data),
            'requirements': clean_html(form.requirements.data),
            'launch': clean_html(form.launch.data)
        }
        
        # Check if this is an autosave request
        is_autosave = request.form.get('autosave') == 'true'
        
        # Update the project
        Project.query.filter_by(id=project_id).update(sanitized_data)
        
        # Create changelog entry if changes were made and not an autosave
        if changes and not is_autosave:
            change_content = ", ".join(changes)
            # Sanitize the change content before storing
            sanitized_change_content = sanitize_text(change_content)
            
            changelog = Changelog(
                change_type='edit',
                content=sanitized_change_content,
                project_id=project_id,
                user_id=current_user.id,
                timestamp=datetime.utcnow()
            )
            db.session.add(changelog)
        
        db.session.commit()
        
        # For AJAX requests (autosave)
        if request.is_xhr:
            return jsonify({'success': True, 'message': 'Changes saved'})
        
        if not is_autosave:
            flash('Project updated successfully!', 'success')
            return redirect(url_for('project', project_id=project_id))
    
    # Populate form with existing values if it's a GET request
    if request.method == 'GET':
        form.name.data = project.name
        form.dri.data = project.dri
        form.team.data = project.team
        form.context.data = project.context
        form.why.data = project.why
        form.requirements.data = project.requirements
        form.launch.data = project.launch

    return render_template('edit.html', project=project, form=form)
    
@app.route('/projects/<int:project_id>/associate-objective', methods=['POST'])
@login_required
def associate_objective(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check for remove association request
    if 'remove_association' in request.form:
        # Get the objective name for the changelog before removing it
        objective_name = project.objective.title if project.objective else "Unknown objective"
        objective_name = sanitize_text(objective_name)
        
        # Remove the association
        project.objective_id = None
        project.objective = None
        
        # Create a changelog entry
        changelog = Changelog(
            project_id=project.id,
            user_id=current_user.id,
            change_type='objective_removed',
            content=f"Removed association with objective: {objective_name}"
        )
        db.session.add(changelog)
        db.session.commit()
        
        flash('Objective association removed.', 'success')
        return redirect(url_for('project', project_id=project.id))
    
    # Handle new or updated association
    objective_id = request.form.get('objective_id')
    if objective_id:
        objective = Goal.query.get(objective_id)
        if objective:
            # Check if this is a new association or update
            if project.objective_id != objective.id:
                # Store old objective name for changelog if updating
                old_objective = "None"
                if project.objective:
                    old_objective = sanitize_text(project.objective.title)
                
                # Sanitize the objective title for the changelog
                objective_title = sanitize_text(objective.title)
                
                # Update the association
                project.objective_id = objective.id
                project.objective = objective
                
                # Create a changelog entry
                if old_objective == "None":
                    change_type = 'objective_added'
                    content = f"Added association with objective: {objective_title}"
                else:
                    change_type = 'objective_changed'
                    content = f"Changed objective from '{old_objective}' to '{objective_title}'"
                
                changelog = Changelog(
                    project_id=project.id,
                    user_id=current_user.id,
                    change_type=change_type,
                    content=content
                )
                db.session.add(changelog)
                db.session.commit()
                
                flash('Project linked to objective successfully.', 'success')
            else:
                # No change was made
                flash('No changes to objective association.', 'info')
        else:
            flash('Selected objective not found.', 'error')
    else:
        flash('No objective selected.', 'warning')
    
    return redirect(url_for('project', project_id=project.id))

@app.route('/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    # Implement project delete logic here
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('dashboard'))
    
    
@app.route('/create', methods=['GET', 'POST'])
@login_required
def createProject():
    form = CreateProject()
    if request.method == 'POST' and form.validate_on_submit():
        # Sanitize all inputs consistently
        projectDetails = Project(
            name=sanitize_text(form.name.data),
            dri=sanitize_text(form.dri.data),
            team=sanitize_text(form.team.data),
            context=clean_html(form.context.data),
            why=clean_html(form.why.data),
            requirements=clean_html(form.requirements.data),
            launch=clean_html(form.launch.data), 
        )

        db.session.add(projectDetails)
        db.session.flush()  # This gets us the ID of the new project
        
        # Create changelog entry
        changelog = Changelog(
            change_type='create',
            content=f"Project '{sanitize_text(form.name.data)}' created",
            project_id=projectDetails.id,
            user_id=current_user.id
        )
        db.session.add(changelog)
        db.session.commit()
        
        flash('Project created successfully!')
        return redirect(url_for('index'))
        
    return render_template('create.html', form=form)

@app.route('/project/<int:project_id>/edit/', methods=('GET', 'POST'))
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
### Managing Objectives
########################################################

@app.route('/goals', methods=['GET', 'POST'])
def createGoal():
    form = CreateGoal()
    if form.validate_on_submit():
        new_goal = Goal(
            title=form.title.data,
            details=form.details.data,
            requested_by=form.requested_by.data,
            user_id=current_user.id
        )
        db.session.add(new_goal)
        db.session.commit()
        flash('Goal created successfully.')
        return redirect(url_for('createGoal'))

    goals = Goal.query.order_by(Goal.created.desc()).all()
    return render_template('objectives.html', form=form, goals=goals)


@app.route('/goals/edit', methods=['POST'])
@login_required
def editGoal():
    goal_id = request.form.get('goal_id')
    goal = Goal.query.get(goal_id)
    if goal:
        goal.title = request.form.get('title')
        goal.details = request.form.get('details')
        goal.requested_by = request.form.get('requested_by')
        db.session.commit()
        flash('Goal updated successfully.')
    else:
        flash('Goal not found.')
    return redirect(url_for('createGoal'))
    
    
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
@login_required
def add_to_cycle(project_id, sprint_id):
    if request.method == 'GET':
        # Get the sprint info for the changelog
        sprint = Sprint.query.get_or_404(sprint_id)
        project = Project.query.get_or_404(project_id)
        
        addToSprint = SprintProjectMap(
            sprint_id=sprint_id,
            project_id=project_id
        )

        db.session.add(addToSprint)
        
        # Create changelog entry
        changelog = Changelog(
            change_type='sprint_assignment',
            content=f"Project assigned to sprint: '{sprint.title}'",
            project_id=project_id,
            user_id=current_user.id
        )
        db.session.add(changelog)
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
@login_required
def api_move_project():
    """
    API endpoint to move a project to sprint, backlog, or discussion
    """
    data = request.json
    project_id = data.get('projectId')
    new_location = data.get('location')
    
    # Validate the required fields
    if not project_id or not new_location:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
    
    # Check if project exists
    project = Project.query.get(project_id)
    if project is None:
        return jsonify({"success": False, "message": "Project not found"}), 404
    
    # Record the old location for the changelog
    old_location = project.location
    
    # Update the project location
    project.location = new_location
    
    # Create changelog entry for location change
    if old_location != new_location:
        changelog = Changelog(
            change_type='location_change',
            content=f"Project moved from '{old_location}' to '{new_location}'",
            project_id=project_id,
            user_id=current_user.id,
            timestamp=datetime.utcnow()
        )
        db.session.add(changelog)
    
    # If project is moving out of sprint, remove it from sprint mappings
    if old_location == 'sprint' or new_location != 'sprint':
        # Find all sprint mappings for this project and remove them
        sprint_mappings = SprintProjectMap.query.filter_by(project_id=project_id).all()
        for mapping in sprint_mappings:
            # Add changelog for sprint removal
            sprint = Sprint.query.get(mapping.sprint_id)
            sprint_name = sprint.title if sprint else "Unknown Sprint"
            
            removal_changelog = Changelog(
                change_type='sprint_removal',
                content=f"Project removed from sprint: '{sprint_name}'",
                project_id=project_id,
                user_id=current_user.id,
                timestamp=datetime.utcnow()
            )
            db.session.add(removal_changelog)
            
            # Delete the mapping
            db.session.delete(mapping)
    
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
        
        
        
@app.route('/project/<int:project_id>/add_comment', methods=['POST'])
@login_required
def add_comment(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    form = CommentForm()
    
    if form.validate_on_submit():
        # Sanitize comment content
        sanitized_content = sanitize_text(form.content.data)
        
        comment = Comment(
            content=sanitized_content,
            project_id=project_id,
            user_id=current_user.id
        )
        
        db.session.add(comment)
        db.session.commit()
        
        flash('Comment added successfully!', 'success')
    else:
        flash('Error adding comment. Please check your input.', 'danger')
    
    return redirect(url_for('project', project_id=project_id))

@app.route('/comment/<int:comment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.filter_by(id=comment_id).first_or_404()
    
    # Check if current user is the author of the comment
    if comment.user_id != current_user.id:
        flash('You do not have permission to edit this comment.', 'danger')
        return redirect(url_for('project', project_id=comment.project_id))
    
    form = CommentForm()
    
    if request.method == 'GET':
        form.content.data = comment.content
    
    if form.validate_on_submit():
        comment.content = form.content.data
        db.session.commit()
        
        flash('Comment updated successfully!', 'success')
        return redirect(url_for('project', project_id=comment.project_id))
    
    return render_template('edit_comment.html', form=form, comment=comment)

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.filter_by(id=comment_id).first_or_404()
    
    # Check if current user is the author of the comment
    if comment.user_id != current_user.id:
        flash('You do not have permission to delete this comment.', 'danger')
        return redirect(url_for('project', project_id=comment.project_id))
    
    project_id = comment.project_id
    
    db.session.delete(comment)
    db.session.commit()
    
    flash('Comment deleted successfully!', 'success')
    return redirect(url_for('project', project_id=project_id))
    
    
########################################################
### Manage Cycles
########################################################

@app.route('/cycles/', methods=['GET', 'POST'])
def show_cycles():
    cycles = (
        Sprint.query
        .all()
    )
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
    return render_template('cycles.html', title='Naked Roadmap - View All Cycles', cycles=cycles, form=form)
    
    
@app.route('/cycles/details/<int:cycle_id>', methods=['GET', 'POST'])
def show_cycle_details():
    cycles = (
        Sprint.query
        .all()
    )
    selected_cycle = next((s for s in cycles if s.id == cycle_id), None)
    
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
    return render_template('cycles.html', title='Naked Roadmap - View All Cycles', cycles=cycles, form=form, selected_cycle=selected_cycle)
    
    
########################################################
### Cycle Planning Process
########################################################
    
@app.route('/planning/')
@login_required
def plan_sprint():
    projects = (
        Project.query
        .order_by(Project.created.desc())
        .all()
    )
    goals = (
        Goal.query
        .order_by(Goal.created.desc())
        .all()
    )
    
    sprints = (
        Sprint.query
        .filter(Sprint.status != "Completed")
        .order_by(Sprint.date_start.asc())
        .all()
    )
    
    # Find recommended sprint (next upcoming sprint or current sprint)
    today = datetime.now()
    recommended_sprint = None
    
    for sprint in sprints:
        # If sprint starts in the future or is currently active
        if sprint.date_end >= today.date():
            recommended_sprint = sprint
            break
    
    sprintlog = (
        SprintProjectMap.query
        .order_by(SprintProjectMap.order.asc())
        .all()
    )
    
    return render_template(
        'plan-cycle-1.html', 
        title='Plan a Cycle', 
        projects=projects, 
        goals=goals, 
        config=Config, 
        sprints=sprints, 
        recommended_sprint=recommended_sprint,
        sprintlog=sprintlog, 
        datetime=datetime, 
        today=today
    )

@app.route('/planning/cycle/<int:sprint_id>', methods=['GET'])
def planningStep2CycleSelected(sprint_id):
    projects = (
        Project.query
        .order_by(Project.created.desc())
        .filter(Project.location == "discussion")
        .all()
    )
    goals = (
        db.session.query(
            Goal,
            func.count(SprintProjectMap.id).label('sprint_project_count')
        )
        .outerjoin(Project, Project.objective_id == Goal.id)
        .outerjoin(SprintProjectMap, (SprintProjectMap.project_id == Project.id) & 
                                     (SprintProjectMap.sprint_id == sprint_id))
        .filter(Goal.status == 'Active')
        .group_by(Goal.id)
        .order_by(Goal.created.desc())
        .all()
    )
    selectedsprint = (
        Sprint.query
        .filter(Sprint.id == sprint_id)
        .first()
    )
    # Get all sprints ordered by start date
    sprints = (
        Sprint.query
        .filter(Sprint.status != "Completed")
        .order_by(Sprint.date_start.asc())
        .all()
    )
    sprintlog = (
        SprintProjectMap.query
        .filter(SprintProjectMap.sprint_id == sprint_id)
        .order_by(SprintProjectMap.order.asc())
        .all()
    )
    today = datetime.now()
    
    return render_template(
        'plan-cycle-2.html', 
        title='Plan a Cycle', 
        projects=projects, 
        goals=goals, 
        config=Config, 
        sprints=sprints, 
        sprintlog=sprintlog, 
        datetime=datetime, 
        today=today,
        selectedsprint=selectedsprint
    )
    
@app.route('/planning/cycle/create', methods=['GET', 'POST'])
def planningStep2CycleCreation():
    form = CreateSprint()
    
    try:
        if request.method == 'POST':
            new_cycle = Sprint(
                title=form.title.data,
                date_start=form.date_start.data,
                date_end=form.date_end.data
            )
    
            db.session.add(new_cycle)
            db.session.commit()

            flash('Congratulations, sprint created!')
            return redirect(url_for(planningStep2CycleSelected), sprint_id=new_cycle.id)
    except TypeError as e:
        print(f"Error: {e}")
    
    
########################################################
### API Routes for Sprint Selection
########################################################

@app.route('/api/sprint/<int:sprint_id>', methods=['GET'])
def api_get_sprint(sprint_id):
    """API endpoint to get sprint details including associated projects"""
    sprint = Sprint.query.get_or_404(sprint_id)
    
    # Get all projects associated with this sprint
    sprint_projects = SprintProjectMap.query.filter_by(sprint_id=sprint_id).all()
    
    # Build the response data
    sprint_data = {
        'id': sprint.id,
        'title': sprint.title,
        'date_start': sprint.date_start.isoformat() if sprint.date_start else None,
        'date_end': sprint.date_end.isoformat() if sprint.date_end else None,
        'projects': []
    }
    
    # Add project data
    for entry in sprint_projects:
        project = Project.query.get(entry.project_id)
        if project:
            sprint_data['projects'].append({
                'id': project.id,
                'name': project.name,
                'status': entry.status,
                'goal': entry.goal,
                'dri': project.dri,
                'team': project.team
            })
    
    return jsonify({'success': True, 'sprint': sprint_data})

@app.route('/api/create_sprint', methods=['POST'])
@login_required
def api_create_sprint():
    """API endpoint to create a new sprint and return its details"""
    form = CreateSprint()
    
    if form.validate_on_submit():
        try:
            new_sprint = Sprint(
                title=form.title.data,
                date_start=form.date_start.data,
                date_end=form.date_end.data
            )
            
            db.session.add(new_sprint)
            db.session.commit()
            
            # Return the new sprint data
            sprint_data = {
                'id': new_sprint.id,
                'title': new_sprint.title,
                'date_start': new_sprint.date_start.isoformat() if new_sprint.date_start else None,
                'date_end': new_sprint.date_end.isoformat() if new_sprint.date_end else None
            }
            
            return jsonify({'success': True, 'sprint': sprint_data})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    return jsonify({'success': False, 'message': 'Form validation failed'})

@app.route('/api/project/commit_to_sprint', methods=['POST'])
@login_required
def api_commit_to_sprint():
    """API endpoint to commit a project to the selected sprint or update its goal"""
    data = request.json
    project_id = data.get('projectId')
    sprint_id = data.get('sprintId')
    goal = data.get('goal', '')
    sprint_project_id = data.get('sprintProjectId')
    
    if not project_id or not sprint_id:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    # Check if project and sprint exist
    project = Project.query.get_or_404(project_id)
    sprint = Sprint.query.get_or_404(sprint_id)
    
    # If sprint_project_id is provided, update existing record
    if sprint_project_id:
        existing = SprintProjectMap.query.get(sprint_project_id)
        if existing:
            old_goal = existing.goal
            existing.goal = goal
            
            # Add changelog entry if goal changed
            if old_goal != goal:
                changelog = Changelog(
                    change_type='sprint_goal_update',
                    content=f"Sprint goal updated from '{old_goal}' to '{goal}'",
                    project_id=project_id,
                    user_id=current_user.id,
                    timestamp=datetime.utcnow()
                )
                db.session.add(changelog)
            
            db.session.commit()
            return jsonify({
                'success': True, 
                'message': 'Project goal updated in sprint',
                'sprintProjectId': existing.id
            })
        else:
            return jsonify({'success': False, 'message': 'Sprint project mapping not found'})
    
    # Check if this project is already in this sprint
    existing = SprintProjectMap.query.filter_by(
        project_id=project_id,
        sprint_id=sprint_id
    ).first()
    
    if existing:
        # Update the goal if it's changed
        old_goal = existing.goal
        if existing.goal != goal:
            existing.goal = goal
            
            # Add changelog entry
            changelog = Changelog(
                change_type='sprint_goal_update',
                content=f"Sprint goal updated from '{old_goal}' to '{goal}'",
                project_id=project_id,
                user_id=current_user.id,
                timestamp=datetime.utcnow()
            )
            db.session.add(changelog)
        
        # Ensure project location is set to 'active' when in sprint
        if project.location != 'active':
            old_location = project.location
            project.location = 'active'
            
            # Add changelog for location change
            location_changelog = Changelog(
                change_type='location_change',
                content=f"Project moved from '{old_location}' to 'active'",
                project_id=project_id,
                user_id=current_user.id,
                timestamp=datetime.utcnow()
            )
            db.session.add(location_changelog)
            
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Project goal updated in sprint',
            'sprintProjectId': existing.id
        })
    
    # Create new sprint-project mapping
    # First, get count of current projects to set the order
    current_count = SprintProjectMap.query.filter_by(sprint_id=sprint_id).count()
    
    new_mapping = SprintProjectMap(
        sprint_id=sprint_id,
        project_id=project_id,
        goal=goal,
        status="Planned",
        order=current_count + 1,
        added=datetime.utcnow()
    )
    
    db.session.add(new_mapping)
    
    # Update project location to 'active' when added to sprint
    old_location = project.location
    project.location = 'active'
    
    # Add changelog for location change
    changelog_location = Changelog(
        change_type='location_change',
        content=f"Project moved from '{old_location}' to 'active'",
        project_id=project_id,
        user_id=current_user.id,
        timestamp=datetime.utcnow()
    )
    db.session.add(changelog_location)
    
    # Add changelog entries for sprint assignment
    changelog_sprint = Changelog(
        change_type='sprint_assignment',
        content=f"Project assigned to sprint: '{sprint.title}' with goal: '{goal}'",
        project_id=project_id,
        user_id=current_user.id,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(changelog_sprint)
    
    try:
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Project committed to sprint successfully',
            'sprintProjectId': new_mapping.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
        
        
@app.route('/api/projects/reorder', methods=['POST'])
@login_required
def reorder_projects():
    """API endpoint to update the order of projects in a sprint"""
    data = request.json
    
    if not data or 'projects' not in data:
        return jsonify({'success': False, 'message': 'Missing project order data'})
    
    try:
        # Begin transaction
        for project_data in data['projects']:
            sprint_project = SprintProjectMap.query.get(project_data['id'])
            if sprint_project:
                sprint_project.order = project_data['order']
                
                # Add changelog entry for significant order changes (optional)
                # Only log if order changed by more than 2 positions to avoid clutter
                old_order = getattr(sprint_project, 'order', 0) or 0
                new_order = project_data['order']
                if abs(old_order - new_order) > 2:
                    changelog = Changelog(
                        change_type='project_reorder',
                        content=f"Project priority changed from position {old_order} to {new_order}",
                        project_id=sprint_project.project_id,
                        user_id=current_user.id
                    )
                    db.session.add(changelog)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Project order updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/project/toggle_critical', methods=['POST'])
@login_required
def toggle_project_critical():
    """API endpoint to toggle a project's critical status"""
    data = request.json
    
    if not data or 'sprintProjectId' not in data or 'critical' not in data:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    sprint_project_id = data['sprintProjectId']
    critical_status = data['critical']
    
    try:
        sprint_project = SprintProjectMap.query.get_or_404(sprint_project_id)
        
        # Update the critical status
        old_status = sprint_project.critical
        sprint_project.critical = critical_status
        
        # Add changelog entry if status changed
        if old_status != critical_status:
            status_text = "critical" if critical_status else "non-critical"
            changelog = Changelog(
                change_type='critical_status_change',
                # Sanitize the content text
                content=sanitize_text(f"Project marked as {status_text}"),
                project_id=sprint_project.project_id,
                user_id=current_user.id
            )
            db.session.add(changelog)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Project critical status updated to {critical_status}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
        
########################################################
### Cycle Closing
########################################################

@app.route('/api/activate_sprint', methods=['POST'])
@login_required
def activate_sprint():
    """API endpoint to activate a sprint and optionally send notification emails"""
    try:
        # Get form data
        sprint_id = request.form.get('sprint_id')
        send_email = request.form.get('send_email') == 'on'
        email_addresses = request.form.get('email_addresses', '')
        
        if not sprint_id:
            return jsonify({'success': False, 'message': 'Sprint ID is required'}), 400
        
        # Get the sprint
        sprint = Sprint.query.get_or_404(sprint_id)
        
        # Update the sprint status
        sprint.status = 'Active'
        
        # Create changelog entry
        changelog = Changelog(
            change_type='sprint_activation',
            content=f"Sprint '{sprint.title}' activated by {current_user.username}",
            # Use the first project's ID for the changelog (or adjust as needed)
            project_id=SprintProjectMap.query.filter_by(sprint_id=sprint_id).first().project_id,
            user_id=current_user.id,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(changelog)
        db.session.commit()
        
        # Send email notification if requested
        if send_email and email_addresses:
            send_sprint_notification(sprint_id, email_addresses.split(','))
        
        # Return success
        return jsonify({
            'success': True,
            'message': f"Sprint '{sprint.title}' has been activated successfully.",
            'redirect_url': url_for('index')  # Can be changed to a sprint details page
        })
        
    except Exception as e:
        print(f"Error activating sprint: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


def send_sprint_notification(sprint_id, recipients):
    """Send an email notification about the activated sprint"""
    try:
        # Get sprint and related data
        sprint = Sprint.query.get(sprint_id)
        sprint_projects = (
            SprintProjectMap.query
            .filter_by(sprint_id=sprint_id)
            .order_by(SprintProjectMap.order)
            .all()
        )
        
        # Analytics data
        teams = {}
        dris = {}
        objective_ids = set()
        critical_count = 0
        
        for entry in sprint_projects:
            project = entry.project
            
            # Count projects by team
            team = project.team
            teams[team] = teams.get(team, 0) + 1
            
            # Count projects by DRI
            dri = project.dri
            dris[dri] = dris.get(dri, 0) + 1
            
            # Count objectives
            if project.objective_id:
                objective_ids.add(project.objective_id)
            
            # Count critical projects
            if entry.critical:
                critical_count += 1
        
        # Create HTML email content using a template
        html_content = render_sprint_email_template(sprint, sprint_projects, {
            'teams': teams,
            'dris': dris,
            'objective_count': len(objective_ids),
            'critical_count': critical_count,
            'total_projects': len(sprint_projects)
        })
        
        # Send the email
        send_html_email(
            subject=f"Sprint Activated: {sprint.title}",
            recipients=recipients,
            html_content=html_content
        )
        
        return True
        
    except Exception as e:
        print(f"Error sending sprint notification: {str(e)}")
        return False


def render_sprint_email_template(sprint, sprint_projects, analytics):
    """Render the HTML email template for sprint notification"""
    template_str = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Sprint Activated: {{ sprint.title }}</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; }
            .header { padding: 20px 0; border-bottom: 1px solid #eee; }
            .logo { max-height: 40px; margin-bottom: 20px; }
            .sprint-details { background-color: #f5f7f9; padding: 20px; border-radius: 6px; margin: 20px 0; }
            .sprint-title { font-size: 24px; font-weight: bold; margin-bottom: 10px; color: #1a56db; }
            .sprint-meta { margin-bottom: 15px; }
            .projects-list { margin: 30px 0; }
            .project-item { padding: 15px 0; border-bottom: 1px solid #eee; }
            .project-title { font-weight: bold; font-size: 18px; }
            .project-meta { color: #666; font-size: 14px; }
            .project-goal { background-color: #f0f4ff; padding: 10px; border-radius: 4px; margin-top: 10px; }
            .critical-badge { background-color: #feefb3; color: #9f6000; padding: 3px 6px; border-radius: 4px; font-size: 12px; }
            .analytics { margin-top: 30px; padding: 20px; background-color: #f9f9f9; border-radius: 6px; }
            .analytics-title { font-size: 20px; margin-bottom: 15px; }
            .analytics-grid { display: flex; flex-wrap: wrap; gap: 15px; margin-bottom: 20px; }
            .analytics-card { flex: 1; min-width: 120px; background: white; border-radius: 6px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
            .analytics-value { font-size: 24px; font-weight: bold; color: #1a56db; }
            .analytics-label { font-size: 14px; color: #666; }
            .breakdown-section { margin-top: 20px; }
            .breakdown-title { font-size: 16px; margin-bottom: 10px; }
            .breakdown-item { display: flex; align-items: center; margin-bottom: 5px; }
            .breakdown-label { flex: 1; }
            .breakdown-value { font-weight: bold; margin-left: 10px; }
            .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }
        </style>
    </head>
    <body>
        <div class="header">
            <img src="cid:logo" alt="Company Logo" class="logo">
            <h1>Sprint Activated: {{ sprint.title }}</h1>
        </div>
        
        <div class="sprint-details">
            <div class="sprint-title">{{ sprint.title }}</div>
            <div class="sprint-meta">
                <strong>Timeline:</strong> {{ sprint.date_start.strftime('%b %d, %Y') }} - {{ sprint.date_end.strftime('%b %d, %Y') }}<br>
                <strong>Duration:</strong> {{ (sprint.date_end - sprint.date_start).days }} days<br>
                <strong>Projects:</strong> {{ analytics.total_projects }} total ({{ analytics.critical_count }} critical)
            </div>
        </div>
        
        <h2>Sprint Commitments</h2>
        <div class="projects-list">
            {% for entry in sprint_projects %}
            {% set project = entry.project %}
            <div class="project-item">
                <div class="project-title">
                    {{ project.name }}
                    {% if entry.critical %}
                    <span class="critical-badge">CRITICAL</span>
                    {% endif %}
                </div>
                <div class="project-meta">
                    <strong>Owner:</strong> {{ project.dri }} | <strong>Team:</strong> {{ project.team }}
                    {% if project.objective %}
                    | <strong>Objective:</strong> {{ project.objective.title }}
                    {% endif %}
                </div>
                <div class="project-goal">
                    <strong>Goal:</strong> {{ entry.goal }}
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="analytics">
            <div class="analytics-title">Sprint Analytics</div>
            
            <div class="analytics-grid">
                <div class="analytics-card">
                    <div class="analytics-value">{{ analytics.total_projects }}</div>
                    <div class="analytics-label">Total Projects</div>
                </div>
                <div class="analytics-card">
                    <div class="analytics-value">{{ analytics.objective_count }}</div>
                    <div class="analytics-label">Objectives Supported</div>
                </div>
                <div class="analytics-card">
                    <div class="analytics-value">{{ analytics.critical_count }}</div>
                    <div class="analytics-label">Critical Projects</div>
                </div>
            </div>
            
            <div class="breakdown-section">
                <div class="breakdown-title">Projects by Team</div>
                {% for team, count in analytics.teams.items() %}
                <div class="breakdown-item">
                    <div class="breakdown-label">{{ team }}</div>
                    <div class="breakdown-value">{{ count }}</div>
                </div>
                {% endfor %}
            </div>
            
            <div class="breakdown-section">
                <div class="breakdown-title">Projects by DRI</div>
                {% for dri, count in analytics.dris.items() %}
                <div class="breakdown-item">
                    <div class="breakdown-label">{{ dri }}</div>
                    <div class="breakdown-value">{{ count }}</div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="footer">
            <p>This is an automated notification from the Roadmap Planning Tool. Please do not reply to this email.</p>
        </div>
    </body>
    </html>
    """
    
    template = Template(template_str)
    return template.render(sprint=sprint, sprint_projects=sprint_projects, analytics=analytics)


def send_html_email(subject, recipients, html_content):
    """Send an HTML email with the sprint notification using app configuration"""
    try:
        # Get email configuration from the database
        smtp_server = get_config('smtp_server')
        smtp_port = int(get_config('smtp_port', 587))
        sender_email = get_config('smtp_email')
        sender_password = get_config('smtp_password')
        email_enabled = get_config('email_enabled') == 'true'
        
        if not all([smtp_server, smtp_port, sender_email, sender_password, email_enabled]):
            print("Email settings are incomplete or email notifications are disabled")
            return False
        
        # Create message
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipients)
        
        # Attach HTML content
        msg_html = MIMEText(html_content, 'html')
        msg.attach(msg_html)
        
        # Attach company logo for inline display
        with open('app/static/fig-icon.svg', 'rb') as f:
            logo_data = f.read()
            logo_img = MIMEImage(logo_data)
            logo_img.add_header('Content-ID', '<logo>')
            logo_img.add_header('Content-Disposition', 'inline', filename='company-logo.svg')
            msg.attach(logo_img)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        print(f"Email sent successfully to {len(recipients)} recipients")
        return True
    
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False
        
        
## ################################
## Settings Pages
## ################################


@app.route('/settings')
@login_required
def settings():
    """Settings page for application configuration"""
    # Get all configuration values
    configs = {}
    config_records = AppConfig.query.all()
    
    for config in config_records:
        # Don't expose the actual password value to the frontend
        if config.key == 'smtp_password' and config.value:
            configs[config.key] = '********'
        else:
            configs[config.key] = config.value
    
    return render_template('settings.html', 
                           title='Application Settings', 
                           configs=configs)

@app.route('/settings/general', methods=['POST'])
@login_required
def save_general_settings():
    """Save general application settings"""
    try:
        app_name = request.form.get('app_name')
        
        if app_name:
            set_config('app_name', app_name, 'Application name displayed in the UI')
        
        # Get updated configs for the template
        configs = {config.key: config.value for config in AppConfig.query.all()}
        
        return render_template('settings.html', 
                               title='Application Settings', 
                               configs=configs, 
                               success_message='General settings saved successfully.')
    
    except Exception as e:
        # Get configs for the template
        configs = {config.key: config.value for config in AppConfig.query.all()}
        
        return render_template('settings.html', 
                               title='Application Settings', 
                               configs=configs, 
                               error_message=f'Error saving settings: {str(e)}')

@app.route('/settings/email', methods=['POST'])
@login_required
def save_email_settings():
    """Save email configuration settings"""
    try:
        smtp_server = request.form.get('smtp_server')
        smtp_port = request.form.get('smtp_port')
        smtp_email = request.form.get('smtp_email')
        smtp_password = request.form.get('smtp_password')
        email_enabled = 'true' if request.form.get('email_enabled') else 'false'
        
        # Update configuration values
        set_config('smtp_server', smtp_server, 'SMTP server for sending emails')
        set_config('smtp_port', smtp_port, 'SMTP port')
        set_config('smtp_email', smtp_email, 'Email address used for sending notifications')
        
        # Only update password if it's not the masked value
        if smtp_password and smtp_password != '********':
            # In a production environment, you would want to encrypt this
            set_config('smtp_password', smtp_password, 'Password for the email account')
        
        set_config('email_enabled', email_enabled, 'Whether email notifications are enabled')
        
        # Get updated configs for the template
        configs = {}
        for config in AppConfig.query.all():
            if config.key == 'smtp_password' and config.value:
                configs[config.key] = '********'
            else:
                configs[config.key] = config.value
        
        return render_template('settings.html', 
                               title='Application Settings', 
                               configs=configs, 
                               success_message='Email settings saved successfully.')
    
    except Exception as e:
        # Get configs for the template
        configs = {}
        for config in AppConfig.query.all():
            if config.key == 'smtp_password' and config.value:
                configs[config.key] = '********'
            else:
                configs[config.key] = config.value
        
        return render_template('settings.html', 
                               title='Application Settings', 
                               configs=configs, 
                               error_message=f'Error saving settings: {str(e)}')

@app.route('/api/test_email', methods=['POST'])
@login_required
def test_email():
    """Test email configuration by sending a test email"""
    try:
        data = request.json
        recipient_email = data.get('email')
        
        if not recipient_email:
            return jsonify({'success': False, 'message': 'Recipient email is required'})
        
        # Get email configuration
        smtp_server = get_config('smtp_server')
        smtp_port = get_config('smtp_port')
        smtp_email = get_config('smtp_email')
        smtp_password = get_config('smtp_password')
        email_enabled = get_config('email_enabled') == 'true'
        
        if not all([smtp_server, smtp_port, smtp_email, smtp_password, email_enabled]):
            return jsonify({
                'success': False, 
                'message': 'Email settings are incomplete or email notifications are disabled'
            })
        
        # Send test email
        app_name = get_config('app_name', 'Roadmap Planning Tool')
        subject = f"Test Email from {app_name}"
        html_content = f"""
        <html>
        <body>
            <h2>Test Email</h2>
            <p>This is a test email from {app_name}.</p>
            <p>If you're receiving this email, your email configuration is working correctly.</p>
        </body>
        </html>
        """
        
        # Use the send_html_email function from previous artifact
        success = send_test_html_email(
            subject=subject,
            recipient=recipient_email,
            html_content=html_content
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Test email sent successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send test email'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def send_test_html_email(subject, recipient, html_content):
    """Send a test HTML email"""
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        # Get email configuration
        smtp_server = get_config('smtp_server')
        smtp_port = int(get_config('smtp_port', 587))
        sender_email = get_config('smtp_email')
        sender_password = get_config('smtp_password')
        
        if not all([smtp_server, smtp_port, sender_email, sender_password]):
            return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient
        
        # Attach HTML content
        msg_html = MIMEText(html_content, 'html')
        msg.attach(msg_html)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True
    
    except Exception as e:
        print(f"Error sending test email: {str(e)}")
        return False


@app.route('/api/check_email_config', methods=['GET'])
def check_email_config():
    """Check if email is configured and enabled"""
    smtp_server = get_config('smtp_server')
    smtp_port = get_config('smtp_port')
    smtp_email = get_config('smtp_email')
    smtp_password = get_config('smtp_password')
    email_enabled = get_config('email_enabled') == 'true'
    
    is_configured = all([smtp_server, smtp_port, smtp_email, smtp_password, email_enabled])
    
    return jsonify({
        'configured': is_configured
    })
    
## ##############################
## Analytics
## ##############################

@app.route('/analytics')
@login_required
def analytics():
    """
    Analytics and insights dashboard for project, team, and goal performance metrics.
    Provides executives with data to optimize team planning and resource allocation.
    """
    # Get team analytics data - active projects
    teams_active = db.session.query(
        Project.team, 
        func.count(Project.id).label('project_count')
    ).filter(
        Project.location == 'active'
    ).group_by(
        Project.team
    ).all()
    
    # Get team analytics data - completed projects
    teams_historic = db.session.query(
        Project.team, 
        func.count(Project.id).label('project_count')
    ).filter(
        Project.location == 'completed'
    ).group_by(
        Project.team
    ).all()
    
    # Get user load data (active projects)
    user_active_load = db.session.query(
        Project.dri, 
        func.count(Project.id).label('project_count')
    ).filter(
        Project.location == 'active'
    ).group_by(
        Project.dri
    ).all()

    # Get user load data (historic/completed projects)
    user_historic_load = db.session.query(
        Project.dri, 
        func.count(Project.id).label('project_count')
    ).filter(
        Project.location == 'completed'
    ).group_by(
        Project.dri
    ).all()
    
    # Project completion stats
    completed_projects = Project.query.filter(Project.location == 'completed').count()
    total_projects = Project.query.count()
    
    # Project type distribution (tasks vs. projects)
    project_types = db.session.query(
        Project.type, 
        func.count(Project.id).label('count')
    ).group_by(
        Project.type
    ).all()
    
    # Get sprint/cycle data
    sprints = Sprint.query.all()
    avg_sprint_duration = 0
    if sprints:
        total_days = sum([(s.date_end - s.date_start).days for s in sprints if s.date_start and s.date_end])
        avg_sprint_duration = total_days / len(sprints) if len(sprints) > 0 else 0
    
    # Commitment completion percentage
    sprint_projects = SprintProjectMap.query
    completed_commitments = sprint_projects.filter(SprintProjectMap.status == 'Done').count()
    total_commitments = sprint_projects.count()
    commitment_completion = 0
    if total_commitments > 0:
        commitment_completion = (completed_commitments / total_commitments) * 100
    
    # Calculate average days to complete a commitment
    completed_commitments_data = db.session.query(SprintProjectMap) \
        .filter(SprintProjectMap.status == 'Done') \
        .all()
    
    # For each completed commitment, calculate days from addition to completion
    # This is an approximation since we don't have actual completion dates stored
    avg_days_to_complete = 0
    if completed_commitments_data:
        commitment_durations = []
        for commitment in completed_commitments_data:
            sprint = Sprint.query.get(commitment.sprint_id)
            if sprint and sprint.date_start and sprint.date_end:
                # Approximate duration as the sprint duration since we don't have exact completion dates
                duration = (sprint.date_end - sprint.date_start).days
                commitment_durations.append(duration)
        
        if commitment_durations:
            avg_days_to_complete = sum(commitment_durations) / len(commitment_durations)
    
    # Average commitments per cycle
    avg_commitments_per_cycle = 0
    cycle_commitments = db.session.query(
        SprintProjectMap.sprint_id,
        func.count(SprintProjectMap.id).label('commitment_count')
    ).group_by(
        SprintProjectMap.sprint_id
    ).all()
    
    if cycle_commitments:
        avg_commitments_per_cycle = sum([c.commitment_count for c in cycle_commitments]) / len(cycle_commitments)
    
    # Goal achievement stats
    goals_achieved = Goal.query.filter(Goal.status == 'Achieved').count()
    total_goals = Goal.query.count()
    
    # Average projects per goal
    avg_projects_per_goal = 0
    goals_with_projects = db.session.query(
        Goal.id, 
        func.count(Project.id).label('project_count')
    ).join(
        Project, 
        Goal.id == Project.objective_id
    ).group_by(
        Goal.id
    ).all()
    
    if goals_with_projects:
        avg_projects_per_goal = sum([g.project_count for g in goals_with_projects]) / len(goals_with_projects)
    
    # Critical vs. Non-Critical Project Ratio
    critical_projects = SprintProjectMap.query.filter(SprintProjectMap.critical == True).count()
    critical_percentage = (critical_projects / total_commitments * 100) if total_commitments > 0 else 0
    
    # Calculate team balance - standard deviation of project distribution
    team_balance = 0
    if teams_active:
        team_counts = [t.project_count for t in teams_active]
        if team_counts:
            mean = sum(team_counts) / len(team_counts)
            variance = sum((count - mean) ** 2 for count in team_counts) / len(team_counts)
            team_balance = variance ** 0.5  # standard deviation
    
    # Get historical data for trends (projects completed by month)
    current_date = datetime.now()
    six_months_ago = current_date - timedelta(days=180)
    
    monthly_completion = db.session.query(
        func.strftime('%Y-%m', Project.created).label('month'),
        func.count(Project.id).label('count')
    ).filter(
        Project.location == 'completed',
        Project.created >= six_months_ago
    ).group_by('month').all()
    
    # Project complexity metrics (using number of comments as a proxy)
    project_complexity = db.session.query(
        Project.id,
        Project.name,
        func.count(Comment.id).label('comment_count')
    ).outerjoin(
        Comment
    ).group_by(
        Project.id
    ).order_by(
        func.count(Comment.id).desc()
    ).limit(5).all()
    
    # Calculate cycle health score (composite metric)
    cycle_health_score = 0
    if total_commitments > 0 and total_goals > 0:
        cycle_health_score = (
            (commitment_completion / 100) * 0.6 + 
            ((goals_achieved / total_goals) * 100 / 100) * 0.4
        ) * 100
    
    return render_template(
        'analytics.html',
        title='Analytics & Insights',
        teams_active=teams_active,
        teams_historic=teams_historic,
        user_active_load=user_active_load,
        user_historic_load=user_historic_load,
        completed_projects=completed_projects,
        total_projects=total_projects,
        project_types=project_types,
        avg_sprint_duration=avg_sprint_duration,
        commitment_completion=commitment_completion,
        completed_commitments=completed_commitments,
        total_commitments=total_commitments,
        avg_days_to_complete=avg_days_to_complete,
        avg_commitments_per_cycle=avg_commitments_per_cycle,
        goals_achieved=goals_achieved,
        total_goals=total_goals,
        avg_projects_per_goal=avg_projects_per_goal,
        critical_projects=critical_projects,
        critical_percentage=critical_percentage,
        team_balance=team_balance,
        monthly_completion=monthly_completion,
        project_complexity=project_complexity,
        cycle_health_score=cycle_health_score
    )
    
@app.route('/project/<int:project_id>/update_type', methods=['POST'])
def update_project_type(project_id):
    if request.method == 'POST':
        data = request.get_json()
        project_type = data.get('type')
        
        if project_type not in ['project', 'task']:
            return jsonify({'error': 'Invalid project type'}), 400
        
        project = Project.query.get_or_404(project_id)
        old_type = project.type if project.type else 'Not set'
        project.type = project_type
        db.session.commit()
        
        try:
            # Create changelog entry using the correct fields from your model
            user_id = current_user.id if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else None
            
            # Ensure we have a user_id since it's not nullable
            if user_id is None:
                # You might want to use a system user ID or handle this differently
                # depending on your application's requirements
                return jsonify({'success': True, 'type': project_type, 'warning': 'No user detected, changelog not created'})
            
            changelog = Changelog(
                project_id=project_id,
                change_type='edit',  # This is 'change_type' in your model
                content=f'Project type changed from "{old_type}" to "{project_type}"',  # This is 'content' in your model
                user_id=user_id
                # timestamp will be automatically set by the default
            )
            db.session.add(changelog)
            db.session.commit()
        except Exception as e:
            # Log the error but don't fail the request
            print(f"Error creating changelog: {str(e)}")
            # Don't roll back the project change even if changelog fails
        
        return jsonify({'success': True, 'type': project_type})