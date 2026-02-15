# Backend Ops Cheat Sheet (EC2)

Use this after `install-systemd.sh` is done.

Assumptions:
- Service name: `fax-backend`
- Backup timer: `fax-backup.timer`
- Repo path: `/home/ubuntu/fax-buisness`

## 1) Service control

```bash
# Start / stop / restart
sudo systemctl start fax-backend
sudo systemctl stop fax-backend
sudo systemctl restart fax-backend

# Enable on boot
sudo systemctl enable fax-backend

# Check status
sudo systemctl status fax-backend --no-pager -l
```

## 2) Logs and troubleshooting

```bash
# Live logs
sudo journalctl -u fax-backend -f

# Last 200 lines
sudo journalctl -u fax-backend -n 200 --no-pager

# Logs since today
sudo journalctl -u fax-backend --since today --no-pager
```

## 3) Health checks

```bash
# Local EC2 check
curl -sS http://127.0.0.1:8000/api/health

# Public check (if exposed)
curl -sS http://<EC2_PUBLIC_IP>/api/health
```

## 4) Backup operations

```bash
# Check timer/service
sudo systemctl status fax-backup.timer --no-pager -l
sudo systemctl list-timers --all | grep fax-backup

# Run one backup now
sudo systemctl start fax-backup.service

# Or run script directly
bash /home/ubuntu/fax-buisness/backend/deploy/backup.sh

# List backup files
ls -lh /var/backups/fax
```

## 5) Restore (disaster recovery)

```bash
# 1) Stop backend
sudo systemctl stop fax-backend

# 2) Restore from one archive
bash /home/ubuntu/fax-buisness/backend/deploy/restore.sh \
  /var/backups/fax/fax-backup-YYYYMMDDTHHMMSSZ.tar.gz \
  /home/ubuntu/fax-buisness

# 3) Start backend
sudo systemctl start fax-backend

# 4) Verify
curl -sS http://127.0.0.1:8000/api/health
```

## 6) Deploy/update workflow

```bash
cd /home/ubuntu/fax-buisness
git pull

# if dependencies changed:
cd backend
source .venv/bin/activate
pip install -r requirements.txt

# restart service
sudo systemctl restart fax-backend
sudo systemctl status fax-backend --no-pager -l
```

## 7) Common quick fixes

```bash
# Bad .env values or path issues
sudo systemctl restart fax-backend
sudo journalctl -u fax-backend -n 100 --no-pager

# Permission issues on app data folders
sudo chown -R ubuntu:ubuntu /home/ubuntu/fax-buisness/backend/data

# Check if port 8000 is listening locally
ss -tulpen | grep 8000
```

