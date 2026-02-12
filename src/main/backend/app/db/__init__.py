from importlib import import_module

__all__ = ["engine", "SessionLocal", "get_session", "init_db"]


def __getattr__(name: str):
    if name in __all__:
        module = import_module(".db", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
