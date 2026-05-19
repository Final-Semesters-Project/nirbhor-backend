### create virtual environment
```
python3 -m venv .venv
```

## Activate Virtual Environment (venv)
```
source .venv/bin/activate
```

# Packages/Libraries
1. FastAPI(standard)
2. SQLAlchemy[asyncio] (for async db access)
3. Asyncpg (async postgres driver for asyncio)
4. Psycopg2 (sync postgres driver for alembic migrations)
5. GeoAlchemy2
6. Alembic (not installed yet)
7. firebase-admin (not installed yet)
8. apscheduler
9. passlib-bcrypt & argon2(for password hashing)
10. python-jose[cryptography] (for JWT tokens)
11. cloudinary (for image store)
12. Loguru (logging)
13. cachetools (for TTL caching)
14. anthropic or openai (for AI review summary)
15. gunicorn (for production)
