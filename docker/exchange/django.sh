#!/bin/bash

if [[ $DEV == True ]]; then
  python manage.py runserver 0.0.0.0:8000
else
  bash -c "DEBUG=False waitress-serve --port=8000 exchange.wsgi:application"
fi
