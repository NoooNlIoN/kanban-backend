FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# Add asyncpg and redis dependencies
RUN pip install --no-cache-dir asyncpg redis websockets

# Copy project
COPY . .

# Run the application
CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"] 