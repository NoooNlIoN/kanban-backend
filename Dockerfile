FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.lock README.md pyproject.toml .
RUN pip install --no-cache-dir -r requirements.lock

# Add asyncpg and redis dependencies
RUN pip install --no-cache-dir asyncpg websockets

# Copy project
COPY . .

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"] 