-- Usage analytics tables and indexes for internal telemetry.
-- Safe to rerun. Existing tables/indexes are ignored.

BEGIN
  EXECUTE IMMEDIATE '
    CREATE TABLE TB_TA_PM_USAGE_EVENTS (
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
      FOREIGN KEY (space_id) REFERENCES TB_TA_PM_SPACES (space_id)
    )
  ';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE '
    CREATE TABLE TB_TA_PM_PERFORMANCE_SAMPLES (
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
      FOREIGN KEY (space_id) REFERENCES TB_TA_PM_SPACES (space_id)
    )
  ';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_usage_events_feature_action_created ON TB_TA_PM_USAGE_EVENTS (feature_key, action_key, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_usage_events_session_created ON TB_TA_PM_USAGE_EVENTS (session_id, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_usage_events_space_created ON TB_TA_PM_USAGE_EVENTS (space_id, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_usage_events_user_created ON TB_TA_PM_USAGE_EVENTS (user_id, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_usage_events_view_created ON TB_TA_PM_USAGE_EVENTS (view_key, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_performance_samples_kind_created ON TB_TA_PM_PERFORMANCE_SAMPLES (sample_kind, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_performance_samples_session_created ON TB_TA_PM_PERFORMANCE_SAMPLES (session_id, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_performance_samples_space_created ON TB_TA_PM_PERFORMANCE_SAMPLES (space_id, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_performance_samples_user_created ON TB_TA_PM_PERFORMANCE_SAMPLES (user_id, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_performance_samples_view_created ON TB_TA_PM_PERFORMANCE_SAMPLES (view_key, occurred_at)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
/
