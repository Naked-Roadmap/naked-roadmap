from datetime import datetime, timezone
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

class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    posts: so.WriteOnlyMapped['Post'] = so.relationship(back_populates='author')
    def __repr__(self):
        return '<User {}>'.format(self.username)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Post(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    created: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    content: so.Mapped[str] = so.mapped_column(sa.TEXT())
    title: so.Mapped[str] = so.mapped_column(sa.TEXT())
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    author: so.Mapped[User] = so.relationship(back_populates='posts')

    def __repr__(self):
        return '<Post {}>'.format(self.body)

class Project(db.Model):
    __tablename__ = "project"
    id = db.Column(db.Integer, primary_key=True, unique=True)
    name = db.Column(db.String(256))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    dri = db.Column(db.String(256))
    team = db.Column(db.String(256))
    context = db.Column(db.Text)
    why = db.Column(db.Text)
    requirements = db.Column(db.Text)
    launch = db.Column(db.Text)

    def __repr__(self):
        return (
            f"ID: {self.id} | "
            + f"Project Name: {self.name} | "
            + f"Created on (UTC): {self.created} | "
            + f"Directly Responsible Individual: {self.dri} | "
            + f"Team: {self.team} | "
            + f"Context: {self.context} | "
            + f"Reason for Prioritization: {self.why} | "
            + f"Requirements: {self.requirements} | "
            + f"Launch Plan: {self.launch}"
        )
        
# Notes:
# https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-iv-database