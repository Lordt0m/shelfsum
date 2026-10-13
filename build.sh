#!/usr/bin/env bash
set -euo pipefail

python -m pip install -r requirements.txt
npm ci
npm run build
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_demo
