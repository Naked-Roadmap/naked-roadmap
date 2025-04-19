## Requirements
Index:
TODO: If no active cycle, then use last completed on dashboard

Projects Pages

Planning Pages:
TODO: Test further. Some workflows and path updates are not working. I.e., moving projects and locations back and forth, updating the date field on committment
TODO: Modify commitment status on a sprint page, index page
TODO: Fix links on the planning page discussion section
TODO: Fix links on the planning page commitments section
TODO: Send email when planning is complete
TODO: Sent sprint as active when planning is complete
TODO: Only one sprint active. The rest as upcoming or completed.
TODO: Group sprint projects by team (see details column)
TODO: Add cycle commitment outcomes per project alongside goals.
TODO: Send "Planned cycle email"
TODO: Send "Retro'd cycle email"
TODO: Add in "critical" toggle for sprint projects, and reason for critical
TODO: Collected & prioritized single stack roadmap section

Goals Page:
TODO: Goals order
TODO: Edit or delete comment on project only if you're the owner of the comment.
TODO: Add in an org configuration page outside of the app config.

Other:
TODO: Add Teams Page, create and list teams
TODO: Update project edit with team dropdown

## Analytics
TODO: Team Load (active projects)
TODO: Individual Load (active projects)
TODO: Project Completion Average (Days, Cycles)
TODO: Number of projects completed
TODO: Commitment Completion %
TODO: Number of cycles run
TODO: Number of goals achieved
TODO: Projects associated with a goal

## Nice to Have
TODO: Different types of users:
    - Viewer
    - Editer
TODO: Public vs. Private (anyone can see vs. need to be logged in to see)

## Marketing
TODO: Create community discourse as part of implementation of marketing site to allow modding, feature requests, support, etc.  https://github.com/discourse/discourse

## DONE
-- DONE: Create "Planning Page" (if no active sprint, run a planning session)
-- DONE: "Sprint" dropdown for homepage to select which one projects are being added to. Show only active and upcoming sprints.
-- DONE: Sprint goals route
-- DONE: Fix the edit button on modal
-- DONE: Add in all goals list
-- DONE: Fix text links in discussion section to work
-- DONE: Load goals into right dashboard section
-- DONE: % completed of sprint bar.
-- DONE: Add discussion per project
-- DONE: Add in changelog per project
-- DONE: Fix the star/critical functionality on planning page
-- DONE: Fix styles for create page. 
-- DONE: On Dashboard, show recent comments as well
-- DONE: On the project page, ability to attach a project to a goal.
-- DONE: Make sure objectives on the planning page show the number of projects supporting them.
-- DONE: Associate projects to goals.
-- DONE: Projects as tasks vs. projects

## Reminders:

- init env
- flask run
- flask db init
- flask db migrate -m "comment"
- flask db upgrade
- flask db stamp head for failed migrations

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