# PostgreSQL Setup

This describes how to prepare a PostgreSQL database for the FastAPI backend (useful when deploying to ECS/RDS or running locally with `psql`).

## 1. Create roles and database via `psql`

```bash
psql -h <host> -U <admin_user>
CREATE DATABASE fax_dev;
CREATE USER fax_user WITH PASSWORD 'change-me';
GRANT ALL PRIVILEGES ON DATABASE fax_dev TO fax_user;
```

If you use Amazon RDS, you can run the same statements from the master user (or via the AWS console) and ensure the security group permits backend connections.

## 2. Configure the backend

Set the `FAX_DB_URL` environment variable before starting FastAPI. Example pointing at RDS/PostgreSQL:

```
export FAX_DB_URL="postgresql://fax_user:change-me@db.example.com:5432/fax_dev"
```

On Windows (PowerShell):

```powershell
$env:FAX_DB_URL = "postgresql://fax_user:change-me@db.example.com:5432/fax_dev"
```

The backend automatically calls `SQLModel.metadata.create_all(engine)` so the tables defined in `backend/app/models.py` are created the first time the service starts. Running `python -m backend.app.main` after setting `FAX_DB_URL` will also create the schema.

## 3. Verify and inspect

- Use `psql` to confirm the tables exist:
  ```bash
  psql "<connection>" -c "\dt schema_name.*"
  ```
- To run migrations later, point `FAX_DB_URL` at the new host/port and restart the FastAPI process (SQLModel handles schema changes via `metadata.create_all`).

## 4. Production readiness

- Consider enabling automated backups/snapshots on your RDS instance.
- Keep credentials out of source control; use AWS Secrets Manager or environment variables via your orchestrator.
