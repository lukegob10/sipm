-- Agent Approval Gate V1 migration.
-- Adds the pending approval queue used by service-account agent submissions.
-- Safe to re-run: each object is created only when it does not already exist.

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_tables
	WHERE table_name = 'TB_TA_PM_AGENT_CHANGE_REQUESTS';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE q'[
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
				CONSTRAINT agent_cr_pk PRIMARY KEY (change_request_id),
				CONSTRAINT agent_cr_space_fk
					FOREIGN KEY (space_id)
					REFERENCES "TB_TA_PM_SPACES" (space_id),
				CONSTRAINT agent_cr_proposer_fk
					FOREIGN KEY (proposed_by_user_id)
					REFERENCES "TB_TA_PM_USERS" (user_id),
				CONSTRAINT agent_cr_reviewer_fk
					FOREIGN KEY (reviewed_by_user_id)
					REFERENCES "TB_TA_PM_USERS" (user_id)
			)
		]';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'IDX_AGENT_CR_SPACE_STATUS';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX idx_agent_cr_space_status ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (space_id, status, created_at)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'IDX_AGENT_CR_PROPOSER';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX idx_agent_cr_proposer ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (proposed_by_user_id, created_at)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_space_id';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX "ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_space_id" ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (space_id)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_proposed_by_user_id';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX "ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_proposed_by_user_id" ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (proposed_by_user_id)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_reviewed_by_user_id';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX "ix_TB_TA_PM_AGENT_CHANGE_REQUESTS_reviewed_by_user_id" ON "TB_TA_PM_AGENT_CHANGE_REQUESTS" (reviewed_by_user_id)';
	END IF;
END;
/
