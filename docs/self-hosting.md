# Self-Hosting OpenBuild

## Requirements

- Docker and Docker Compose
- 2 CPU cores, 4GB RAM minimum (8GB recommended for large drawing sets)
- 50GB disk space (drawings are large files)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/openbuild/openbuild.git
cd openbuild

# Start all services
docker compose up -d

# The application is available at:
# - Frontend: http://localhost:5173
# - API: http://localhost:3000
# - MinIO Console: http://localhost:9001 (admin: openbuild/openbuild_dev)
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | 5173 | React web application |
| API | 3000 | Rust backend server |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Cache and sessions |
| MinIO | 9000/9001 | File storage (drawings) |
| Meilisearch | 7700 | Full-text search |

## Configuration

Environment variables for the API server:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgres://openbuild:openbuild_dev@localhost:5432/openbuild` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `S3_ENDPOINT` | `http://localhost:9000` | S3-compatible storage endpoint |
| `S3_BUCKET` | `openbuild` | Storage bucket name |
| `S3_ACCESS_KEY` | `openbuild` | S3 access key |
| `S3_SECRET_KEY` | `openbuild_dev` | S3 secret key |
| `JWT_SECRET` | (required in prod) | Secret for JWT token signing |
| `LISTEN_ADDR` | `0.0.0.0:3000` | API listen address |

## Backups

### Database
```bash
# Backup
docker compose exec postgres pg_dump -U openbuild openbuild > backup.sql

# Restore
docker compose exec -i postgres psql -U openbuild openbuild < backup.sql
```

### File Storage
MinIO data is stored in a Docker volume. Back up the volume or configure MinIO replication for production use.

## Upgrading

```bash
git pull
docker compose pull
docker compose up -d
```

Database migrations run automatically on API startup.
