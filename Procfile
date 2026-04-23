web: gunicorn socialnetworking.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120
worker: celery -A socialnetworking worker --loglevel=info --concurrency 2
