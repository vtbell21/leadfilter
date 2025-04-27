#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
# Removed migrate step; run migrations as a postdeploy or release command 