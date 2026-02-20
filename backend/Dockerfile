FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi[standard]>=0.115" \
    "sqlalchemy[asyncio]>=2.0" \
    "asyncpg>=0.29" \
    "alembic>=1.13" \
    "bcrypt>=4.1" \
    "python-jose[cryptography]>=3.3" \
    "pydantic[email]>=2.6" \
    "python-multipart>=0.0.9" \
    "uvicorn[standard]>=0.29"

COPY . .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
