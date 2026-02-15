#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-archive.tar.gz> [app_dir]"
  exit 1
fi

archive_path="$1"
APP_DIR="${2:-${APP_DIR:-/home/ubuntu/fax}}"
BACKEND_DIR="$APP_DIR/backend"
DB_PATH="$BACKEND_DIR/data/fax.db"

if [[ ! -f "$archive_path" ]]; then
  echo "Archive not found: $archive_path"
  exit 1
fi

checksum_path="$archive_path.sha256"
if [[ -f "$checksum_path" ]]; then
  sha256sum -c "$checksum_path"
fi

tmp_dir="$(mktemp -d)"
tar -C "$tmp_dir" -xzf "$archive_path"
payload_dir="$(find "$tmp_dir" -maxdepth 1 -type d -name 'fax-backup-*' | head -n 1)"

if [[ -z "${payload_dir:-}" ]]; then
  echo "Invalid backup archive format."
  rm -rf "$tmp_dir"
  exit 1
fi

mkdir -p "$BACKEND_DIR/data" "$BACKEND_DIR/uploads" "$BACKEND_DIR/generated"

if [[ -f "$payload_dir/fax.db" ]]; then
  cp "$payload_dir/fax.db" "$DB_PATH"
fi

if [[ -d "$payload_dir/uploads" ]]; then
  rm -rf "$BACKEND_DIR/uploads"
  cp -a "$payload_dir/uploads" "$BACKEND_DIR/uploads"
fi

if [[ -d "$payload_dir/generated" ]]; then
  rm -rf "$BACKEND_DIR/generated"
  cp -a "$payload_dir/generated" "$BACKEND_DIR/generated"
fi

rm -rf "$tmp_dir"
echo "Restore completed into: $BACKEND_DIR"

