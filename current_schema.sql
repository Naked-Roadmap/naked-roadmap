CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
CREATE TABLE user (
	id INTEGER NOT NULL, 
	username VARCHAR(64) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(256), 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_user_email ON user (email);
CREATE UNIQUE INDEX ix_user_username ON user (username);
CREATE TABLE IF NOT EXISTS "sprint" (
	id INTEGER NOT NULL, 
	created DATETIME NOT NULL, 
	title TEXT NOT NULL, 
	date_start DATE NOT NULL, 
	date_end DATE NOT NULL, 
	goals TEXT, 
	status TEXT, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_sprint_date_start ON sprint (date_start);
CREATE INDEX ix_sprint_created ON sprint (created);
CREATE INDEX ix_sprint_date_end ON sprint (date_end);
CREATE TABLE sprint_project_map (
	id INTEGER NOT NULL, 
	added DATETIME NOT NULL, 
	sprint_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	goal TEXT, 
	status TEXT NOT NULL, "order" INTEGER, critical BOOLEAN, status_comment TEXT, status_updated DATETIME, status_updated_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES project (id), 
	FOREIGN KEY(sprint_id) REFERENCES sprint (id)
);
CREATE INDEX ix_sprint_project_map_added ON sprint_project_map (added);
CREATE INDEX ix_sprint_project_map_project_id ON sprint_project_map (project_id);
CREATE INDEX ix_sprint_project_map_sprint_id ON sprint_project_map (sprint_id);
CREATE TABLE goal (
	id INTEGER NOT NULL, 
	created DATETIME NOT NULL, 
	title TEXT NOT NULL, 
	requested_by TEXT NOT NULL, 
	details TEXT NOT NULL, 
	user_id INTEGER NOT NULL, status TEXT, completed DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id)
);
CREATE INDEX ix_goal_created ON goal (created);
CREATE INDEX ix_goal_user_id ON goal (user_id);
CREATE TABLE comments (
	id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	created_at DATETIME, 
	updated_at DATETIME, 
	project_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES project (id), 
	FOREIGN KEY(user_id) REFERENCES user (id)
);
CREATE TABLE changelogs (
	id INTEGER NOT NULL, 
	timestamp DATETIME, 
	change_type VARCHAR(50) NOT NULL, 
	content TEXT NOT NULL, 
	project_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES project (id), 
	FOREIGN KEY(user_id) REFERENCES user (id)
);
CREATE INDEX ix_changelogs_timestamp ON changelogs (timestamp);
CREATE TABLE app_config (
	id INTEGER NOT NULL, 
	"key" VARCHAR(100) NOT NULL, 
	value TEXT, 
	description TEXT, 
	created DATETIME NOT NULL, 
	updated DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_app_config_key ON app_config ("key");
CREATE TABLE role (
	id INTEGER NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
CREATE TABLE user_roles (
	user_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	PRIMARY KEY (user_id, role_id), 
	FOREIGN KEY(role_id) REFERENCES role (id), 
	FOREIGN KEY(user_id) REFERENCES user (id)
);
CREATE TABLE IF NOT EXISTS "project" (
	id INTEGER NOT NULL, 
	name TEXT NOT NULL, 
	created DATETIME NOT NULL, 
	dri TEXT NOT NULL, 
	team TEXT NOT NULL, 
	context TEXT NOT NULL, 
	why TEXT NOT NULL, 
	requirements TEXT NOT NULL, 
	launch TEXT NOT NULL, 
	location TEXT, 
	type TEXT, 
	status TEXT, 
	objective_id INTEGER, 
	user_id INTEGER, 
	is_public BOOLEAN, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_project_goal FOREIGN KEY(objective_id) REFERENCES goal (id), 
	CONSTRAINT fk_project_user_id FOREIGN KEY(user_id) REFERENCES user (id), 
	UNIQUE (id)
);
CREATE INDEX ix_project_created ON project (created);
CREATE INDEX ix_project_user_id ON project (user_id);
