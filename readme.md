### create virtual environment
```
Linux: python3 -m venv .venv
```
- If you are facing problems to install libraries using pip install even after activating venv, getting error like "externally-managed-environments", then do the following:
 - 1. Delete the corrupted venv: ```rm -rf .venv```
 - 2. Ensure you have python3-venv installed: 
        ```
            sudo apt update
            sudo apt install python3-venv python3-full
        ```
 - 3. sudo apt install python3-venv python3-full
 - 4. Create the venv: ```python3 -m venv .venv```
 - 5. Activate
 - 6. Verify the link: ```which pip```

## Activate Virtual Environment (venv)
```
Linux: source .venv/bin/activate
Windows: .venv\Scripts\activate  
Gitbash terminal: source .venv/Scripts/activate
```

## Install libraries from requirements.txt
```
pip install -r requirements.txt
```

## Save libraries to requirements.txt
```
pip freeze > requirements.txt
```

- Add ENV variables to `.env` and firebase credentials to `serviceAccountKey.json`

## Run server with docker
```
docker compose -f docker-compose.dev.yml up --build
```

## Database migrations
- Generate alembic migrations
```
docker exec -it nirbhor_backend_dev alembic revision --autogenerate -m "message"  
```

- Apply migrations
```
docker exec -it nirbhor_backend_dev alembic upgrade head  
```


## Stop Container
```
Keeps DB data: docker compose -f docker-compose.dev.yml down OR ctrl+c

Deletes DB data: docker compose -f docker-compose.dev.yml down -v  
```


# Packages/Libraries
1. FastAPI(standard)
2. SQLAlchemy[asyncio] (for async db access)
3. Asyncpg (async postgres driver for asyncio)
4. Psycopg2 (sync postgres driver for alembic migrations)
5. GeoAlchemy2
6. Alembic
7. firebase-admin (not installed yet)
8. apscheduler
9. passlib-bcrypt & argon2(for password hashing)
10. python-jose[cryptography] (for JWT tokens)
11. cloudinary (for image store)
12. Loguru (logging)
13. cachetools (for TTL caching)
14. anthropic or openai (for AI review summary)
15. gunicorn (for production)
