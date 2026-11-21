# Nirbhor Backend

Backend service for Nirbhor, built with FastAPI and PostgreSQL/PostGIS.

## Development setup

### 1. Create a Python virtual environment

On Linux:

```bash
python3 -m venv .venv
```

If `pip install` fails after activating the environment with an error such as
`externally-managed-environments`, recreate the virtual environment:

1. Remove the corrupted virtual environment:

   ```bash
   rm -rf .venv
   ```

2. Update the package index and install the Python virtual-environment packages:

   ```bash
   sudo apt update
   sudo apt install python3-venv python3-full
   ```

3. Create the virtual environment again:

   ```bash
   python3 -m venv .venv
   ```

4. Activate it using the instructions below.
5. Verify that `pip` points to the environment using `which pip`.

### 2. Activate the virtual environment

```bash
# Linux
source .venv/bin/activate

# Windows Command Prompt
.venv\Scripts\activate

# Git Bash
source .venv/Scripts/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

To update `requirements.txt` with the packages installed in the active
environment:

```bash
pip freeze > requirements.txt
```

### 4. Configure environment variables and Firebase

Add the required environment variables to a `.env` file. You can use
`.env.example` as a reference. Add the Firebase credentials to
`serviceAccountKey.json`.

Keep credentials and other secrets private; do not commit them to the
repository.

## Run the development server with Docker

With Docker and the Docker Compose plugin installed, start the development
services from the repository root:

```bash
docker compose -f docker-compose.dev.yml up --build
```

The development Compose setup starts the backend, PostgreSQL/PostGIS database,
and pgAdmin. The backend is available at `http://localhost:8000`.

## Database migrations

Generate an Alembic migration from model changes:

```bash
docker exec -it nirbhor_backend_dev alembic revision --autogenerate -m "message"
```

Apply pending migrations:

```bash
docker exec -it nirbhor_backend_dev alembic upgrade head
```

## Stop the containers

Stop the services while keeping the database data:

```bash
docker compose -f docker-compose.dev.yml down
```

You can also stop the running services with `Ctrl+C`.

Stop the services and delete the database volume and its data:

```bash
docker compose -f docker-compose.dev.yml down -v
```

## Packages and libraries

The project uses the following packages and libraries:

1. FastAPI (standard) for the API.
2. SQLAlchemy with asyncio for asynchronous database access.
3. Asyncpg as the asynchronous PostgreSQL driver.
4. Psycopg2 as the synchronous PostgreSQL driver used by Alembic migrations.
5. GeoAlchemy2 for spatial database support.
6. Alembic for database migrations.
7. `firebase-admin` for Firebase services.
8. APScheduler for scheduled jobs.
9. Passlib with bcrypt and Argon2 for password hashing.
10. `python-jose[cryptography]` for JWT tokens.
11. Cloudinary for image storage.
12. Loguru for logging.
13. Cachetools for TTL caching.
14. Anthropic or OpenAI libraries for AI review summaries.
15. Gunicorn for production serving.

See [`requirements.txt`](requirements.txt) for the dependency versions currently
used by the project.
