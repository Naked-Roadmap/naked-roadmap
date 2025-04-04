from app import app

import sqlite3
from flask import Flask, render_template, request, url_for, flash, redirect
from werkzeug.exceptions import abort
from app.models import User, Post, Project

# def get_db_connection():
#     conn = sqlite3.connect('database.db')
#     conn.row_factory = sqlite3.Row
#     return conn
# 
# def get_post(post_id):
#     conn = get_db_connection()
#     post = conn.execute('SELECT * FROM posts WHERE id = ?',
#                         (post_id,)).fetchone()
#     conn.close()
#     if post is None:
#         abort(404)
#     return post

@app.shell_context_processor
def make_shell_context():
    return {'sa': sa, 'so': so, 'db': db, 'User': User, 'Post': Post, 'Project':Project}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test123'




