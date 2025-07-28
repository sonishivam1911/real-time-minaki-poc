FROM python:3.9

WORKDIR /app

# Add system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . ./api

# Set Python path so imports work
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Now api.main:app will work because /app/api/main.py exists
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-80}