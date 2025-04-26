#!/bin/bash

# Collect static files
python manage.py collectstatic --noinput

# Deploy to Elastic Beanstalk
eb deploy 