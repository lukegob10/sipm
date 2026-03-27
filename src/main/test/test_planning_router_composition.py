from backend.app.routes.planning import router as planning_router


def test_planning_router_exposes_expected_paths():
    route_paths = {route.path for route in planning_router.routes}

    assert {
        "/resource-allocations",
        "/resource-allocations/{allocation_id}",
        "/resource-allocations/summary",
        "/planning/windows",
        "/planning/windows/{window_id}",
        "/planning/work-allocation/teams",
        "/planning/work-allocation/teams/{team_id}",
        "/planning/work-allocation/people",
        "/planning/work-allocation/people/{person_id}",
        "/planning/work-allocation/tasks",
        "/planning/work-allocation/tasks/{task_id}",
        "/planning/work-allocation/allocations",
        "/planning/work-allocation/allocations/{allocation_id}",
        "/planning/work-allocation/report.pdf",
    }.issubset(route_paths)
