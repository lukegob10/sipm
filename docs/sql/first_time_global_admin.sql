-- First-time SIPM global admin bootstrap.
--
-- Purpose:
--   Promote an existing user to global_admin after the canonical schema has
--   been created and the first user row already exists.
--
-- Operator note:
--   Change the SOEID literal if a different first admin is required.

UPDATE "TB_TA_PM_USERS"
SET
  role = 'global_admin',
  is_active = 1,
  force_password_reset = 0,
  failed_attempts = 0,
  locked_until = NULL,
  updated_at = SYSDATE
WHERE LOWER(soeid) = LOWER('LG22254');

COMMIT;

SELECT user_id, soeid, email, display_name, role, is_active
FROM "TB_TA_PM_USERS"
WHERE LOWER(soeid) = LOWER('LG22254');
