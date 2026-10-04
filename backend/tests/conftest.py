import pytest

from app.core.rate_limit import reset_for_tests
from app.db.session import engine


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests():
    """pytest-asyncio gives each test function its own event loop by
    default, but app.db.session.engine is a module-level singleton whose
    asyncpg connection pool gets bound to whichever loop first used it.
    Reusing it from a later test's (different) loop raises
    'RuntimeError: Event loop is closed' from asyncpg's cleanup code.
    Disposing the pool after every test forces the next test that touches
    the DB to open fresh connections against its own loop.
    """
    reset_for_tests()
    yield
    await engine.dispose()
