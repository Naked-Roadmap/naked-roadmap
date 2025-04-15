## Requirements
TODO: Create "Planning Page" (if no active sprint, run a planning session)
TODO: Load goals into right dashboard section
TODO: "Sprint" dropdown for homepage to select which one projects are being added to. Show only active and upcoming sprints.
TODO: Only one sprint active. The rest as upcoming or completed.
TODO: Sort sprint projects
TODO: Add in "critical" toggle for sprint projects, and reason for critical
TODO: % completed of sprint bar.
TODO: Projects as tasks vs. projects
TODO: Collected & prioritized single stack roadmap section
TODO: Associate projects to goals.
TODO: Goals order
TODO: Add in changelog per project
TODO: Add discussion per project
TODO: Add in an org configuration page outside of the app config.

## Nice to Have
TODO: Different types of users:
    - Viewer
    - Editer
TODO: Public vs. Private (anyone can see vs. need to be logged in to see)

## Marketing
TODO: Create community disqus as part of implementation of marketing site to allow modding, feature requests, support, etc. 

## DONE
-- DONE: Sprint goals route
-- DONE: Fix the edit button on modal
-- DONE: Add in all goals list
-- DONE: Fix text links in discussion section to work

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