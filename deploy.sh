#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/srv/daillyfresh"
VENV_DIR="/srv/daillyfresh/.venv"
BRANCH="${1:-deploy}"
SERVICE_NAME="daillyfresh"
HEALTHCHECK_URL="http://127.0.0.1:8000/healthz/"

cd "$APP_DIR"

git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    sudo systemctl kill -s HUP --kill-who=main "$SERVICE_NAME"
else
    sudo systemctl start "$SERVICE_NAME"
fi

curl --fail --silent --show-error "$HEALTHCHECK_URL" > /dev/null

sudo systemctl status "$SERVICE_NAME" --no-pager
