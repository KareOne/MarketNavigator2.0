"""
Celery configuration for MarketNavigator v2.
Includes robust database connection management to prevent pool exhaustion.
"""

import os
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, worker_process_init

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('marketnavigator')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Initialize worker process with fresh database connections.
    This is called when a worker process starts.
    """
    from django.db import connections
    for conn in connections.all():
        conn.close()


@task_prerun.connect
def close_old_connections_before_task(**kwargs):
    """
    Close old/stale database connections before starting a task.
    This ensures we don't use connections that may have timed out.
    """
    from django.db import close_old_connections
    close_old_connections()


@task_postrun.connect
def close_db_connections_after_task(**kwargs):
    """
    Close database connections after each task completes.
    This prevents connection pool exhaustion in Celery workers.
    """
    from django.db import connection
    connection.close()


@task_failure.connect
def close_db_connections_on_failure(**kwargs):
    """
    Ensure connections are closed even when tasks fail.
    Prevents connection leaks in exception scenarios.
    """
    from django.db import connection
    connection.close()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

