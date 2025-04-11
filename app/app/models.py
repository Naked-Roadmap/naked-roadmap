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
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.TEXT())
    created: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    dri: so.Mapped[str] = so.mapped_column(sa.TEXT())
    team: so.Mapped[str] = so.mapped_column(sa.TEXT())
    context: so.Mapped[str] = so.mapped_column(sa.TEXT())
    why: so.Mapped[str] = so.mapped_column(sa.TEXT())
    requirements: so.Mapped[str] = so.mapped_column(sa.TEXT())
    launch: so.Mapped[str] = so.mapped_column(sa.TEXT())
    backlog: so.Mapped[bool] = so.mapped_column(unique=False, default=False, nullable=True)
    discussion: so.Mapped[bool] = so.mapped_column(unique=False, default=True, nullable=True)
    location: so.Mapped[str] = so.mapped_column(sa.TEXT(),  nullable=True, default="discussion")

    def __repr__(self):
        return '<Project {}>'.format(self.body)
        
class Request(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    created: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    title: so.Mapped[str] = so.mapped_column(sa.TEXT())
    requested_by: so.Mapped[str] = so.mapped_column(sa.TEXT())
    details: so.Mapped[str] = so.mapped_column(sa.TEXT())
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    
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

class SprintProjectMap(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    added: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    sprint_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Sprint.id), index=True)
    project_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Project.id), index=True)
    goal: so.Mapped[str] = so.mapped_column(sa.TEXT(), nullable=True)
    status: so.Mapped[str] = so.mapped_column(sa.TEXT(), default="Committed")
    
    def __repr__(self):
        return '<Sprint/Project Map {}>'.format(self.body)

# Notes:
# https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-iv-database