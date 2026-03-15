-- Oracle migration: add GitHub repo traceability columns to solutions and subcomponents.

ALTER TABLE "TB_TA_PM_SOLUTIONS"
ADD ("GITHUB_REPO_URL" VARCHAR2(1024 CHAR));

ALTER TABLE "TB_TA_PM_SUBCOMPONENTS"
ADD ("GITHUB_REPO_URL" VARCHAR2(1024 CHAR));
