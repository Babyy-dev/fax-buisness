# Deployment Hardening and Backups

This directory contains Linux deployment assets for running the backend as a hardened service and backing up SQLite data.

## Files
- `fax-backend.service.template`: hardened systemd service for FastAPI
- `fax-backup.service.template`: one-shot backup service
- `fax-backup.timer`: daily scheduler for backups
- `install-systemd.sh`: installs and enables systemd units
- `backup.sh`: creates timestamped backup archives
- `restore.sh`: restores DB/uploads/generated from an archive
- `backup.env.example`: backup configuration template

## Install on EC2 (Ubuntu)
Run as root:

```bash
sudo bash /home/ubuntu/<repo>/backend/deploy/install-systemd.sh --app-dir /home/ubuntu/<repo> --user ubuntu
```

## Service status
```bash
sudo systemctl status fax-backend
sudo systemctl status fax-backup.timer
```

## Manual backup
```bash
bash /home/ubuntu/<repo>/backend/deploy/backup.sh
```

## Manual restore
Stop backend first:
```bash
sudo systemctl stop fax-backend
bash /home/ubuntu/<repo>/backend/deploy/restore.sh /var/backups/fax/fax-backup-YYYYMMDDTHHMMSSZ.tar.gz /home/ubuntu/<repo>
sudo systemctl start fax-backend
```

## Daily operations quick reference
See `backend/deploy/OPS_CHEATSHEET.md` for start/stop, logs, health checks, backup, restore, and update commands.
