-- SIPM repair migration: create missing space access request table.
-- Use this when the app is deployed before the full space onboarding migration ran.
-- Safe to re-run.

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_tables
	WHERE table_name = 'TB_TA_PM_SPACE_ACCESS_REQUESTS';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE q'[
			CREATE TABLE "TB_TA_PM_SPACE_ACCESS_REQUESTS" (
				request_id VARCHAR2(255 CHAR) NOT NULL,
				space_id VARCHAR2(255 CHAR) NOT NULL,
				requester_user_id VARCHAR2(255 CHAR) NOT NULL,
				requested_role VARCHAR2(255 CHAR) DEFAULT 'member' NOT NULL,
				status VARCHAR2(255 CHAR) DEFAULT 'pending' NOT NULL,
				decided_by_user_id VARCHAR2(255 CHAR),
				decided_at DATE,
				decision_note CLOB,
				created_at DATE NOT NULL,
				updated_at DATE NOT NULL,
				CONSTRAINT space_access_requests_pk PRIMARY KEY (request_id),
				CONSTRAINT space_access_requests_space_fk
					FOREIGN KEY (space_id)
					REFERENCES "TB_TA_PM_SPACES" (space_id),
				CONSTRAINT space_access_requests_requester_fk
					FOREIGN KEY (requester_user_id)
					REFERENCES "TB_TA_PM_USERS" (user_id),
				CONSTRAINT space_access_requests_decider_fk
					FOREIGN KEY (decided_by_user_id)
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
	WHERE index_name = 'IDX_SPACE_ACCESS_REQUEST_SPACE_STATUS';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX idx_space_access_request_space_status ON "TB_TA_PM_SPACE_ACCESS_REQUESTS" (space_id, status, created_at)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'IDX_SPACE_ACCESS_REQUEST_REQUESTER_STATUS';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX idx_space_access_request_requester_status ON "TB_TA_PM_SPACE_ACCESS_REQUESTS" (requester_user_id, status, created_at)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'ix_TB_TA_PM_SPACE_ACCESS_REQUESTS_space_id';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX "ix_TB_TA_PM_SPACE_ACCESS_REQUESTS_space_id" ON "TB_TA_PM_SPACE_ACCESS_REQUESTS" (space_id)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'ix_TB_TA_PM_SPACE_ACCESS_REQUESTS_requester_user_id';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX "ix_TB_TA_PM_SPACE_ACCESS_REQUESTS_requester_user_id" ON "TB_TA_PM_SPACE_ACCESS_REQUESTS" (requester_user_id)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'ix_TB_TA_PM_SPACE_ACCESS_REQUESTS_status';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE
			'CREATE INDEX "ix_TB_TA_PM_SPACE_ACCESS_REQUESTS_status" ON "TB_TA_PM_SPACE_ACCESS_REQUESTS" (status)';
	END IF;
END;
/

COMMIT;
