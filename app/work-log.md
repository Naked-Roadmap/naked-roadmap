##
TODO: Create initialization to run on first time setup to create a backlog sprint, undeletable.

## 2025.04.03
TODO: Different types of users:
    - Viewer
    - Editer
TODO: Public vs. Private (anyone can see vs. need to be logged in to see)

## Reminders:
- init env
- flask run
- flask db init
- flask db migrate -m "comment"
- flask db upgrade

(venv) $ flask shell
>>> db
<SQLAlchemy sqlite:////home/miguel/microblog/app.db>
>>> User
<class 'app.models.User'>
>>> Post
<class 'app.models.Post'>


source env/bin/activate

To freeze and install requirements:
$ pipreqs . 
$ pip install -r requirements.txt


Fixing migrations:
$ flask db stamp head
$ flask db migrate
$ flask db upgrade