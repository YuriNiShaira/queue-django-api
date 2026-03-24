# Use official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --default-timeout=100 --upgrade pip && pip install --default-timeout=100 -r requirements.txt

# Copy project
COPY . /app/

# Copy entrypoint script and grant execution permissions
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose the port Daphne will run on
EXPOSE 8000


# Set the entrypoint to our script
ENTRYPOINT ["/app/entrypoint.sh"]

# Collect static files (optional, depending on your setup)
# RUN python manage.py collectstatic --noinput

# Start the Daphne server
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "backend.asgi:application"]
