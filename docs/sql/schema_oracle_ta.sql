-- Oracle DDL generated from SQLAlchemy models.
-- Table names follow TB_TA_PM_* with no schema qualifier.

-- Table: TB_TA_PM_EXTERNAL_REF

CREATE TABLE "TB_TA_PM_EXTERNAL_REF" (
	external_ref_id VARCHAR2 NOT NULL, 
	work_item_type VARCHAR2 NOT NULL, 
	work_item_id VARCHAR2 NOT NULL, 
	ref_type VARCHAR2 NOT NULL, 
	ref_url VARCHAR2, 
	ref_key VARCHAR2, 
	label VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (external_ref_id), 
	CONSTRAINT uix_external_ref_unique UNIQUE (work_item_type, work_item_id, ref_type, ref_key)
);

-- Table: TB_TA_PM_PHASES

CREATE TABLE "TB_TA_PM_PHASES" (
	phase_id VARCHAR2 NOT NULL, 
	phase_group VARCHAR2 NOT NULL, 
	phase_name VARCHAR2 NOT NULL, 
	sequence INTEGER NOT NULL, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (phase_id)
);

-- Table: TB_TA_PM_SPACES

CREATE TABLE "TB_TA_PM_SPACES" (
	space_id VARCHAR2 NOT NULL, 
	name VARCHAR2 NOT NULL, 
	slug VARCHAR2 NOT NULL, 
	is_active SMALLINT NOT NULL, 
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
	user_id VARCHAR2 NOT NULL, 
	soeid VARCHAR2 NOT NULL, 
	email VARCHAR2 NOT NULL, 
	display_name VARCHAR2 NOT NULL, 
	password_hash VARCHAR2 NOT NULL, 
	role VARCHAR2 NOT NULL, 
	is_active SMALLINT NOT NULL, 
	team_tag VARCHAR2, 
	capacity_hours INTEGER NOT NULL, 
	capacity_fte_month FLOAT NOT NULL, 
	failed_attempts INTEGER NOT NULL, 
	locked_until DATE, 
	last_login_at DATE, 
	external_id VARCHAR2, 
	temp_password_hash VARCHAR2, 
	temp_password_expires_at DATE, 
	force_password_reset SMALLINT NOT NULL, 
	password_changed_at DATE, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (user_id), 
	CONSTRAINT uix_user_email UNIQUE (email), 
	CONSTRAINT uix_user_soeid UNIQUE (soeid)
);

-- Table: TB_TA_PM_AI_REQUESTS

CREATE TABLE "TB_TA_PM_AI_REQUESTS" (
	ai_request_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	request_type VARCHAR2 NOT NULL, 
	entity_type VARCHAR2, 
	entity_id VARCHAR2, 
	instruction VARCHAR2, 
	prompt VARCHAR2, 
	output VARCHAR2, 
	approved SMALLINT NOT NULL, 
	approved_by_user_id VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (ai_request_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(approved_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_CHANGE_LOG

CREATE TABLE "TB_TA_PM_CHANGE_LOG" (
	change_id VARCHAR2 NOT NULL, 
	entity_type VARCHAR2 NOT NULL, 
	entity_id VARCHAR2 NOT NULL, 
	action VARCHAR2 NOT NULL, 
	field VARCHAR2, 
	old_value VARCHAR2, 
	new_value VARCHAR2, 
	user_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	request_id VARCHAR2, 
	created_at DATE NOT NULL, 
	PRIMARY KEY (change_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_PLANNING_WINDOWS

CREATE TABLE "TB_TA_PM_PLANNING_WINDOWS" (
	window_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	name VARCHAR2 NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (window_id), 
	CONSTRAINT uix_planning_window_name UNIQUE (name), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_PROJECTS

CREATE TABLE "TB_TA_PM_PROJECTS" (
	project_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_name VARCHAR2 NOT NULL, 
	status VARCHAR(11 CHAR) NOT NULL, 
	description VARCHAR2, 
	success_criteria VARCHAR2, 
	sponsor VARCHAR2 NOT NULL, 
	sponsor_user_soeid VARCHAR2, 
	strategic_objective VARCHAR2, 
	priority INTEGER NOT NULL, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (project_id), 
	CONSTRAINT uix_project_name UNIQUE (project_name), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_SPACE_MEMBERSHIPS

CREATE TABLE "TB_TA_PM_SPACE_MEMBERSHIPS" (
	membership_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2 NOT NULL, 
	user_id VARCHAR2 NOT NULL, 
	role VARCHAR2 NOT NULL, 
	status VARCHAR2 NOT NULL, 
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
	team_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	name VARCHAR2 NOT NULL, 
	description VARCHAR2, 
	lead VARCHAR2, 
	default_capacity_per_week INTEGER NOT NULL, 
	default_capacity_fte_month FLOAT NOT NULL, 
	capacity_unit VARCHAR2 NOT NULL, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (team_id), 
	CONSTRAINT uix_team_name UNIQUE (name), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_AI_SESSIONS

CREATE TABLE "TB_TA_PM_AI_SESSIONS" (
	session_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2, 
	entity_type VARCHAR2, 
	entity_id VARCHAR2, 
	user_id VARCHAR2, 
	messages CLOB, 
	last_active_at DATE, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (session_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_AI_TOOL_CALLS

CREATE TABLE "TB_TA_PM_AI_TOOL_CALLS" (
	tool_call_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	ai_request_id VARCHAR2, 
	tool_name VARCHAR2 NOT NULL, 
	payload CLOB, 
	output CLOB, 
	status VARCHAR2, 
	elapsed_ms INTEGER, 
	payload_bytes INTEGER, 
	output_bytes INTEGER, 
	payload_tokens INTEGER, 
	output_tokens INTEGER, 
	cache_hit SMALLINT, 
	drilldown SMALLINT, 
	context_bytes INTEGER, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (tool_call_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(ai_request_id) REFERENCES "TB_TA_PM_AI_REQUESTS" (ai_request_id)
);

-- Table: TB_TA_PM_CHECKLIST_ITEMS

CREATE TABLE "TB_TA_PM_CHECKLIST_ITEMS" (
	checklist_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2 NOT NULL, 
	month_key VARCHAR2 NOT NULL, 
	title VARCHAR2 NOT NULL, 
	status VARCHAR2 NOT NULL, 
	created_by_user_id VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (checklist_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(created_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_PROJECT_CARD_DIGESTS

CREATE TABLE "TB_TA_PM_PROJECT_CARD_DIGESTS" (
	project_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	tenant_id VARCHAR2, 
	project_name VARCHAR2 NOT NULL, 
	status VARCHAR2, 
	priority INTEGER, 
	sponsor VARCHAR2, 
	open_solution_count INTEGER NOT NULL, 
	open_task_count INTEGER NOT NULL, 
	top_risks_json CLOB, 
	short_summary CLOB, 
	source_updated_at DATE, 
	refreshed_at DATE, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (project_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_PROJECT_CHARTERS

CREATE TABLE "TB_TA_PM_PROJECT_CHARTERS" (
	charter_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2 NOT NULL, 
	title VARCHAR2, 
	content CLOB NOT NULL, 
	state VARCHAR2 NOT NULL, 
	created_by_user_id VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (charter_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(created_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_PROJECT_DECISION_LOGS

CREATE TABLE "TB_TA_PM_PROJECT_DECISION_LOGS" (
	decision_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2 NOT NULL, 
	title VARCHAR2, 
	decision CLOB NOT NULL, 
	rationale CLOB, 
	impact CLOB, 
	created_by_user_id VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (decision_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(created_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_PROJECT_PLANS

CREATE TABLE "TB_TA_PM_PROJECT_PLANS" (
	plan_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2 NOT NULL, 
	title VARCHAR2, 
	content CLOB NOT NULL, 
	state VARCHAR2 NOT NULL, 
	created_by_user_id VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (plan_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(created_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_RESOURCE_ALLOCATIONS

CREATE TABLE "TB_TA_PM_RESOURCE_ALLOCATIONS" (
	allocation_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	work_item_type VARCHAR2 NOT NULL, 
	work_item_id VARCHAR2 NOT NULL, 
	assignee_user_soeid VARCHAR2, 
	assignee VARCHAR2, 
	team_id VARCHAR2, 
	week_start DATE NOT NULL, 
	month_start DATE, 
	hours INTEGER NOT NULL, 
	fte_months FLOAT NOT NULL, 
	window_id VARCHAR2, 
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
	solution_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2 NOT NULL, 
	solution_name VARCHAR2 NOT NULL, 
	version VARCHAR2 NOT NULL, 
	status VARCHAR(11 CHAR) NOT NULL, 
	rag_status VARCHAR(5 CHAR) NOT NULL, 
	rag_reason VARCHAR2, 
	priority INTEGER NOT NULL, 
	due_date DATE, 
	current_phase VARCHAR2, 
	description VARCHAR2, 
	success_criteria VARCHAR2, 
	problem_statement VARCHAR2, 
	owner VARCHAR2 NOT NULL, 
	owner_user_soeid VARCHAR2, 
	assignee VARCHAR2 NOT NULL, 
	assignee_user_soeid VARCHAR2, 
	approver VARCHAR2, 
	approver_user_soeid VARCHAR2, 
	key_stakeholder VARCHAR2, 
	blockers VARCHAR2, 
	risks VARCHAR2, 
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

-- Table: TB_TA_PM_TEAM_MEMBERS

CREATE TABLE "TB_TA_PM_TEAM_MEMBERS" (
	team_member_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	team_id VARCHAR2 NOT NULL, 
	member_name VARCHAR2 NOT NULL, 
	role VARCHAR2 NOT NULL, 
	capacity_override INTEGER, 
	capacity_unit VARCHAR2, 
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

-- Table: TB_TA_PM_AI_QUERY_METRICS

CREATE TABLE "TB_TA_PM_AI_QUERY_METRICS" (
	query_metric_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	session_id VARCHAR2, 
	user_id VARCHAR2, 
	project_id VARCHAR2, 
	entity_type VARCHAR2, 
	entity_id VARCHAR2, 
	tool_calls_count INTEGER NOT NULL, 
	context_calls_count INTEGER NOT NULL, 
	bytes_returned INTEGER NOT NULL, 
	approx_tokens_returned INTEGER NOT NULL, 
	bytes_sent INTEGER NOT NULL, 
	approx_tokens_sent INTEGER NOT NULL, 
	cache_hit_rate FLOAT, 
	drilldown_rate FLOAT, 
	answer_quality_score FLOAT, 
	notes CLOB, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (query_metric_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(session_id) REFERENCES "TB_TA_PM_AI_SESSIONS" (session_id), 
	FOREIGN KEY(user_id) REFERENCES "TB_TA_PM_USERS" (user_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id)
);

-- Table: TB_TA_PM_EXTERNAL_DOCUMENTS

CREATE TABLE "TB_TA_PM_EXTERNAL_DOCUMENTS" (
	document_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2, 
	solution_id VARCHAR2, 
	filename VARCHAR2 NOT NULL, 
	content_type VARCHAR2, 
	storage_path VARCHAR2 NOT NULL, 
	uploaded_by_user_id VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (document_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id), 
	FOREIGN KEY(uploaded_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_SOLUTION_CARD_DIGESTS

CREATE TABLE "TB_TA_PM_SOLUTION_CARD_DIGESTS" (
	solution_id VARCHAR2 NOT NULL, 
	project_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	tenant_id VARCHAR2, 
	solution_name VARCHAR2 NOT NULL, 
	status VARCHAR2, 
	rag_status VARCHAR2, 
	priority INTEGER, 
	current_phase VARCHAR2, 
	due_date DATE, 
	owner VARCHAR2, 
	assignee VARCHAR2, 
	open_task_count INTEGER NOT NULL, 
	blocked_task_count INTEGER NOT NULL, 
	top_risks_json CLOB, 
	short_summary CLOB, 
	source_updated_at DATE, 
	refreshed_at DATE, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (solution_id), 
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Table: TB_TA_PM_SOLUTION_PHASES

CREATE TABLE "TB_TA_PM_SOLUTION_PHASES" (
	solution_phase_id VARCHAR2 NOT NULL, 
	solution_id VARCHAR2 NOT NULL, 
	phase_id VARCHAR2 NOT NULL, 
	is_enabled SMALLINT NOT NULL, 
	sequence_override INTEGER, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (solution_phase_id), 
	CONSTRAINT uix_solution_phase UNIQUE (solution_id, phase_id), 
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id), 
	FOREIGN KEY(phase_id) REFERENCES "TB_TA_PM_PHASES" (phase_id)
);

-- Table: TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT

CREATE TABLE "TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT" (
	snapshot_id VARCHAR2 NOT NULL, 
	solution_id VARCHAR2 NOT NULL, 
	week_start DATE NOT NULL, 
	rag_status VARCHAR(5 CHAR) NOT NULL, 
	progress_note VARCHAR2, 
	next_week_plan VARCHAR2, 
	confidence_on_due_date VARCHAR(6 CHAR), 
	owner_user_id VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (snapshot_id), 
	CONSTRAINT uix_solution_week_start UNIQUE (solution_id, week_start), 
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id), 
	FOREIGN KEY(owner_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_SOW_DOCUMENTS

CREATE TABLE "TB_TA_PM_SOW_DOCUMENTS" (
	sow_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2 NOT NULL, 
	solution_id VARCHAR2, 
	title VARCHAR2, 
	content VARCHAR2 NOT NULL, 
	state VARCHAR2 NOT NULL, 
	approval_state VARCHAR2 NOT NULL, 
	approval_requested_at DATE, 
	approval_requested_by_user_id VARCHAR2, 
	approval_decided_at DATE, 
	approval_decided_by_user_id VARCHAR2, 
	approval_note CLOB, 
	created_by_user_id VARCHAR2, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (sow_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id), 
	FOREIGN KEY(approval_requested_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id), 
	FOREIGN KEY(approval_decided_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id), 
	FOREIGN KEY(created_by_user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
);

-- Table: TB_TA_PM_SUBCOMPONENTS

CREATE TABLE "TB_TA_PM_SUBCOMPONENTS" (
	subcomponent_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	project_id VARCHAR2 NOT NULL, 
	solution_id VARCHAR2 NOT NULL, 
	subcomponent_name VARCHAR2 NOT NULL, 
	status VARCHAR(11 CHAR) NOT NULL, 
	priority INTEGER NOT NULL, 
	due_date DATE, 
	completed_at DATE, 
	assignee_user_soeid VARCHAR2, 
	assignee VARCHAR2 NOT NULL, 
	estimate_hours INTEGER, 
	blocked SMALLINT NOT NULL, 
	blocker_note VARCHAR2, 
	done_criteria VARCHAR2, 
	capacity_hours INTEGER NOT NULL, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	deleted_at DATE, 
	PRIMARY KEY (subcomponent_id), 
	CONSTRAINT uix_subcomponent_solution_name UNIQUE (solution_id, subcomponent_name), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id)
);

-- Table: TB_TA_PM_TASK_CARD_DIGESTS

CREATE TABLE "TB_TA_PM_TASK_CARD_DIGESTS" (
	subcomponent_id VARCHAR2 NOT NULL, 
	project_id VARCHAR2 NOT NULL, 
	solution_id VARCHAR2 NOT NULL, 
	space_id VARCHAR2, 
	tenant_id VARCHAR2, 
	subcomponent_name VARCHAR2 NOT NULL, 
	status VARCHAR2, 
	priority INTEGER, 
	assignee VARCHAR2, 
	due_date DATE, 
	blocked SMALLINT NOT NULL, 
	blocker_note CLOB, 
	estimate_hours INTEGER, 
	short_summary CLOB, 
	source_updated_at DATE, 
	refreshed_at DATE, 
	created_at DATE NOT NULL, 
	updated_at DATE NOT NULL, 
	PRIMARY KEY (subcomponent_id), 
	FOREIGN KEY(subcomponent_id) REFERENCES "TB_TA_PM_SUBCOMPONENTS" (subcomponent_id), 
	FOREIGN KEY(project_id) REFERENCES "TB_TA_PM_PROJECTS" (project_id), 
	FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id), 
	FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id)
);

-- Index: idx_ai_query_metrics_project_created
CREATE INDEX idx_ai_query_metrics_project_created ON "TB_TA_PM_AI_QUERY_METRICS" (project_id, created_at);

-- Index: idx_ai_query_metrics_session_created
CREATE INDEX idx_ai_query_metrics_session_created ON "TB_TA_PM_AI_QUERY_METRICS" (session_id, created_at);

-- Index: idx_alloc_item
CREATE INDEX idx_alloc_item ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (work_item_type, work_item_id);

-- Index: idx_alloc_month_assignee
CREATE INDEX idx_alloc_month_assignee ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (month_start, assignee_user_soeid);

-- Index: idx_alloc_week_assignee
CREATE INDEX idx_alloc_week_assignee ON "TB_TA_PM_RESOURCE_ALLOCATIONS" (week_start, assignee_user_soeid);

-- Index: idx_change_entity_created
CREATE INDEX idx_change_entity_created ON "TB_TA_PM_CHANGE_LOG" (entity_type, entity_id, created_at);

-- Index: idx_change_request
CREATE INDEX idx_change_request ON "TB_TA_PM_CHANGE_LOG" (request_id);

-- Index: idx_change_user_created
CREATE INDEX idx_change_user_created ON "TB_TA_PM_CHANGE_LOG" (user_id, created_at);

-- Index: idx_external_ref_work_item
CREATE INDEX idx_external_ref_work_item ON "TB_TA_PM_EXTERNAL_REF" (work_item_type, work_item_id);

-- Index: idx_snapshot_solution_week
CREATE INDEX idx_snapshot_solution_week ON "TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT" (solution_id, week_start);

-- Index: idx_team_member_team
CREATE INDEX idx_team_member_team ON "TB_TA_PM_TEAM_MEMBERS" (team_id);

-- Index: ix_TB_TA_PM_AI_QUERY_METRICS_project_id
CREATE INDEX "ix_TB_TA_PM_AI_QUERY_METRICS_project_id" ON "TB_TA_PM_AI_QUERY_METRICS" (project_id);

-- Index: ix_TB_TA_PM_AI_QUERY_METRICS_session_id
CREATE INDEX "ix_TB_TA_PM_AI_QUERY_METRICS_session_id" ON "TB_TA_PM_AI_QUERY_METRICS" (session_id);

-- Index: ix_TB_TA_PM_AI_QUERY_METRICS_space_id
CREATE INDEX "ix_TB_TA_PM_AI_QUERY_METRICS_space_id" ON "TB_TA_PM_AI_QUERY_METRICS" (space_id);

-- Index: ix_TB_TA_PM_AI_QUERY_METRICS_user_id
CREATE INDEX "ix_TB_TA_PM_AI_QUERY_METRICS_user_id" ON "TB_TA_PM_AI_QUERY_METRICS" (user_id);

-- Index: ix_TB_TA_PM_AI_REQUESTS_approved_by_user_id
CREATE INDEX "ix_TB_TA_PM_AI_REQUESTS_approved_by_user_id" ON "TB_TA_PM_AI_REQUESTS" (approved_by_user_id);

-- Index: ix_TB_TA_PM_AI_REQUESTS_space_id
CREATE INDEX "ix_TB_TA_PM_AI_REQUESTS_space_id" ON "TB_TA_PM_AI_REQUESTS" (space_id);

-- Index: ix_TB_TA_PM_AI_SESSIONS_project_id
CREATE INDEX "ix_TB_TA_PM_AI_SESSIONS_project_id" ON "TB_TA_PM_AI_SESSIONS" (project_id);

-- Index: ix_TB_TA_PM_AI_SESSIONS_space_id
CREATE INDEX "ix_TB_TA_PM_AI_SESSIONS_space_id" ON "TB_TA_PM_AI_SESSIONS" (space_id);

-- Index: ix_TB_TA_PM_AI_SESSIONS_user_id
CREATE INDEX "ix_TB_TA_PM_AI_SESSIONS_user_id" ON "TB_TA_PM_AI_SESSIONS" (user_id);

-- Index: ix_TB_TA_PM_AI_TOOL_CALLS_ai_request_id
CREATE INDEX "ix_TB_TA_PM_AI_TOOL_CALLS_ai_request_id" ON "TB_TA_PM_AI_TOOL_CALLS" (ai_request_id);

-- Index: ix_TB_TA_PM_AI_TOOL_CALLS_space_id
CREATE INDEX "ix_TB_TA_PM_AI_TOOL_CALLS_space_id" ON "TB_TA_PM_AI_TOOL_CALLS" (space_id);

-- Index: ix_TB_TA_PM_CHANGE_LOG_created_at
CREATE INDEX "ix_TB_TA_PM_CHANGE_LOG_created_at" ON "TB_TA_PM_CHANGE_LOG" (created_at);

-- Index: ix_TB_TA_PM_CHANGE_LOG_request_id
CREATE INDEX "ix_TB_TA_PM_CHANGE_LOG_request_id" ON "TB_TA_PM_CHANGE_LOG" (request_id);

-- Index: ix_TB_TA_PM_CHANGE_LOG_space_id
CREATE INDEX "ix_TB_TA_PM_CHANGE_LOG_space_id" ON "TB_TA_PM_CHANGE_LOG" (space_id);

-- Index: ix_TB_TA_PM_CHANGE_LOG_user_id
CREATE INDEX "ix_TB_TA_PM_CHANGE_LOG_user_id" ON "TB_TA_PM_CHANGE_LOG" (user_id);

-- Index: ix_TB_TA_PM_CHECKLIST_ITEMS_created_by_user_id
CREATE INDEX "ix_TB_TA_PM_CHECKLIST_ITEMS_created_by_user_id" ON "TB_TA_PM_CHECKLIST_ITEMS" (created_by_user_id);

-- Index: ix_TB_TA_PM_CHECKLIST_ITEMS_deleted_at
CREATE INDEX "ix_TB_TA_PM_CHECKLIST_ITEMS_deleted_at" ON "TB_TA_PM_CHECKLIST_ITEMS" (deleted_at);

-- Index: ix_TB_TA_PM_CHECKLIST_ITEMS_month_key
CREATE INDEX "ix_TB_TA_PM_CHECKLIST_ITEMS_month_key" ON "TB_TA_PM_CHECKLIST_ITEMS" (month_key);

-- Index: ix_TB_TA_PM_CHECKLIST_ITEMS_project_id
CREATE INDEX "ix_TB_TA_PM_CHECKLIST_ITEMS_project_id" ON "TB_TA_PM_CHECKLIST_ITEMS" (project_id);

-- Index: ix_TB_TA_PM_CHECKLIST_ITEMS_space_id
CREATE INDEX "ix_TB_TA_PM_CHECKLIST_ITEMS_space_id" ON "TB_TA_PM_CHECKLIST_ITEMS" (space_id);

-- Index: ix_TB_TA_PM_EXTERNAL_DOCUMENTS_deleted_at
CREATE INDEX "ix_TB_TA_PM_EXTERNAL_DOCUMENTS_deleted_at" ON "TB_TA_PM_EXTERNAL_DOCUMENTS" (deleted_at);

-- Index: ix_TB_TA_PM_EXTERNAL_DOCUMENTS_project_id
CREATE INDEX "ix_TB_TA_PM_EXTERNAL_DOCUMENTS_project_id" ON "TB_TA_PM_EXTERNAL_DOCUMENTS" (project_id);

-- Index: ix_TB_TA_PM_EXTERNAL_DOCUMENTS_solution_id
CREATE INDEX "ix_TB_TA_PM_EXTERNAL_DOCUMENTS_solution_id" ON "TB_TA_PM_EXTERNAL_DOCUMENTS" (solution_id);

-- Index: ix_TB_TA_PM_EXTERNAL_DOCUMENTS_space_id
CREATE INDEX "ix_TB_TA_PM_EXTERNAL_DOCUMENTS_space_id" ON "TB_TA_PM_EXTERNAL_DOCUMENTS" (space_id);

-- Index: ix_TB_TA_PM_EXTERNAL_DOCUMENTS_uploaded_by_user_id
CREATE INDEX "ix_TB_TA_PM_EXTERNAL_DOCUMENTS_uploaded_by_user_id" ON "TB_TA_PM_EXTERNAL_DOCUMENTS" (uploaded_by_user_id);

-- Index: ix_TB_TA_PM_EXTERNAL_REF_deleted_at
CREATE INDEX "ix_TB_TA_PM_EXTERNAL_REF_deleted_at" ON "TB_TA_PM_EXTERNAL_REF" (deleted_at);

-- Index: ix_TB_TA_PM_EXTERNAL_REF_work_item_id
CREATE INDEX "ix_TB_TA_PM_EXTERNAL_REF_work_item_id" ON "TB_TA_PM_EXTERNAL_REF" (work_item_id);

-- Index: ix_TB_TA_PM_PHASES_sequence
CREATE INDEX "ix_TB_TA_PM_PHASES_sequence" ON "TB_TA_PM_PHASES" (sequence);

-- Index: ix_TB_TA_PM_PLANNING_WINDOWS_deleted_at
CREATE INDEX "ix_TB_TA_PM_PLANNING_WINDOWS_deleted_at" ON "TB_TA_PM_PLANNING_WINDOWS" (deleted_at);

-- Index: ix_TB_TA_PM_PLANNING_WINDOWS_space_id
CREATE INDEX "ix_TB_TA_PM_PLANNING_WINDOWS_space_id" ON "TB_TA_PM_PLANNING_WINDOWS" (space_id);

-- Index: ix_TB_TA_PM_PROJECTS_deleted_at
CREATE INDEX "ix_TB_TA_PM_PROJECTS_deleted_at" ON "TB_TA_PM_PROJECTS" (deleted_at);

-- Index: ix_TB_TA_PM_PROJECTS_project_name
CREATE INDEX "ix_TB_TA_PM_PROJECTS_project_name" ON "TB_TA_PM_PROJECTS" (project_name);

-- Index: ix_TB_TA_PM_PROJECTS_space_id
CREATE INDEX "ix_TB_TA_PM_PROJECTS_space_id" ON "TB_TA_PM_PROJECTS" (space_id);

-- Index: ix_TB_TA_PM_PROJECTS_sponsor_user_soeid
CREATE INDEX "ix_TB_TA_PM_PROJECTS_sponsor_user_soeid" ON "TB_TA_PM_PROJECTS" (sponsor_user_soeid);

-- Index: ix_TB_TA_PM_PROJECTS_status
CREATE INDEX "ix_TB_TA_PM_PROJECTS_status" ON "TB_TA_PM_PROJECTS" (status);

-- Index: ix_TB_TA_PM_PROJECT_CARD_DIGESTS_project_name
CREATE INDEX "ix_TB_TA_PM_PROJECT_CARD_DIGESTS_project_name" ON "TB_TA_PM_PROJECT_CARD_DIGESTS" (project_name);

-- Index: ix_TB_TA_PM_PROJECT_CARD_DIGESTS_refreshed_at
CREATE INDEX "ix_TB_TA_PM_PROJECT_CARD_DIGESTS_refreshed_at" ON "TB_TA_PM_PROJECT_CARD_DIGESTS" (refreshed_at);

-- Index: ix_TB_TA_PM_PROJECT_CARD_DIGESTS_source_updated_at
CREATE INDEX "ix_TB_TA_PM_PROJECT_CARD_DIGESTS_source_updated_at" ON "TB_TA_PM_PROJECT_CARD_DIGESTS" (source_updated_at);

-- Index: ix_TB_TA_PM_PROJECT_CARD_DIGESTS_space_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_CARD_DIGESTS_space_id" ON "TB_TA_PM_PROJECT_CARD_DIGESTS" (space_id);

-- Index: ix_TB_TA_PM_PROJECT_CARD_DIGESTS_status
CREATE INDEX "ix_TB_TA_PM_PROJECT_CARD_DIGESTS_status" ON "TB_TA_PM_PROJECT_CARD_DIGESTS" (status);

-- Index: ix_TB_TA_PM_PROJECT_CARD_DIGESTS_tenant_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_CARD_DIGESTS_tenant_id" ON "TB_TA_PM_PROJECT_CARD_DIGESTS" (tenant_id);

-- Index: ix_TB_TA_PM_PROJECT_CHARTERS_created_by_user_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_CHARTERS_created_by_user_id" ON "TB_TA_PM_PROJECT_CHARTERS" (created_by_user_id);

-- Index: ix_TB_TA_PM_PROJECT_CHARTERS_deleted_at
CREATE INDEX "ix_TB_TA_PM_PROJECT_CHARTERS_deleted_at" ON "TB_TA_PM_PROJECT_CHARTERS" (deleted_at);

-- Index: ix_TB_TA_PM_PROJECT_CHARTERS_project_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_CHARTERS_project_id" ON "TB_TA_PM_PROJECT_CHARTERS" (project_id);

-- Index: ix_TB_TA_PM_PROJECT_CHARTERS_space_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_CHARTERS_space_id" ON "TB_TA_PM_PROJECT_CHARTERS" (space_id);

-- Index: ix_TB_TA_PM_PROJECT_CHARTERS_state
CREATE INDEX "ix_TB_TA_PM_PROJECT_CHARTERS_state" ON "TB_TA_PM_PROJECT_CHARTERS" (state);

-- Index: ix_TB_TA_PM_PROJECT_DECISION_LOGS_created_by_user_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_DECISION_LOGS_created_by_user_id" ON "TB_TA_PM_PROJECT_DECISION_LOGS" (created_by_user_id);

-- Index: ix_TB_TA_PM_PROJECT_DECISION_LOGS_deleted_at
CREATE INDEX "ix_TB_TA_PM_PROJECT_DECISION_LOGS_deleted_at" ON "TB_TA_PM_PROJECT_DECISION_LOGS" (deleted_at);

-- Index: ix_TB_TA_PM_PROJECT_DECISION_LOGS_project_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_DECISION_LOGS_project_id" ON "TB_TA_PM_PROJECT_DECISION_LOGS" (project_id);

-- Index: ix_TB_TA_PM_PROJECT_DECISION_LOGS_space_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_DECISION_LOGS_space_id" ON "TB_TA_PM_PROJECT_DECISION_LOGS" (space_id);

-- Index: ix_TB_TA_PM_PROJECT_PLANS_created_by_user_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_PLANS_created_by_user_id" ON "TB_TA_PM_PROJECT_PLANS" (created_by_user_id);

-- Index: ix_TB_TA_PM_PROJECT_PLANS_deleted_at
CREATE INDEX "ix_TB_TA_PM_PROJECT_PLANS_deleted_at" ON "TB_TA_PM_PROJECT_PLANS" (deleted_at);

-- Index: ix_TB_TA_PM_PROJECT_PLANS_project_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_PLANS_project_id" ON "TB_TA_PM_PROJECT_PLANS" (project_id);

-- Index: ix_TB_TA_PM_PROJECT_PLANS_space_id
CREATE INDEX "ix_TB_TA_PM_PROJECT_PLANS_space_id" ON "TB_TA_PM_PROJECT_PLANS" (space_id);

-- Index: ix_TB_TA_PM_PROJECT_PLANS_state
CREATE INDEX "ix_TB_TA_PM_PROJECT_PLANS_state" ON "TB_TA_PM_PROJECT_PLANS" (state);

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

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_due_date
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_due_date" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (due_date);

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_project_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_project_id" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (project_id);

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_rag_status
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_rag_status" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (rag_status);

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_refreshed_at
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_refreshed_at" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (refreshed_at);

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_solution_name
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_solution_name" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (solution_name);

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_source_updated_at
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_source_updated_at" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (source_updated_at);

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_space_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_space_id" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (space_id);

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_status
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_status" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (status);

-- Index: ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_tenant_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_CARD_DIGESTS_tenant_id" ON "TB_TA_PM_SOLUTION_CARD_DIGESTS" (tenant_id);

-- Index: ix_TB_TA_PM_SOLUTION_PHASES_sequence_override
CREATE INDEX "ix_TB_TA_PM_SOLUTION_PHASES_sequence_override" ON "TB_TA_PM_SOLUTION_PHASES" (sequence_override);

-- Index: ix_TB_TA_PM_SOLUTION_PHASES_solution_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_PHASES_solution_id" ON "TB_TA_PM_SOLUTION_PHASES" (solution_id);

-- Index: ix_TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT_deleted_at
CREATE INDEX "ix_TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT_deleted_at" ON "TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT" (deleted_at);

-- Index: ix_TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT_owner_user_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT_owner_user_id" ON "TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT" (owner_user_id);

-- Index: ix_TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT_solution_id
CREATE INDEX "ix_TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT_solution_id" ON "TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT" (solution_id);

-- Index: ix_TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT_week_start
CREATE INDEX "ix_TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT_week_start" ON "TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT" (week_start);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_approval_decided_by_user_id
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_approval_decided_by_user_id" ON "TB_TA_PM_SOW_DOCUMENTS" (approval_decided_by_user_id);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_approval_requested_by_user_id
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_approval_requested_by_user_id" ON "TB_TA_PM_SOW_DOCUMENTS" (approval_requested_by_user_id);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_approval_state
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_approval_state" ON "TB_TA_PM_SOW_DOCUMENTS" (approval_state);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_created_by_user_id
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_created_by_user_id" ON "TB_TA_PM_SOW_DOCUMENTS" (created_by_user_id);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_deleted_at
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_deleted_at" ON "TB_TA_PM_SOW_DOCUMENTS" (deleted_at);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_project_id
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_project_id" ON "TB_TA_PM_SOW_DOCUMENTS" (project_id);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_solution_id
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_solution_id" ON "TB_TA_PM_SOW_DOCUMENTS" (solution_id);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_space_id
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_space_id" ON "TB_TA_PM_SOW_DOCUMENTS" (space_id);

-- Index: ix_TB_TA_PM_SOW_DOCUMENTS_state
CREATE INDEX "ix_TB_TA_PM_SOW_DOCUMENTS_state" ON "TB_TA_PM_SOW_DOCUMENTS" (state);

-- Index: ix_TB_TA_PM_SPACES_archived_at
CREATE INDEX "ix_TB_TA_PM_SPACES_archived_at" ON "TB_TA_PM_SPACES" (archived_at);

-- Index: ix_TB_TA_PM_SPACES_deleted_at
CREATE INDEX "ix_TB_TA_PM_SPACES_deleted_at" ON "TB_TA_PM_SPACES" (deleted_at);

-- Index: ix_TB_TA_PM_SPACES_is_active
CREATE INDEX "ix_TB_TA_PM_SPACES_is_active" ON "TB_TA_PM_SPACES" (is_active);

-- Index: ix_TB_TA_PM_SPACES_name
CREATE INDEX "ix_TB_TA_PM_SPACES_name" ON "TB_TA_PM_SPACES" (name);

-- Index: ix_TB_TA_PM_SPACES_slug
CREATE INDEX "ix_TB_TA_PM_SPACES_slug" ON "TB_TA_PM_SPACES" (slug);

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

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_assignee_user_soeid
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_assignee_user_soeid" ON "TB_TA_PM_SUBCOMPONENTS" (assignee_user_soeid);

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_blocked
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_blocked" ON "TB_TA_PM_SUBCOMPONENTS" (blocked);

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_deleted_at
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_deleted_at" ON "TB_TA_PM_SUBCOMPONENTS" (deleted_at);

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_due_date
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_due_date" ON "TB_TA_PM_SUBCOMPONENTS" (due_date);

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_priority
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_priority" ON "TB_TA_PM_SUBCOMPONENTS" (priority);

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_project_id
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_project_id" ON "TB_TA_PM_SUBCOMPONENTS" (project_id);

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_solution_id
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_solution_id" ON "TB_TA_PM_SUBCOMPONENTS" (solution_id);

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_space_id
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_space_id" ON "TB_TA_PM_SUBCOMPONENTS" (space_id);

-- Index: ix_TB_TA_PM_SUBCOMPONENTS_status
CREATE INDEX "ix_TB_TA_PM_SUBCOMPONENTS_status" ON "TB_TA_PM_SUBCOMPONENTS" (status);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_blocked
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_blocked" ON "TB_TA_PM_TASK_CARD_DIGESTS" (blocked);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_due_date
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_due_date" ON "TB_TA_PM_TASK_CARD_DIGESTS" (due_date);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_project_id
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_project_id" ON "TB_TA_PM_TASK_CARD_DIGESTS" (project_id);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_refreshed_at
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_refreshed_at" ON "TB_TA_PM_TASK_CARD_DIGESTS" (refreshed_at);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_solution_id
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_solution_id" ON "TB_TA_PM_TASK_CARD_DIGESTS" (solution_id);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_source_updated_at
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_source_updated_at" ON "TB_TA_PM_TASK_CARD_DIGESTS" (source_updated_at);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_space_id
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_space_id" ON "TB_TA_PM_TASK_CARD_DIGESTS" (space_id);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_status
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_status" ON "TB_TA_PM_TASK_CARD_DIGESTS" (status);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_subcomponent_name
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_subcomponent_name" ON "TB_TA_PM_TASK_CARD_DIGESTS" (subcomponent_name);

-- Index: ix_TB_TA_PM_TASK_CARD_DIGESTS_tenant_id
CREATE INDEX "ix_TB_TA_PM_TASK_CARD_DIGESTS_tenant_id" ON "TB_TA_PM_TASK_CARD_DIGESTS" (tenant_id);

-- Index: ix_TB_TA_PM_TEAMS_deleted_at
CREATE INDEX "ix_TB_TA_PM_TEAMS_deleted_at" ON "TB_TA_PM_TEAMS" (deleted_at);

-- Index: ix_TB_TA_PM_TEAMS_name
CREATE INDEX "ix_TB_TA_PM_TEAMS_name" ON "TB_TA_PM_TEAMS" (name);

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

-- Index: ix_TB_TA_PM_USERS_email
CREATE UNIQUE INDEX "ix_TB_TA_PM_USERS_email" ON "TB_TA_PM_USERS" (email);

-- Index: ix_TB_TA_PM_USERS_soeid
CREATE UNIQUE INDEX "ix_TB_TA_PM_USERS_soeid" ON "TB_TA_PM_USERS" (soeid);

-- Index: ix_TB_TA_PM_USERS_team_tag
CREATE INDEX "ix_TB_TA_PM_USERS_team_tag" ON "TB_TA_PM_USERS" (team_tag);
