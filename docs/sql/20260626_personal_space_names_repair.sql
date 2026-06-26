-- SIPM repair migration: normalize existing personal space names.
-- Personal spaces are displayed to their owner as "Personal"; the stored name stays unique as "SOEID Personal".
-- Safe to re-run.

UPDATE "TB_TA_PM_SPACES" spaces
SET name = (
		SELECT UPPER(users.soeid) || ' Personal'
		FROM "TB_TA_PM_USERS" users
		WHERE users.user_id = spaces.owner_user_id
	),
	updated_at = SYSDATE
WHERE spaces.space_kind = 'personal'
  AND spaces.owner_user_id IS NOT NULL
  AND spaces.deleted_at IS NULL
  AND EXISTS (
	SELECT 1
	FROM "TB_TA_PM_USERS" users
	WHERE users.user_id = spaces.owner_user_id
  )
  AND NOT EXISTS (
	SELECT 1
	FROM "TB_TA_PM_SPACES" other_spaces
	JOIN "TB_TA_PM_USERS" users
	  ON users.user_id = spaces.owner_user_id
	WHERE other_spaces.space_id <> spaces.space_id
	  AND other_spaces.deleted_at IS NULL
	  AND other_spaces.name = UPPER(users.soeid) || ' Personal'
  );

UPDATE "TB_TA_PM_SPACES" spaces
SET slug = (
		SELECT LOWER(users.soeid) || '-personal'
		FROM "TB_TA_PM_USERS" users
		WHERE users.user_id = spaces.owner_user_id
	),
	updated_at = SYSDATE
WHERE spaces.space_kind = 'personal'
  AND spaces.owner_user_id IS NOT NULL
  AND spaces.deleted_at IS NULL
  AND EXISTS (
	SELECT 1
	FROM "TB_TA_PM_USERS" users
	WHERE users.user_id = spaces.owner_user_id
  )
  AND NOT EXISTS (
	SELECT 1
	FROM "TB_TA_PM_SPACES" other_spaces
	JOIN "TB_TA_PM_USERS" users
	  ON users.user_id = spaces.owner_user_id
	WHERE other_spaces.space_id <> spaces.space_id
	  AND other_spaces.deleted_at IS NULL
	  AND other_spaces.slug = LOWER(users.soeid) || '-personal'
  );

COMMIT;
