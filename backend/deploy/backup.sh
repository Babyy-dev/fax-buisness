#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/fax}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/fax}"
DB_PATH="${DB_PATH:-$APP_DIR/backend/data/fax.db}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
INCLUDE_UPLOADS="${INCLUDE_UPLOADS:-1}"
INCLUDE_GENERATED="${INCLUDE_GENERATED:-1}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp_dir="$(mktemp -d)"
work_dir="$tmp_dir/fax-backup-$timestamp"
archive_path="$BACKUP_DIR/fax-backup-$timestamp.tar.gz"
sha_path="$archive_path.sha256"

mkdir -p "$work_dir"
mkdir -p "$BACKUP_DIR"

if [[ -f "$DB_PATH" ]]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB_PATH" ".backup '$work_dir/fax.db'"
  else
    cp "$DB_PATH" "$work_dir/fax.db"
  fi
fi

if [[ "$INCLUDE_UPLOADS" == "1" && -d "$APP_DIR/backend/uploads" ]]; then
  cp -a "$APP_DIR/backend/uploads" "$work_dir/uploads"
fi

if [[ "$INCLUDE_GENERATED" == "1" && -d "$APP_DIR/backend/generated" ]]; then
  cp -a "$APP_DIR/backend/generated" "$work_dir/generated"
fi

if [[ -d "$APP_DIR/backend/logs" ]]; then
  mkdir -p "$work_dir/logs"
  cp -a "$APP_DIR/backend/logs" "$work_dir/logs"
fi

tar -C "$tmp_dir" -czf "$archive_path" "fax-backup-$timestamp"
sha256sum "$archive_path" > "$sha_path"

find "$BACKUP_DIR" -type f -name "fax-backup-*.tar.gz" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -type f -name "fax-backup-*.tar.gz.sha256" -mtime +"$RETENTION_DAYS" -delete

rm -rf "$tmp_dir"
echo "Backup created: $archive_path"
echo "Checksum file: $sha_path"

