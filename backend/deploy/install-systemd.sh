#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/ubuntu/fax"
SERVICE_USER="ubuntu"
ENABLE_BACKUP_TIMER="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-dir)
      APP_DIR="$2"
      shift 2
      ;;
    --user)
      SERVICE_USER="$2"
      shift 2
      ;;
    --no-backup-timer)
      ENABLE_BACKUP_TIMER="0"
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--app-dir /home/ubuntu/fax] [--user ubuntu] [--no-backup-timer]"
      exit 1
      ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

BACKEND_TEMPLATE="$APP_DIR/backend/deploy/fax-backend.service.template"
BACKUP_TEMPLATE="$APP_DIR/backend/deploy/fax-backup.service.template"
TIMER_TEMPLATE="$APP_DIR/backend/deploy/fax-backup.timer"

for file in "$BACKEND_TEMPLATE" "$BACKUP_TEMPLATE" "$TIMER_TEMPLATE"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing template: $file"
    exit 1
  fi
done

sed \
  -e "s|__APP_DIR__|$APP_DIR|g" \
  -e "s|__SERVICE_USER__|$SERVICE_USER|g" \
  "$BACKEND_TEMPLATE" > /etc/systemd/system/fax-backend.service

sed \
  -e "s|__APP_DIR__|$APP_DIR|g" \
  -e "s|__SERVICE_USER__|$SERVICE_USER|g" \
  "$BACKUP_TEMPLATE" > /etc/systemd/system/fax-backup.service

cp "$TIMER_TEMPLATE" /etc/systemd/system/fax-backup.timer

install -d -m 750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_DIR/backend/logs"
install -d -m 750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_DIR/backend/data"
install -d -m 750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_DIR/backend/uploads"
install -d -m 750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_DIR/backend/generated"

chmod +x "$APP_DIR/backend/deploy/backup.sh"
chmod +x "$APP_DIR/backend/deploy/restore.sh"

if [[ ! -f "$APP_DIR/backend/deploy/backup.env" && -f "$APP_DIR/backend/deploy/backup.env.example" ]]; then
  cp "$APP_DIR/backend/deploy/backup.env.example" "$APP_DIR/backend/deploy/backup.env"
  chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/backend/deploy/backup.env"
fi

systemctl daemon-reload
systemctl enable fax-backend.service
systemctl restart fax-backend.service

if [[ "$ENABLE_BACKUP_TIMER" == "1" ]]; then
  systemctl enable fax-backup.timer
  systemctl restart fax-backup.timer
fi

echo "Installed: fax-backend.service"
if [[ "$ENABLE_BACKUP_TIMER" == "1" ]]; then
  echo "Installed: fax-backup.service + fax-backup.timer"
fi

