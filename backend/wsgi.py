"""Production WSGI entrypoint.

Used by gunicorn:
    gunicorn -c gunicorn.conf.py wsgi:app
"""

from app.server import create_app

app = create_app()
