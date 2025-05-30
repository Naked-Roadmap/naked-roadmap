from app import app
import sqlite3
from flask import Flask, render_template, request, url_for, flash, redirect
from werkzeug.exceptions import abort
from app.models import User, Post, Project, Goal, Sprint, SprintProjectMap, Comment, Changelog

@app.shell_context_processor
def make_shell_context():
    return {'sa': sa, 'so': so, 'db': db, 'User': User, 'Post': Post, 'Project':Project, 'Goal':Goal, 'Sprint':Sprint, 'Comment':Comment, 'Changelog':Changelog}

app = Flask(__name__)
app.config.from_object(Config)
