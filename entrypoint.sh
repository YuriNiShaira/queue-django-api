#!/bin/bash

# Exit immediately if a command fails
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Starting Daphne server..."
exec "$@"