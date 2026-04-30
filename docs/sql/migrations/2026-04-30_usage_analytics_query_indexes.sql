-- Additional time-window indexes for usage analytics read aggregation.
-- Safe to rerun. Existing indexes are ignored.

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_usage_events_created ON TB_TA_PM_USAGE_EVENTS (occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_performance_samples_created ON TB_TA_PM_PERFORMANCE_SAMPLES (occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/
