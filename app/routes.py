from app import app, db, login
from app.forms import LoginForm, RegistrationForm, CreateProject, CreateGoal, CreateSprint, CommentForm
from app.models import User, Project, Goal, Sprint, SprintProjectMap, Comment, Changelog, AppConfig, get_config, set_config, get_secure_config, set_secure_config, Role
import sqlalchemy as sa
from flask import Flask, render_template, request, url_for, flash, redirect, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.exceptions import abort
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlsplit, urlparse, urljoin
from config import Config
from datetime import datetime, timedelta
from flask_wtf.csrf import generate_csrf
from . import utils
from .utils import ALLOWED_TAGS, ALLOWED_ATTRIBUTES, clean_html, sanitize_text , is_valid_email, validate_email_list
from .auth import admin_required, project_access_required, project_edit_required
import bleach
from sqlalchemy import func
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import os
from jinja2 import Template
import json

"""
Notes on Route Decorators:
    @login_required # Should be used everywhere if login needed.
    @admin_required # Admin pages, i.e., settings page
        
    ### Authorization on routes:
    ### VIEW
    if not current_user.can_view_project(project):
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('index'))
    ### EDIT
    if not current_user.can_edit_project(project):
        flash('You do not have permission to edit this project.', 'danger')
        return redirect(url_for('project', project_id=project_id))
    ### DELETE
    if not current_user.can_delete_project(project):
        flash('You do not have permission to delete this project.', 'danger')
        return redirect(url_for('project', project_id=project_id))
"""


########################################################
### Decorators
########################################################

@app.before_request
def validate_request_size():
    """
    Validates the request URL length to prevent DoS attacks.
    """
    # Most web servers limit URLs to around 2000 characters
    # Setting a reasonable limit for our application
    max_url_length = 2000
    
    if request.url and len(request.url) > max_url_length:
        abort(414)  # HTTP 414 URI Too Long
        
@app.errorhandler(414)
def uri_too_long(error):
    """Handle URI Too Long errors"""
    flash('The requested URL was too long. Please try again with a shorter URL.', 'error')
    return redirect(url_for('index')), 414

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())
    
########################################################
### Logging in and Out
########################################################
    
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
        
        # Use the safe redirect function instead of directly using 'next'
        next_page = get_safe_redirect()
        return redirect(next_page)
        
    return render_template('login.html', title='Sign In', form=form)

def is_safe_url(target):
    """
    Validates if a URL is safe to redirect to by checking if it's relative
    or matches the current host.
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    
    # Only allow redirects to the same host or relative URLs
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc and \
           test_url.path != '/login'  # Prevent redirect loops to login
           
def get_safe_redirect():
    """
    Gets the 'next' parameter and validates it's safe.
    Returns a safe URL, defaulting to the index page.
    """
    next_url = request.args.get('next')
    
    # Basic checks for potential redirect loops or excessive length
    if not next_url:
        return url_for('index')
    
    # Check for redirect loops by limiting the number of 'next=' occurrences
    if next_url.count('next=') > 1 or len(next_url) > 2000:
        return url_for('index')
    
    # Validate that the URL is safe
    if not is_safe_url(next_url):
        return url_for('index')
        
    return next_url
    
@app.route('/logout')
def logout():
    logout_user()
    
    next_page = get_safe_redirect()
    return redirect(next_page or url_for('index'))
    
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
        
        # Assign default role
        default_role = Role.query.filter_by(name='team_member').first()
        if default_role:
            user.roles.append(default_role)
            db.session.commit()
            
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)
    
########################################################
### Index
########################################################

@app.route('/')
@app.route('/index')
@login_required
def index():
    # Get the oldest active sprint first
    active_sprint = (
        Sprint.query
        .filter(Sprint.status == 'Active')
        .order_by(Sprint.date_start.asc())
        .first()
    )
    
    # If no active sprint, get the most recent one
    if not active_sprint:
        active_sprint = (
            Sprint.query
            .order_by(Sprint.date_start.desc())
            .first()
        )
    
    # Count active sprints to determine if we should show the "see other active cycles" link
    active_sprint_count = (
        Sprint.query
        .filter(Sprint.status == 'Active')
        .count()
    )
    
    # Get sprint commitments for the active sprint
    sprintlog = []
    if active_sprint:
        sprintlog = (
            SprintProjectMap.query
            .filter(SprintProjectMap.sprint_id == active_sprint.id)
            .order_by(SprintProjectMap.order.asc())
            .all()
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
    
    # Get all sprints for reference
    sprints = (
        Sprint.query
        .order_by(Sprint.date_start.desc())
        .all()
    )
    
    # Get recent comments and changes
    comments = (
        Comment.query
        .order_by(Comment.created_at.desc())
        .limit(5)
    )
    
    # Get recent changes grouped by project (last 10 changes)
    recent_changes_raw = (
        Changelog.query
        .order_by(Changelog.timestamp.desc())
        .limit(10)
        .all()
    )
    
    # Group changes by project
    changes_by_project = {}
    for change in recent_changes_raw:
        project_id = change.project_id
        if project_id not in changes_by_project:
            changes_by_project[project_id] = {
                'project': change.project,
                'changes': [],
                'latest_timestamp': change.timestamp
            }
        changes_by_project[project_id]['changes'].append(change)
    
    # Sort projects by most recent change timestamp
    changes = sorted(
        changes_by_project.values(),
        key=lambda x: x['latest_timestamp'],
        reverse=True
    )
    
    # Get active projects with counts for different statuses
    active_projects = (
        Project.query
        .filter(Project.status == 'Active')
        .order_by(Project.created.desc())
        .all()
    )
    
    # Count projects by location
    backlog_count = Project.query.filter(Project.location == 'backlog').count()
    discussion_count = Project.query.filter(Project.location == 'discussion').count()
    
    today = datetime.now()
    return render_template(
        'index.html', 
        title='Home', 
        active_projects=active_projects,
        backlog_count=backlog_count,
        discussion_count=discussion_count,
        goals=goals, 
        config=Config, 
        sprints=sprints,
        active_sprint=active_sprint,
        active_sprint_count=active_sprint_count,
        sprintlog=sprintlog, 
        datetime=datetime, 
        today=today, 
        comments=comments, 
        changes=changes
    )
    
########################################################
### Managing Projects
########################################################

@app.route('/project/<int:project_id>')
@login_required
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
    
@app.route('/project/<int:project_id>/edit/', methods=('GET', 'POST'))
@login_required
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
    
@app.route('/<int:project_id>/delete', methods=('POST',))
@login_required
def delete(project_id):
    deleteProject = db.session.query(Project).filter(Project.id==project_id).first()
    db.session.delete(deleteProject)
    db.session.commit()
    # db.session.scalar(Project.query.filter_by(id=project_id).delete())
    flash('Project was successfully deleted!')
    return redirect(url_for('index'))
    
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
            user_id=current_user.id 
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

@app.route('/projects')
@login_required 
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
### Commenting on Projects
########################################################

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
### Managing Objectives & Goals
########################################################

@app.route('/goals', methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
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
        
        
########################################################
### Manage Cycles
########################################################

@app.route('/cycles/', methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
            return redirect(url_for('planningStep2CycleSelected', sprint_id=new_cycle.id))
    except TypeError as e:
        print(f"Error: {e}")
        flash(f'Error creating sprint: {str(e)}', 'error')
        return redirect(url_for('plan_sprint'))
    
    # This is the missing return statement for GET requests
    return render_template('plan-cycle-1.html', form=form)
    
    
########################################################
### API Routes for Sprint Selection
########################################################

@app.route('/api/sprint/<int:sprint_id>', methods=['GET'])
@login_required
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
    return render_template(
        'emails/sprint_activated.html',
        sprint=sprint,
        sprint_projects=sprint_projects,
        analytics=analytics
    )


def send_html_email(subject, recipients, html_content):
    """Send an HTML email with the sprint notification using app configuration"""
    try:
        # Get email configuration from the database with decryption
        smtp_server = get_config('smtp_server')
        smtp_port = int(get_config('smtp_port', 587))
        sender_email = get_config('smtp_email')
        sender_password = get_config('smtp_password')  # This will be decrypted
        email_enabled = get_config('email_enabled') == 'true'
        
        if not all([smtp_server, smtp_port, sender_email, sender_password, email_enabled]):
            print("Email settings are incomplete or email notifications are disabled")
            return False
        
        # Validate recipient emails
        validated, valid_emails, invalid_emails = validate_email_list(','.join(recipients))
        if not validated:
            print(f"Invalid email addresses found: {invalid_emails}")
            return False
            
        if not valid_emails:
            print("No valid email addresses provided")
            return False
        
        # Create message
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ', '.join(valid_emails)
        
        # Add anti-spoofing headers
        msg['X-Mailer'] = 'Naked Roadmap Email Service'
        msg['Message-ID'] = f"<{os.urandom(16).hex()}@{smtp_server.split('.', 1)[0]}>"
        
        # Attach HTML content
        msg_html = MIMEText(html_content, 'html')
        msg.attach(msg_html)
        
        # Send email
        import smtplib
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        print(f"Email sent successfully to {len(valid_emails)} recipients")
        return True
    
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False
        
        
## ################################
## Settings Pages
## ################################


@app.route('/settings')
@login_required
@admin_required
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
    
    return render_template('settings/settings.html', 
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
        
        return render_template('settings/settings.html', 
                               title='Application Settings', 
                               configs=configs, 
                               error_message=f'Error saving settings: {str(e)}')

@app.route('/settings/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    roles = Role.query.all()
    return render_template('settings/users.html', users=users, roles=roles)

@app.route('/settings/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    """Admin interface to edit user roles"""
    user = User.query.get_or_404(user_id)
    roles = Role.query.all()
    
    if request.method == 'POST':
        # Update user roles
        new_role_ids = request.form.getlist('roles')
        
        # Clear existing roles
        user.roles = []
        for role_id in new_role_ids:
            role = Role.query.get(int(role_id))
            if role:
                user.roles.append(role)
                
        db.session.commit()
        flash(f'User {user.username} updated successfully', 'success')
        return redirect(url_for('admin_users'))
        
    return render_template('settings/edit_user.html', user=user, roles=roles)




@app.route('/api/test_email', methods=['POST'])
@login_required
def test_email():
    """Test email configuration by sending a test email"""
    try:
        data = request.json
        recipient_email = data.get('email')
        
        if not recipient_email:
            return jsonify({'success': False, 'message': 'Recipient email is required'})
        
        # Validate email address
        if not is_valid_email(recipient_email):
            return jsonify({'success': False, 'message': 'Invalid email address format'})
        
        # Get email configuration
        smtp_server = get_config('smtp_server')
        smtp_port = get_config('smtp_port')
        smtp_email = get_config('smtp_email')
        smtp_password = get_config('smtp_password')  # This will be decrypted
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
            <p>Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </body>
        </html>
        """
        
        success = send_html_email(
            subject=subject,
            recipients=[recipient_email],
            html_content=html_content
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Test email sent successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send test email. Check server logs for details.'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
        
        
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
@login_required
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
@login_required
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
        
        
        
# ######################
# Sprint Management
# ######################

@app.route('/sprint/<int:sprint_id>')
@login_required
def sprint_detail(sprint_id):
    # Get the requested sprint
    sprint = Sprint.query.get_or_404(sprint_id)
    
    # Get sprint commitments for this sprint
    sprintlog = (
        SprintProjectMap.query
        .filter(SprintProjectMap.sprint_id == sprint_id)
        .order_by(SprintProjectMap.order.asc())
        .all()
    )
    
    # Calculate sprint progress
    total_days = (sprint.date_end - sprint.date_start).days if sprint.date_start and sprint.date_end else 1
    if total_days <= 0:
        total_days = 1
    
    today_date = datetime.now().date()
    days_elapsed = (today_date - sprint.date_start).days if sprint.date_start else 0
    percentage_time = (days_elapsed / total_days) * 100
    
    if percentage_time > 100:
        percentage_time = 100
    elif percentage_time < 0:
        percentage_time = 0
    
    # Calculate completion progress
    done_count = len([entry for entry in sprintlog if entry.status == "Done"])
    total_count = len(sprintlog)
    percentage_projects = (done_count / total_count) * 100 if total_count > 0 else 0
    
    # Get comments and changes related to this sprint
    # Projects in this sprint
    sprint_project_ids = [entry.project_id for entry in sprintlog]
    
    comments = []
    changes = []
    
    if sprint_project_ids:
        comments = (
            Comment.query
            .filter(Comment.project_id.in_(sprint_project_ids))
            .order_by(Comment.created_at.desc())
            .limit(10)
            .all()
        )
        
        changes = (
            Changelog.query
            .filter(Changelog.project_id.in_(sprint_project_ids))
            .order_by(Changelog.timestamp.desc())
            .limit(10)
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
    
    # Calculate the teams involved
    teams_involved = set()
    dris_involved = set()
    for entry in sprintlog:
        project = Project.query.get(entry.project_id)
        if project:
            teams_involved.add(project.team)
            dris_involved.add(project.dri)

    # Calculate complexity for display
    comment_count = len(comments)
    change_count = len(changes)
    
    return render_template(
        'sprint-detail.html',
        title=f'Sprint: {sprint.title}',
        sprint=sprint,
        sprintlog=sprintlog,
        today=datetime.now(),
        datetime=datetime,
        percentage_time=percentage_time,
        percentage_projects=percentage_projects,
        total_days=total_days,
        days_elapsed=days_elapsed,
        done_count=done_count,
        total_count=total_count,
        comments=comments,
        changes=changes,
        goals=goals,
        teams_involved=teams_involved,
        dris_involved=dris_involved,
        comment_count=comment_count,
        change_count=change_count
    )

# Route to close a sprint
@app.route('/sprint/<int:sprint_id>/close', methods=['POST'])
@login_required
@admin_required  # Only admins can close a sprint
def close_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    
    # Update sprint status to completed
    sprint.status = 'Completed'
    
    # Create a changelog entry
    sprintlog = SprintProjectMap.query.filter_by(sprint_id=sprint_id).first()
    
    if sprintlog:
        # Use the first project for the changelog
        changelog = Changelog(
            change_type='sprint_completion',
            content=f"Sprint '{sprint.title}' marked as completed by {current_user.username}",
            project_id=sprintlog.project_id,
            user_id=current_user.id,
            timestamp=datetime.utcnow()
        )
        db.session.add(changelog)
    
    db.session.commit()
    
    flash(f"Sprint '{sprint.title}' has been closed successfully.", 'success')
    return redirect(url_for('show_cycles'))

# Route to update commitment status
@app.route('/sprint/<int:sprint_id>/commitment/<int:commitment_id>/update', methods=['POST'])
@login_required
def update_commitment_status(sprint_id, commitment_id):
    commitment = SprintProjectMap.query.get_or_404(commitment_id)
    
    # Verify this commitment belongs to the specified sprint
    if commitment.sprint_id != sprint_id:
        flash('Invalid commitment for this sprint.', 'danger')
        return redirect(url_for('sprint_detail', sprint_id=sprint_id))
    
    # Get the new status and comment
    new_status = request.form.get('status')
    comment = request.form.get('comment', '')
    
    # Validate the status
    valid_statuses = ['Planned', 'In Progress', 'Done', 'Blocked', 'Cancelled']
    if new_status not in valid_statuses:
        flash('Invalid status value.', 'danger')
        return redirect(url_for('sprint_detail', sprint_id=sprint_id))
    
    # Update the commitment
    old_status = commitment.status
    commitment.status = new_status
    commitment.status_comment = comment
    commitment.status_updated = datetime.utcnow()
    commitment.status_updated_by = current_user.id
    
    # Create a changelog entry
    project = Project.query.get(commitment.project_id)
    changelog = Changelog(
        change_type='commitment_status_change',
        content=f"Commitment status for '{project.name}' changed from '{old_status}' to '{new_status}' with comment: {comment}",
        project_id=commitment.project_id,
        user_id=current_user.id,
        timestamp=datetime.utcnow()
    )
    db.session.add(changelog)
    
    db.session.commit()
    
    flash('Commitment status updated successfully!', 'success')
    return redirect(url_for('sprint_detail', sprint_id=sprint_id))

# ########################
# Closing a Cycle
# ########################
@app.route('/sprint/<int:sprint_id>/close-cycle', methods=['GET', 'POST'])
@login_required
@admin_required  # Only admins can close a sprint
def close_cycle(sprint_id):
    # Get the sprint
    sprint = Sprint.query.get_or_404(sprint_id)
    
    # Make sure it's not already completed
    if sprint.status == 'Completed':
        flash('This sprint is already marked as completed.', 'warning')
        return redirect(url_for('sprint_detail', sprint_id=sprint_id))
    
    # Get all sprint commitments
    sprint_commitments = SprintProjectMap.query.filter_by(sprint_id=sprint_id).all()
    
    # For POST handling
    if request.method == 'POST':
        # Process the form submission
        retrospective = sanitize_text(request.form.get('retrospective', ''))
        
        # Process email notification settings if applicable
        send_email = request.form.get('send_email') == 'on'
        email_addresses = request.form.get('email_addresses', '')
        
        # Update each commitment's status
        for commitment in sprint_commitments:
            commitment_id = str(commitment.id)
            status = request.form.get(f'status_{commitment_id}')
            comment = sanitize_text(request.form.get(f'comment_{commitment_id}', ''))
            
            # Only update if the status is valid
            if status in ['Completed', 'Not Completed', 'Blocked', 'Deferred', 'Cancelled']:
                old_status = commitment.status
                commitment.status = status
                commitment.status_comment = comment
                commitment.status_updated = datetime.utcnow()
                commitment.status_updated_by = current_user.id
                
                # Create changelog entry for the status change
                if old_status != status:
                    changelog = Changelog(
                        project_id=commitment.project_id,
                        user_id=current_user.id,
                        change_type='commitment_status_change',
                        content=f"Status changed from '{old_status}' to '{status}' with comment: {comment}"
                    )
                    db.session.add(changelog)
                
                # If marked as completed, check if the project should also be completed
                if status == 'Completed':
                    complete_project = request.form.get(f'complete_project_{commitment_id}') == 'yes'
                    project = Project.query.get(commitment.project_id)
                    
                    if complete_project and project:
                        old_project_status = project.status
                        old_project_location = project.location
                        
                        project.status = 'Completed'
                        project.location = 'completed'
                        
                        # Create changelog for project completion
                        project_changelog = Changelog(
                            project_id=project.id,
                            user_id=current_user.id,
                            change_type='project_completion',
                            content=f"Project marked as completed as part of sprint '{sprint.title}' closeout"
                        )
                        db.session.add(project_changelog)
                    elif project:
                        # Move the project back to discussion
                        old_project_location = project.location
                        project.location = 'discussion'
                        
                        # Create changelog for location change
                        if old_project_location != 'discussion':
                            project_changelog = Changelog(
                                project_id=project.id,
                                user_id=current_user.id,
                                change_type='location_change',
                                content=f"Project moved from '{old_project_location}' to 'discussion' after sprint completion"
                            )
                            db.session.add(project_changelog)
        
        # Update sprint status and save retrospective
        sprint.status = 'Completed'
        sprint.goals = retrospective  # Using the goals field to store retrospective
        
        # Create a changelog entry for sprint completion
        if sprint_commitments:
            # Use the first commitment's project for the changelog
            first_project_id = sprint_commitments[0].project_id
            sprint_changelog = Changelog(
                project_id=first_project_id,
                user_id=current_user.id,
                change_type='sprint_completion',
                content=f"Sprint '{sprint.title}' marked as completed with retrospective: {retrospective[:100]}{'...' if len(retrospective) > 100 else ''}"
            )
            db.session.add(sprint_changelog)
        
        db.session.commit()
        
        # Send email notification if enabled
        if send_email and email_addresses:
            send_sprint_closeout_notification(sprint_id, email_addresses.split(','))
        
        flash(f"Sprint '{sprint.title}' has been successfully closed.", 'success')
        return redirect(url_for('index'))
    
    # For GET request, prepare the template data
    # Calculate sprint metrics for display
    total_days = (sprint.date_end - sprint.date_start).days if sprint.date_start and sprint.date_end else 0
    today_date = datetime.now().date()
    days_elapsed = (today_date - sprint.date_start).days if sprint.date_start else 0
    percentage_time = min(100, max(0, (days_elapsed / total_days) * 100)) if total_days > 0 else 0
    
    # Count commitments by status
    status_counts = {}
    for status in ['Planned', 'In Progress', 'Done', 'Blocked', 'Cancelled']:
        status_counts[status] = sum(1 for c in sprint_commitments if c.status == status)
    
    # Get list of all completed sprints for comparison
    completed_sprints = Sprint.query.filter_by(status='Completed').all()
    
    # Calculate team involvement
    teams_involved = set()
    dris_involved = set()
    for commitment in sprint_commitments:
        project = Project.query.get(commitment.project_id)
        if project:
            teams_involved.add(project.team)
            dris_involved.add(project.dri)
    
    # Calculate sprint complexity based on comments and changes
    project_ids = [commitment.project_id for commitment in sprint_commitments]
    comment_count = 0
    change_count = 0
    if project_ids:
        # Get comments made during the sprint
        if sprint.date_start and sprint.date_end:
            comment_count = Comment.query.filter(
                Comment.project_id.in_(project_ids),
                Comment.created_at >= sprint.date_start,
                Comment.created_at <= sprint.date_end
            ).count()
            
            change_count = Changelog.query.filter(
                Changelog.project_id.in_(project_ids),
                Changelog.timestamp >= sprint.date_start,
                Changelog.timestamp <= sprint.date_end
            ).count()
    
    # Calculate complexity score (subjective formula, can be adjusted)
    complexity_score = (
        len(project_ids) * 0.4 + 
        comment_count * 0.3 + 
        change_count * 0.2 + 
        len(teams_involved) * 0.1
    )
    
    # Check if email configuration is available
    email_configured = (
        get_config('smtp_server') and 
        get_config('smtp_port') and 
        get_config('smtp_email') and 
        get_config('smtp_password') and 
        get_config('email_enabled') == 'true'
    )
    
    # Compare with other completed sprints
    avg_completion_rate = 0
    avg_duration = 0
    if completed_sprints:
        completion_rates = []
        durations = []
        for s in completed_sprints:
            s_commitments = SprintProjectMap.query.filter_by(sprint_id=s.id).all()
            done_count = sum(1 for c in s_commitments if c.status in ['Done', 'Completed'])
            if s_commitments:
                completion_rates.append(done_count / len(s_commitments) * 100)
            if s.date_start and s.date_end:
                durations.append((s.date_end - s.date_start).days)
        
        if completion_rates:
            avg_completion_rate = sum(completion_rates) / len(completion_rates)
        if durations:
            avg_duration = sum(durations) / len(durations)
    
    # Prepare data for the template
    return render_template(
        'close-cycle.html',
        sprint=sprint,
        commitments=sprint_commitments,
        total_days=total_days,
        days_elapsed=days_elapsed,
        percentage_time=percentage_time,
        status_counts=status_counts,
        teams_involved=teams_involved,
        dris_involved=dris_involved,
        complexity_score=complexity_score,
        completed_sprints=completed_sprints,
        avg_completion_rate=avg_completion_rate,
        avg_duration=avg_duration,
        email_configured=email_configured,
        comment_count=comment_count,
        change_count=change_count
    )

def send_sprint_closeout_notification(sprint_id, recipients):
    """Send an email notification about the closed sprint"""
    try:
        # Get sprint and related data
        sprint = Sprint.query.get_or_404(sprint_id)
        sprint_projects = SprintProjectMap.query.filter_by(sprint_id=sprint_id).all()
        
        # Calculate completion statistics
        total_commitments = len(sprint_projects)
        completed_commitments = sum(1 for c in sprint_projects if c.status in ['Done', 'Completed'])
        completion_percentage = (completed_commitments / total_commitments * 100) if total_commitments > 0 else 0
        
        # Get teams and DRIs involved
        teams = {}
        dris = {}
        for entry in sprint_projects:
            project = entry.project
            if project:
                # Count projects by team
                team = project.team
                teams[team] = teams.get(team, 0) + 1
                
                # Count projects by DRI
                dri = project.dri
                dris[dri] = dris.get(dri, 0) + 1
        
        # Create HTML email content using a template
        html_content = render_sprint_closeout_email_template(sprint, sprint_projects, {
            'teams': teams,
            'dris': dris,
            'completion_percentage': completion_percentage,
            'completed_commitments': completed_commitments,
            'total_commitments': total_commitments
        })
        
        # Send the email
        send_html_email(
            subject=f"Sprint Completed: {sprint.title}",
            recipients=recipients,
            html_content=html_content
        )
        
        return True
        
    except Exception as e:
        print(f"Error sending sprint closeout notification: {str(e)}")
        return False

def render_sprint_closeout_email_template(sprint, sprint_projects, analytics):
    """Render the HTML email template for sprint closeout notification"""
    return render_template(
        'emails/sprint_completed.html',
        sprint=sprint,
        sprint_projects=sprint_projects,
        analytics=analytics
    )