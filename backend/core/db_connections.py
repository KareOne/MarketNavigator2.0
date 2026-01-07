"""
Database connection management utilities.
Helps prevent connection pool exhaustion in long-running tasks and async code.
"""
import logging
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def ensure_connection_closed():
    """
    Context manager that ensures database connections are closed after use.
    Use this for operations that don't need persistent connections.
    
    Usage:
        with ensure_connection_closed():
            MyModel.objects.create(...)
    """
    try:
        yield
    finally:
        from django.db import connection
        connection.close()


def close_db_connection():
    """
    Explicitly close the database connection.
    Call this after completing a batch of DB operations in long-running tasks.
    """
    from django.db import connection
    connection.close()


def close_old_db_connections():
    """
    Close old database connections.
    Use at the start of Celery tasks or periodically in long-running operations.
    """
    from django.db import close_old_connections
    close_old_connections()


def with_connection_cleanup(func):
    """
    Decorator that closes DB connections before and after the function.
    Useful for Celery tasks and long-running operations.
    
    Usage:
        @with_connection_cleanup
        def my_task():
            # ... DB operations ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from django.db import connection, close_old_connections
        # Close stale connections before starting
        close_old_connections()
        try:
            return func(*args, **kwargs)
        finally:
            # Close connection after completion
            connection.close()
    return wrapper


def release_connection_on_error(func):
    """
    Decorator that ensures connection is released even on errors.
    Prevents connection leaks in exception scenarios.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from django.db import connection
        try:
            return func(*args, **kwargs)
        except Exception:
            connection.close()
            raise
    return wrapper


class ConnectionGuard:
    """
    Context manager for managing database connections in long-running operations.
    Periodically closes and reopens connections to prevent pool exhaustion.
    
    Usage:
        guard = ConnectionGuard(operations_per_cleanup=50)
        for item in large_list:
            guard.tick()  # Closes connection every 50 operations
            process(item)
        guard.cleanup()  # Final cleanup
    """
    
    def __init__(self, operations_per_cleanup: int = 50):
        self.operations_per_cleanup = operations_per_cleanup
        self.operation_count = 0
    
    def tick(self):
        """Call after each operation. Triggers cleanup when threshold is reached."""
        self.operation_count += 1
        if self.operation_count >= self.operations_per_cleanup:
            self.cleanup()
            self.operation_count = 0
    
    def cleanup(self):
        """Explicitly close the database connection."""
        from django.db import connection
        connection.close()
        logger.debug(f"ConnectionGuard: Closed connection after {self.operation_count} operations")
    
    def __enter__(self):
        from django.db import close_old_connections
        close_old_connections()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False

