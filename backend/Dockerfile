# Use an official Python image
FROM python:3.12-slim

# Install system dependencies (psycopg, build-essential for compiled deps)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Poetry (or pip) - using pip for simplicity
COPY pyproject.toml poetry.lock* /app/
RUN pip install --upgrade pip && pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Copy source code
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
