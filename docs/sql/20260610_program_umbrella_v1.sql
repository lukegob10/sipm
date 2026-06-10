-- SIPM program umbrella migration v1
-- Adds Program -> Project -> Solution -> Subcomponent hierarchy.
-- Run against an existing schema created before TB_TA_PM_PROGRAMS existed.

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

CREATE INDEX "ix_TB_TA_PM_PROGRAMS_deleted_at" ON "TB_TA_PM_PROGRAMS" (deleted_at);
CREATE INDEX "ix_TB_TA_PM_PROGRAMS_space_id" ON "TB_TA_PM_PROGRAMS" (space_id);

ALTER TABLE "TB_TA_PM_PROJECTS" ADD (
	program_id VARCHAR2(255 CHAR)
);

INSERT INTO "TB_TA_PM_PROGRAMS" (
	program_id,
	space_id,
	program_name,
	description,
	created_at,
	updated_at,
	deleted_at
)
SELECT
	LOWER(RAWTOHEX(SYS_GUID())),
	spaces.space_id,
	'Default Program',
	'Default umbrella program for existing projects.',
	SYSDATE,
	SYSDATE,
	NULL
FROM (
	SELECT DISTINCT space_id
	FROM "TB_TA_PM_PROJECTS"
	WHERE deleted_at IS NULL
) spaces
WHERE NOT EXISTS (
	SELECT 1
	FROM "TB_TA_PM_PROGRAMS" programs
	WHERE programs.program_name = 'Default Program'
	AND (
		(programs.space_id = spaces.space_id)
		OR (programs.space_id IS NULL AND spaces.space_id IS NULL)
	)
);

UPDATE "TB_TA_PM_PROJECTS" projects
SET program_id = (
	SELECT programs.program_id
	FROM "TB_TA_PM_PROGRAMS" programs
	WHERE programs.program_name = 'Default Program'
	AND (
		(programs.space_id = projects.space_id)
		OR (programs.space_id IS NULL AND projects.space_id IS NULL)
	)
	AND programs.deleted_at IS NULL
)
WHERE projects.program_id IS NULL;

ALTER TABLE "TB_TA_PM_PROJECTS" MODIFY (
	program_id VARCHAR2(255 CHAR) NOT NULL
);

ALTER TABLE "TB_TA_PM_PROJECTS" ADD CONSTRAINT fk_projects_program_id
	FOREIGN KEY (program_id) REFERENCES "TB_TA_PM_PROGRAMS" (program_id);

CREATE INDEX "ix_TB_TA_PM_PROJECTS_program_id" ON "TB_TA_PM_PROJECTS" (program_id);

COMMIT;
