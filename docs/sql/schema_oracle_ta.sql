-- Oracle DDL generated from SQLAlchemy models.
-- Table names follow TB_TA_PM_* with no schema qualifier.

-- Table: TB_TA_PM_PHASES

CREATE TABLE "TB_TA_PM_PHASES" (
	phase_id VARCHAR2(255 CHAR) NOT NULL,
	phase_group VARCHAR2(255 CHAR) NOT NULL,
	phase_name VARCHAR2(255 CHAR) NOT NULL,
	sequence INTEGER NOT NULL,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	PRIMARY KEY (phase_id)
);

-- Table: TB_TA_PM_SPACES

CREATE TABLE "TB_TA_PM_SPACES" (
	space_id VARCHAR2(255 CHAR) NOT NULL,
	name VARCHAR2(255 CHAR) NOT NULL,
	slug VARCHAR2(255 CHAR) NOT NULL,
	is_active SMALLINT NOT NULL,
	public_program_dashboard_enabled SMALLINT NOT NULL,
	archived_at DATE,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (space_id),
	CONSTRAINT uix_space_slug UNIQUE (slug),
	CONSTRAINT uix_space_name UNIQUE (name)
);

-- Table: TB_TA_PM_USERS

CREATE TABLE "TB_TA_PM_USERS" (
	user_id VARCHAR2(255 CHAR) NOT NULL,
	soeid VARCHAR2(255 CHAR) NOT NULL,
	email VARCHAR2(255 CHAR) NOT NULL,
	display_name VARCHAR2(255 CHAR) NOT NULL,
	password_hash VARCHAR2(255 CHAR) NOT NULL,
	role VARCHAR2(255 CHAR) NOT NULL,
	is_active SMALLINT NOT NULL,
	is_service_account SMALLINT NOT NULL,
	team_tag VARCHAR2(255 CHAR),
	capacity_hours INTEGER NOT NULL,
	capacity_fte_month FLOAT NOT NULL,
	failed_attempts INTEGER NOT NULL,
	locked_until DATE,
	last_login_at DATE,
	external_id VARCHAR2(255 CHAR),
	temp_password_hash VARCHAR2(255 CHAR),
	temp_password_expires_at DATE,
	force_password_reset SMALLINT NOT NULL,
	password_changed_at DATE,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	PRIMARY KEY (user_id),
	CONSTRAINT uix_user_email UNIQUE (email),
	CONSTRAINT uix_user_soeid UNIQUE (soeid)
);

-- Table: TB_TA_PM_API_TOKENS

CREATE TABLE "TB_TA_PM_API_TOKENS" (
	token_id VARCHAR2(255 CHAR) NOT NULL,
	user_id VARCHAR2(255 CHAR) NOT NULL,
	name VARCHAR2(255 CHAR) NOT NULL,
	token_hash VARCHAR2(64 CHAR) NOT NULL,
	created_by_user_id VARCHAR2(255 CHAR) NOT NULL,
	last_used_at DATE,
	expires_at DATE,
	revoked_at DATE,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	PRIMARY KEY (token_id),
	CONSTRAINT uix_api_token_hash UNIQUE (token_hash),
	FOREIGN KEY(user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Index: idx_api_token_user
CREATE INDEX idx_api_token_user ON "TB_TA_PM_API_TOKENS" (user_id);

-- Index: ix_TB_TA_PM_API_TOKENS_revoked_at
CREATE INDEX "ix_TB_TA_PM_API_TOKENS_revoked_at" ON "TB_TA_PM_API_TOKENS" (revoked_at);

-- Table: TB_TA_PM_CHANGE_LOG

-- Audit values must remain CLOB because project/solution descriptions and
-- success criteria can exceed VARCHAR2 limits.
CREATE TABLE "TB_TA_PM_CHANGE_LOG" (
	change_id VARCHAR2(255 CHAR) NOT NULL,
	entity_type VARCHAR2(255 CHAR) NOT NULL,
	entity_id VARCHAR2(255 CHAR) NOT NULL,
	action VARCHAR2(255 CHAR) NOT NULL,
	field VARCHAR2(255 CHAR),
	old_value CLOB,
	new_value CLOB,
	user_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	request_id VARCHAR2(255 CHAR),
	created_at DATE NOT NULL,
	PRIMARY KEY (change_id),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_AGENT_CHANGE_REQUESTS

CREATE TABLE "TB_TA_PM_AGENT_CHANGE_REQUESTS" (
	change_request_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR) NOT NULL,
	proposed_by_user_id VARCHAR2(255 CHAR) NOT NULL,
	status VARCHAR2(255 CHAR) NOT NULL,
	reason VARCHAR2(255 CHAR) NOT NULL,
	idempotency_key VARCHAR2(255 CHAR) NOT NULL,
	operations_json CLOB NOT NULL,
	validation_json CLOB NOT NULL,
	diff_json CLOB NOT NULL,
	reviewed_by_user_id VARCHAR2(255 CHAR),
	reviewed_at DATE,
	review_note CLOB,
	applied_at DATE,
	failed_reason CLOB,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	PRIMARY KEY (change_request_id),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
	FOREIGN KEY(proposed_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id),
	FOREIGN KEY(reviewed_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Index: idx_agent_cr_space_status
CREATE INDEX idx_agent_cr_space_status ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (space_id, status, created_at);

-- Index: idx_agent_cr_proposer
CREATE INDEX idx_agent_cr_proposer ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (proposed_by_user_id, created_at);

-- Index: ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_space_id
CREATE INDEX "ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_space_id" ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (space_id);

-- Index: ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_proposed_by_user_id
CREATE INDEX "ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_proposed_by_user_id" ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (proposed_by_user_id);

-- Index: ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_reviewed_by_user_id
CREATE INDEX "ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_reviewed_by_user_id" ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (reviewed_by_user_id);

-- Table: TB_TA_PM_USAGE_EVENTS

CREATE TABLE "TB_TA_PM_USAGE_EVENTS" (
	event_id VARCHAR2(255 CHAR) NOT NULL,
	occurred_at DATE NOT NULL,
	received_at DATE NOT NULL,
	session_id VARCHAR2(255 CHAR) NOT NULL,
	user_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	view_key VARCHAR2(255 CHAR) NOT NULL,
	category VARCHAR2(255 CHAR) NOT NULL,
	feature_key VARCHAR2(255 CHAR) NOT NULL,
	action_key VARCHAR2(255 CHAR) NOT NULL,
	outcome VARCHAR2(255 CHAR) NOT NULL,
	duration_ms INTEGER,
	status_code INTEGER,
	details_json CLOB,
	PRIMARY KEY (event_id),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_PERFORMANCE_SAMPLES

CREATE TABLE "TB_TA_PM_PERFORMANCE_SAMPLES" (
	sample_id VARCHAR2(255 CHAR) NOT NULL,
	occurred_at DATE NOT NULL,
	received_at DATE NOT NULL,
	session_id VARCHAR2(255 CHAR) NOT NULL,
	user_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	view_key VARCHAR2(255 CHAR) NOT NULL,
	sample_kind VARCHAR2(255 CHAR) NOT NULL,
	navigation_type VARCHAR2(255 CHAR),
	data_load_ms INTEGER,
	render_ms INTEGER,
	ttfb_ms INTEGER,
	dom_interactive_ms INTEGER,
	dom_content_loaded_ms INTEGER,
	load_event_ms INTEGER,
	first_paint_ms INTEGER,
	first_contentful_paint_ms INTEGER,
	largest_contentful_paint_ms INTEGER,
	cls_score FLOAT,
	long_task_count INTEGER,
	long_task_total_ms INTEGER,
	PRIMARY KEY (sample_id),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_USAGE_DAILY_ROLLUPS

CREATE TABLE "TB_TA_PM_USAGE_DAILY_ROLLUPS" (
	rollup_date DATE NOT NULL,
	space_id VARCHAR2(255 CHAR) NOT NULL,
	view_key VARCHAR2(255 CHAR) NOT NULL,
	category VARCHAR2(255 CHAR) NOT NULL,
	feature_key VARCHAR2(255 CHAR) NOT NULL,
	action_key VARCHAR2(255 CHAR) NOT NULL,
	outcome VARCHAR2(255 CHAR) NOT NULL,
	event_count NUMBER(19) NOT NULL,
	route_view_count NUMBER(19) NOT NULL,
	workflow_action_count NUMBER(19) NOT NULL,
	success_count NUMBER(19) NOT NULL,
	failure_count NUMBER(19) NOT NULL,
	last_occurred_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	PRIMARY KEY (rollup_date, space_id, view_key, category, feature_key, action_key, outcome)
);

-- Table: TB_TA_PM_USAGE_IDENTITY_DAILY_ROLLUPS

CREATE TABLE "TB_TA_PM_USAGE_IDENTITY_DAILY_ROLLUPS" (
	rollup_date DATE NOT NULL,
	space_id VARCHAR2(255 CHAR) NOT NULL,
	token_type VARCHAR2(255 CHAR) NOT NULL,
	token_value VARCHAR2(255 CHAR) NOT NULL,
	updated_at DATE NOT NULL,
	PRIMARY KEY (rollup_date, space_id, token_type, token_value)
);

-- Table: TB_TA_PM_USAGE_ROUTE_IDENTITY_DAILY_ROLLUPS

CREATE TABLE "TB_TA_PM_USAGE_ROUTE_IDENTITY_DAILY_ROLLUPS" (
	rollup_date DATE NOT NULL,
	space_id VARCHAR2(255 CHAR) NOT NULL,
	view_key VARCHAR2(255 CHAR) NOT NULL,
	token_type VARCHAR2(255 CHAR) NOT NULL,
	token_value VARCHAR2(255 CHAR) NOT NULL,
	updated_at DATE NOT NULL,
	PRIMARY KEY (rollup_date, space_id, view_key, token_type, token_value)
);

-- Table: TB_TA_PM_PLANNING_WINDOWS

CREATE TABLE "TB_TA_PM_PLANNING_WINDOWS" (
	window_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	name VARCHAR2(255 CHAR) NOT NULL,
	start_date DATE NOT NULL,
	end_date DATE NOT NULL,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (window_id),
	CONSTRAINT uix_planning_window_name UNIQUE (name),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_PROGRAMS

CREATE TABLE "TB_TA_PM_PROGRAMS" (
	program_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	program_name VARCHAR2(255 CHAR) NOT NULL,
	description CLOB,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (program_id),
	CONSTRAINT uix_program_space_name UNIQUE (space_id, program_name),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_PROJECTS

CREATE TABLE "TB_TA_PM_PROJECTS" (
	project_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	program_id VARCHAR2(255 CHAR) NOT NULL,
	project_name VARCHAR2(255 CHAR) NOT NULL,
	status VARCHAR(11 CHAR) NOT NULL,
	description CLOB,
	success_criteria CLOB,
	sponsor VARCHAR2(255 CHAR) NOT NULL,
	sponsor_user_soeid VARCHAR2(255 CHAR),
	strategic_objective CLOB,
	priority INTEGER NOT NULL,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (project_id),
	CONSTRAINT uix_project_space_name UNIQUE (space_id, project_name),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
	FOREIGN KEY(program_id) REFERENCES "TB_TA_PM_PROGRAMS" (program_id)
);

-- Table: TB_TA_PM_SPACE_MEMBERSHIPS

CREATE TABLE "TB_TA_PM_SPACE_MEMBERSHIPS" (
	membership_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR) NOT NULL,
	user_id VARCHAR2(255 CHAR) NOT NULL,
	role VARCHAR2(255 CHAR) NOT NULL,
	status VARCHAR2(255 CHAR) NOT NULL,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (membership_id),
	CONSTRAINT uix_space_membership UNIQUE (space_id, user_id),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
	FOREIGN KEY(user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_TEAMS

CREATE TABLE "TB_TA_PM_TEAMS" (
	team_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	name VARCHAR2(255 CHAR) NOT NULL,
	description VARCHAR2(255 CHAR),
	lead VARCHAR2(255 CHAR),
	default_capacity_per_week INTEGER NOT NULL,
	default_capacity_fte_month FLOAT NOT NULL,
	capacity_unit VARCHAR2(255 CHAR) NOT NULL,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (team_id),
	CONSTRAINT uix_team_space_name UNIQUE (space_id, name),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_RESOURCE_ALLOCATIONS

CREATE TABLE "TB_TA_PM_RESOURCE_ALLOCATIONS" (
	allocation_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	work_item_type VARCHAR2(255 CHAR) NOT NULL,
	work_item_id VARCHAR2(255 CHAR) NOT NULL,
	assignee_user_soeid VARCHAR2(255 CHAR),
	assignee VARCHAR2(255 CHAR),
	team_id VARCHAR2(255 CHAR),
	week_start DATE NOT NULL,
	month_start DATE,
	hours INTEGER NOT NULL,
	fte_months FLOAT NOT NULL,
	window_id VARCHAR2(255 CHAR),
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (allocation_id),
	CONSTRAINT uix_alloc_unique_assignment UNIQUE (work_item_type, work_item_id, assignee_user_soeid, week_start, window_id),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
	FOREIGN KEY(team_id) REFERENCES "TB_TA_PM_TEAMS" (team_id),
	FOREIGN KEY(window_id) REFERENCES "TB_TA_PM_PLANNING_WINDOWS" (window_id)
);

-- Table: TB_TA_PM_SOLUTIONS

CREATE TABLE "TB_TA_PM_SOLUTIONS" (
	solution_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	project_id VARCHAR2(255 CHAR) NOT NULL,
	solution_name VARCHAR2(255 CHAR) NOT NULL,
	version VARCHAR2(255 CHAR) NOT NULL,
	status VARCHAR(11 CHAR) NOT NULL,
	rag_status VARCHAR(5 CHAR) NOT NULL,
	rag_reason CLOB,
	priority INTEGER NOT NULL,
	due_date DATE,
	current_phase VARCHAR2(255 CHAR),
	description CLOB,
	success_criteria CLOB,
	problem_statement CLOB,
	github_repo_url VARCHAR2(1024 CHAR),
	escalation VARCHAR2(255 CHAR),
	owner VARCHAR2(255 CHAR) NOT NULL,
	owner_user_soeid VARCHAR2(255 CHAR),
	assignee VARCHAR2(255 CHAR) NOT NULL,
	assignee_user_soeid VARCHAR2(255 CHAR),
	approver VARCHAR2(255 CHAR),
	approver_user_soeid VARCHAR2(255 CHAR),
	key_stakeholder VARCHAR2(255 CHAR),
	blockers CLOB,
	risks CLOB,
	impact_confidence VARCHAR(6 CHAR),
	planned_start_date DATE,
	rag_confidence FLOAT,
	completed_at DATE,
	capacity_hours INTEGER NOT NULL,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (solution_id),
	CONSTRAINT uix_solution_project_name_version UNIQUE (project_id, solution_name, version),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id)
);

-- Table: TB_TA_PM_SOLUTION_DOCUMENTS

CREATE TABLE "TB_TA_PM_SOLUTION_DOCUMENTS" (
	document_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	solution_id VARCHAR2(255 CHAR) NOT NULL,
	filename VARCHAR2(1024 CHAR) NOT NULL,
	content_type VARCHAR2(255 CHAR),
	size_bytes INTEGER NOT NULL,
	content BLOB NOT NULL,
	uploaded_by_user_id VARCHAR2(255 CHAR) NOT NULL,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (document_id),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id)
);

-- Table: TB_TA_PM_TEAM_MEMBERS

CREATE TABLE "TB_TA_PM_TEAM_MEMBERS" (
	team_member_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	team_id VARCHAR2(255 CHAR) NOT NULL,
	member_name VARCHAR2(255 CHAR) NOT NULL,
	role VARCHAR2(255 CHAR) NOT NULL,
	capacity_override INTEGER,
	capacity_unit VARCHAR2(255 CHAR),
	hours_capacity INTEGER,
	capacity_fte_month FLOAT,
	points_capacity INTEGER,
	percent_capacity FLOAT,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (team_member_id),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
	FOREIGN KEY(team_id) REFERENCES "TB_TA_PM_TEAMS" (team_id)
);

-- Table: TB_TA_PM_SOLUTION_PHASES

CREATE TABLE "TB_TA_PM_SOLUTION_PHASES" (
	solution_phase_id VARCHAR2(255 CHAR) NOT NULL,
	solution_id VARCHAR2(255 CHAR) NOT NULL,
	phase_id VARCHAR2(255 CHAR) NOT NULL,
	is_enabled SMALLINT NOT NULL,
	sequence_override INTEGER,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	PRIMARY KEY (solution_phase_id),
	CONSTRAINT uix_solution_phase UNIQUE (solution_id, phase_id),
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id),
	FOREIGN KEY(phase_id) REFERENCES "TB_TA_PM_PHASES" (phase_id)
);

-- Table: TB_TA_PM_TASKS

CREATE TABLE "TB_TA_PM_TASKS" (
	task_id VARCHAR2(255 CHAR) NOT NULL,
	space_id VARCHAR2(255 CHAR),
	project_id VARCHAR2(255 CHAR) NOT NULL,
	solution_id VARCHAR2(255 CHAR) NOT NULL,
	task_name VARCHAR2(255 CHAR) NOT NULL,
	status VARCHAR(11 CHAR) NOT NULL,
	priority INTEGER NOT NULL,
	due_date DATE,
	completed_at DATE,
	assignee_user_soeid VARCHAR2(255 CHAR),
	assignee VARCHAR2(255 CHAR) NOT NULL,
	github_repo_url VARCHAR2(1024 CHAR),
	estimate_hours INTEGER,
	blocked SMALLINT NOT NULL,
	blocker_note CLOB,
	done_criteria CLOB,
	capacity_hours INTEGER NOT NULL,
	created_at DATE NOT NULL,
	updated_at DATE NOT NULL,
	deleted_at DATE,
	PRIMARY KEY (task_id),
	CONSTRAINT uix_task_solution_name UNIQUE (solution_id, task_name),
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id),
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id)
);

-- Index: idx_alloc_item
CREATE INDEX idx_alloc_item ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (work_item_type, work_item_id);

-- Index: idx_alloc_month_assignee
CREATE INDEX idx_alloc_month_assignee ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (month_start, assignee_user_soeid);

-- Index: idx_alloc_week_assignee
CREATE INDEX idx_alloc_week_assignee ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (week_start, assignee_user_soeid);

-- Index: idx_change_entity_created
CREATE INDEX idx_change_entity_created ON "TB_TA_PM_CHANGE_LOG" (entity_type, entity_id, created_at);

-- Index: idx_change_user_created
CREATE INDEX idx_change_user_created ON "TB_TA_PM_CHANGE_LOG" (user_id, created_at);

-- Index: idx_performance_samples_created
CREATE INDEX idx_performance_samples_created ON "TB_TA_PM_PERFORMANCE_SAMPLES" (occurred_at);

-- Index: idx_performance_samples_kind_created
CREATE INDEX idx_performance_samples_kind_created ON "TB_TA_PM_PERFORMANCE_SAMPLES" (sample_kind, occurred_at);

-- Index: idx_performance_samples_session_created
CREATE INDEX idx_performance_samples_session_created ON "TB_TA_PM_PERFORMANCE_SAMPLES" (session_id, occurred_at);

-- Index: idx_performance_samples_space_created
CREATE INDEX idx_performance_samples_space_created ON "TB_TA_PM_PERFORMANCE_SAMPLES" (space_id, occurred_at);

-- Index: idx_performance_samples_user_created
CREATE INDEX idx_performance_samples_user_created ON "TB_TA_PM_PERFORMANCE_SAMPLES" (user_id, occurred_at);

-- Index: idx_performance_samples_view_created
CREATE INDEX idx_performance_samples_view_created ON "TB_TA_PM_PERFORMANCE_SAMPLES" (view_key, occurred_at);

-- Index: idx_usage_events_created
CREATE INDEX idx_usage_events_created ON "TB_TA_PM_USAGE_EVENTS" (occurred_at);

-- Index: idx_usage_events_feature_action_created
CREATE INDEX idx_usage_events_feature_action_created ON "TB_TA_PM_USAGE_EVENTS" (feature_key, action_key, occurred_at);

-- Index: idx_usage_events_session_created
CREATE INDEX idx_usage_events_session_created ON "TB_TA_PM_USAGE_EVENTS" (session_id, occurred_at);

-- Index: idx_usage_events_space_created
CREATE INDEX idx_usage_events_space_created ON "TB_TA_PM_USAGE_EVENTS" (space_id, occurred_at);

-- Index: idx_usage_events_user_created
CREATE INDEX idx_usage_events_user_created ON "TB_TA_PM_USAGE_EVENTS" (user_id, occurred_at);

-- Index: idx_usage_events_view_created
CREATE INDEX idx_usage_events_view_created ON "TB_TA_PM_USAGE_EVENTS" (view_key, occurred_at);

-- Index: idx_usage_identity_rollups_date
CREATE INDEX idx_usage_identity_rollups_date ON "TB_TA_PM_USAGE_IDENTITY_DAILY_ROLLUPS" (rollup_date, token_type);

-- Index: idx_usage_identity_rollups_scope
CREATE INDEX idx_usage_identity_rollups_scope ON "TB_TA_PM_USAGE_IDENTITY_DAILY_ROLLUPS" (space_id, rollup_date, token_type);

-- Index: idx_usage_rollups_date_failure
CREATE INDEX idx_usage_rollups_date_failure ON "TB_TA_PM_USAGE_DAILY_ROLLUPS" (rollup_date, outcome, view_key, feature_key, action_key);

-- Index: idx_usage_rollups_date_view
CREATE INDEX idx_usage_rollups_date_view ON "TB_TA_PM_USAGE_DAILY_ROLLUPS" (rollup_date, view_key);

-- Index: idx_usage_rollups_date_workflow
CREATE INDEX idx_usage_rollups_date_workflow ON "TB_TA_PM_USAGE_DAILY_ROLLUPS" (rollup_date, category, feature_key, action_key);

-- Index: idx_usage_rollups_space_date
CREATE INDEX idx_usage_rollups_space_date ON "TB_TA_PM_USAGE_DAILY_ROLLUPS" (space_id, rollup_date);

-- Index: idx_usage_route_identity_date
CREATE INDEX idx_usage_route_identity_date ON "TB_TA_PM_USAGE_ROUTE_IDENTITY_DAILY_ROLLUPS" (rollup_date, view_key, token_type);

-- Index: idx_usage_route_identity_scope
CREATE INDEX idx_usage_route_identity_scope ON "TB_TA_PM_USAGE_ROUTE_IDENTITY_DAILY_ROLLUPS" (space_id, rollup_date, view_key, token_type);

-- Index: ix_TB_TA_PM_CHANGE_LOG_created_at
CREATE INDEX "ix_TB_TA_PM_CHANGE_LOG_created_at" ON "TB_TA_PM_CHANGE_LOG" (created_at);

-- Index: ix_TB_TA_PM_CHANGE_LOG_request_id
CREATE INDEX "ix_TB_TA_PM_CHANGE_LOG_request_id" ON "TB_TA_PM_CHANGE_LOG" (request_id);

-- Index: ix_TB_TA_PM_CHANGE_LOG_space_id
CREATE INDEX "ix_TB_TA_PM_CHANGE_LOG_space_id" ON "TB_TA_PM_CHANGE_LOG" (space_id);

-- Index: ix_TB_TA_PM_CHANGE_LOG_user_id
CREATE INDEX "ix_TB_TA_PM_CHANGE_LOG_user_id" ON "TB_TA_PM_CHANGE_LOG" (user_id);

-- Index: ix_TB_TA_PM_PHASES_sequence
CREATE INDEX "ix_TB_TA_PM_PHASES_sequence" ON "TB_TA_PM_PHASES" (sequence);

-- Index: ix_TB_TA_PM_PLANNING_WINDOWS_deleted_at
CREATE INDEX "ix_TB_TA_PM_PLANNING_WINDOWS_deleted_at" ON "TB_TA_PM_PLANNING_WINDOWS" (deleted_at);

-- Index: ix_TB_TA_PM_PLANNING_WINDOWS_space_id
CREATE INDEX "ix_TB_TA_PM_PLANNING_WINDOWS_space_id" ON "TB_TA_PM_PLANNING_WINDOWS" (space_id);

-- Index: ix_TB_TA_PM_PROGRAMS_deleted_at
CREATE INDEX "ix_TB_TA_PM_PROGRAMS_deleted_at" ON "TB_TA_PM_PROGRAMS" (deleted_at);

-- Index: ix_TB_TA_PM_PROGRAMS_space_id
CREATE INDEX "ix_TB_TA_PM_PROGRAMS_space_id" ON "TB_TA_PM_PROGRAMS" (space_id);

-- Index: ix_TB_TA_PM_PROJECTS_deleted_at
CREATE INDEX "ix_TB_TA_PM_PROJECTS_deleted_at" ON "TB_TA_PM_PROJECTS" (deleted_at);

-- Index: ix_TB_TA_PM_PROJECTS_program_id
CREATE INDEX "ix_TB_TA_PM_PROJECTS_program_id" ON "TB_TA_PM_PROJECTS" (program_id);

-- Index: ix_TB_TA_PM_PROJECTS_space_id
CREATE INDEX "ix_TB_TA_PM_PROJECTS_space_id" ON "TB_TA_PM_PROJECTS" (space_id);

-- Index: ix_TB_TA_PM_PROJECTS_sponsor_user_soeid
CREATE INDEX "ix_TB_TA_PM_PROJECTS_sponsor_user_soeid" ON "TB_TA_PM_PROJECTS" (sponsor_user_soeid);

-- Index: ix_TB_TA_PM_PROJECTS_status
CREATE INDEX "ix_TB_TA_PM_PROJECTS_status" ON "TB_TA_PM_PROJECTS" (status);

-- Index: ix_TB_TA_PM_RESOURCE_ALLOCATIONS_assignee_user_soeid
CREATE INDEX "ix_TB_TA_PM_RESOURCE_ALLOCATIONS_assignee_user_soeid" ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (assignee_user_soeid);

-- Index: ix_TB_TA_PM_RESOURCE_ALLOCATIONS_deleted_at
CREATE INDEX "ix_TB_TA_PM_RESOURCE_ALLOCATIONS_deleted_at" ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (deleted_at);

-- Index: ix_TB_TA_PM_RESOURCE_ALLOCATIONS_month_start
CREATE INDEX "ix_TB_TA_PM_RESOURCE_ALLOCATIONS_month_start" ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (month_start);

-- Index: ix_TB_TA_PM_RESOURCE_ALLOCATIONS_space_id
CREATE INDEX "ix_TB_TA_PM_RESOURCE_ALLOCATIONS_space_id" ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (space_id);

-- Index: ix_TB_TA_PM_RESOURCE_ALLOCATIONS_team_id
CREATE INDEX "ix_TB_TA_PM_RESOURCE_ALLOCATIONS_team_id" ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (team_id);

-- Index: ix_TB_TA_PM_RESOURCE_ALLOCATIONS_week_start
CREATE INDEX "ix_TB_TA_PM_RESOURCE_ALLOCATIONS_week_start" ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (week_start);

-- Index: ix_TB_TA_PM_RESOURCE_ALLOCATIONS_window_id
CREATE INDEX "ix_TB_TA_PM_RESOURCE_ALLOCATIONS_window_id" ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (window_id);

-- Index: ix_TB_TA_PM_SOLUTIONS_approver_user_soeid
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_approver_user_soeid" ON "TB_TA_PM_SOLUTIONS" (approver_user_soeid);

-- Index: ix_TB_TA_PM_SOLUTIONS_assignee
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_assignee" ON "TB_TA_PM_SOLUTIONS" (assignee);

-- Index: ix_TB_TA_PM_SOLUTIONS_assignee_user_soeid
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_assignee_user_soeid" ON "TB_TA_PM_SOLUTIONS" (assignee_user_soeid);

-- Index: ix_TB_TA_PM_SOLUTIONS_current_phase
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_current_phase" ON "TB_TA_PM_SOLUTIONS" (current_phase);

-- Index: ix_TB_TA_PM_SOLUTIONS_deleted_at
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_deleted_at" ON "TB_TA_PM_SOLUTIONS" (deleted_at);

-- Index: ix_TB_TA_PM_SOLUTIONS_due_date
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_due_date" ON "TB_TA_PM_SOLUTIONS" (due_date);

-- Index: ix_TB_TA_PM_SOLUTIONS_owner_user_soeid
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_owner_user_soeid" ON "TB_TA_PM_SOLUTIONS" (owner_user_soeid);

-- Index: ix_TB_TA_PM_SOLUTIONS_priority
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_priority" ON "TB_TA_PM_SOLUTIONS" (priority);

-- Index: ix_TB_TA_PM_SOLUTIONS_project_id
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_project_id" ON "TB_TA_PM_SOLUTIONS" (project_id);

-- Index: ix_TB_TA_PM_SOLUTIONS_rag_status
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_rag_status" ON "TB_TA_PM_SOLUTIONS" (rag_status);

-- Index: ix_TB_TA_PM_SOLUTIONS_space_id
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_space_id" ON "TB_TA_PM_SOLUTIONS" (space_id);

-- Index: ix_TB_TA_PM_SOLUTIONS_status
CREATE INDEX "ix_TB_TA_PM_SOLUTIONS_status" ON "TB_TA_PM_SOLUTIONS" (status);

-- Index: ix_TB_TA_PM_SOLUTION_DOCUMENTS_deleted_at
CREATE INDEX "ix_TB_TA_PM_SOLUTION_DOCUMENTS_deleted_at" ON "TB_TA_PM_SOLUTION_DOCUMENTS" (deleted_at);

-- Index: ix_TB_TA_PM_SOLUTION_DOCUMENTS_solution_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_DOCUMENTS_solution_id" ON "TB_TA_PM_SOLUTION_DOCUMENTS" (solution_id);

-- Index: ix_TB_TA_PM_SOLUTION_DOCUMENTS_space_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_DOCUMENTS_space_id" ON "TB_TA_PM_SOLUTION_DOCUMENTS" (space_id);

-- Index: ix_TB_TA_PM_SOLUTION_DOCUMENTS_uploaded_by_user_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_DOCUMENTS_uploaded_by_user_id" ON "TB_TA_PM_SOLUTION_DOCUMENTS" (uploaded_by_user_id);

-- Index: ix_TB_TA_PM_SOLUTION_PHASES_sequence_override
CREATE INDEX "ix_TB_TA_PM_SOLUTION_PHASES_sequence_override" ON "TB_TA_PM_SOLUTION_PHASES" (sequence_override);

-- Index: ix_TB_TA_PM_SOLUTION_PHASES_solution_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_PHASES_solution_id" ON "TB_TA_PM_SOLUTION_PHASES" (solution_id);

-- Index: ix_TB_TA_PM_SPACES_archived_at
CREATE INDEX "ix_TB_TA_PM_SPACES_archived_at" ON "TB_TA_PM_SPACES" (archived_at);

-- Index: ix_TB_TA_PM_SPACES_deleted_at
CREATE INDEX "ix_TB_TA_PM_SPACES_deleted_at" ON "TB_TA_PM_SPACES" (deleted_at);

-- Index: ix_TB_TA_PM_SPACES_is_active
CREATE INDEX "ix_TB_TA_PM_SPACES_is_active" ON "TB_TA_PM_SPACES" (is_active);

-- Index: ix_TB_TA_PM_SPACE_MEMBERSHIPS_deleted_at
CREATE INDEX "ix_TB_TA_PM_SPACE_MEMBERSHIPS_deleted_at" ON "TB_TA_PM_SPACE_MEMBERSHIPS" (deleted_at);

-- Index: ix_TB_TA_PM_SPACE_MEMBERSHIPS_role
CREATE INDEX "ix_TB_TA_PM_SPACE_MEMBERSHIPS_role" ON "TB_TA_PM_SPACE_MEMBERSHIPS" (role);

-- Index: ix_TB_TA_PM_SPACE_MEMBERSHIPS_space_id
CREATE INDEX "ix_TB_TA_PM_SPACE_MEMBERSHIPS_space_id" ON "TB_TA_PM_SPACE_MEMBERSHIPS" (space_id);

-- Index: ix_TB_TA_PM_SPACE_MEMBERSHIPS_status
CREATE INDEX "ix_TB_TA_PM_SPACE_MEMBERSHIPS_status" ON "TB_TA_PM_SPACE_MEMBERSHIPS" (status);

-- Index: ix_TB_TA_PM_SPACE_MEMBERSHIPS_user_id
CREATE INDEX "ix_TB_TA_PM_SPACE_MEMBERSHIPS_user_id" ON "TB_TA_PM_SPACE_MEMBERSHIPS" (user_id);

-- Index: ix_TB_TA_PM_TASKS_assignee_user_soeid
CREATE INDEX "ix_TB_TA_PM_TASKS_assignee_user_soeid" ON "TB_TA_PM_TASKS" (assignee_user_soeid);

-- Index: ix_TB_TA_PM_TASKS_blocked
CREATE INDEX "ix_TB_TA_PM_TASKS_blocked" ON "TB_TA_PM_TASKS" (blocked);

-- Index: ix_TB_TA_PM_TASKS_deleted_at
CREATE INDEX "ix_TB_TA_PM_TASKS_deleted_at" ON "TB_TA_PM_TASKS" (deleted_at);

-- Index: ix_TB_TA_PM_TASKS_due_date
CREATE INDEX "ix_TB_TA_PM_TASKS_due_date" ON "TB_TA_PM_TASKS" (due_date);

-- Index: ix_TB_TA_PM_TASKS_priority
CREATE INDEX "ix_TB_TA_PM_TASKS_priority" ON "TB_TA_PM_TASKS" (priority);

-- Index: ix_TB_TA_PM_TASKS_project_id
CREATE INDEX "ix_TB_TA_PM_TASKS_project_id" ON "TB_TA_PM_TASKS" (project_id);

-- Index: ix_TB_TA_PM_TASKS_solution_id
CREATE INDEX "ix_TB_TA_PM_TASKS_solution_id" ON "TB_TA_PM_TASKS" (solution_id);

-- Index: ix_TB_TA_PM_TASKS_space_id
CREATE INDEX "ix_TB_TA_PM_TASKS_space_id" ON "TB_TA_PM_TASKS" (space_id);

-- Index: ix_TB_TA_PM_TASKS_status
CREATE INDEX "ix_TB_TA_PM_TASKS_status" ON "TB_TA_PM_TASKS" (status);

-- Index: ix_TB_TA_PM_TEAMS_deleted_at
CREATE INDEX "ix_TB_TA_PM_TEAMS_deleted_at" ON "TB_TA_PM_TEAMS" (deleted_at);

-- Index: ix_TB_TA_PM_TEAMS_space_id
CREATE INDEX "ix_TB_TA_PM_TEAMS_space_id" ON "TB_TA_PM_TEAMS" (space_id);

-- Index: ix_TB_TA_PM_TEAM_MEMBERS_deleted_at
CREATE INDEX "ix_TB_TA_PM_TEAM_MEMBERS_deleted_at" ON "TB_TA_PM_TEAM_MEMBERS" (deleted_at);

-- Index: ix_TB_TA_PM_TEAM_MEMBERS_member_name
CREATE INDEX "ix_TB_TA_PM_TEAM_MEMBERS_member_name" ON "TB_TA_PM_TEAM_MEMBERS" (member_name);

-- Index: ix_TB_TA_PM_TEAM_MEMBERS_space_id
CREATE INDEX "ix_TB_TA_PM_TEAM_MEMBERS_space_id" ON "TB_TA_PM_TEAM_MEMBERS" (space_id);

-- Index: ix_TB_TA_PM_TEAM_MEMBERS_team_id
CREATE INDEX "ix_TB_TA_PM_TEAM_MEMBERS_team_id" ON "TB_TA_PM_TEAM_MEMBERS" (team_id);

-- Index: ix_TB_TA_PM_USERS_team_tag
CREATE INDEX "ix_TB_TA_PM_USERS_team_tag" ON "TB_TA_PM_USERS" (team_tag);
