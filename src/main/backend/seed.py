from backend.app.db.db import init_db


def main() -> None:
    """Initialize DB schema and run seed routines."""
    init_db(run_seed=True, create_schema=True)


if __name__ == "__main__":
    main()
