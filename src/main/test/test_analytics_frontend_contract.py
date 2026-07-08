from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYTICS_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "analytics.js"


def test_analytics_dashboard_distinguishes_load_metric_sources():
    route_text = ANALYTICS_ROUTE.read_text(encoding="utf-8")

    assert "Combined Median / P95 Load" in route_text
    assert "Page Load Median / P95" in route_text
    assert "Route Transition Median / P95" in route_text
    assert "performanceSummary.navigation_median_load_ms" in route_text
    assert "performanceSummary.route_transition_median_load_ms" in route_text


def test_analytics_dashboard_defaults_to_seven_day_window():
    route_text = ANALYTICS_ROUTE.read_text(encoding="utf-8")

    assert "days: 7" in route_text
    assert 'analyticsState.days = Number(target.value) || 7;' in route_text
