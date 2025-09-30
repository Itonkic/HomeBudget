# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for OpenCV
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of the project
COPY . .

# Flask configuration
ENV FLASK_APP=app.app:app
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000
ENV FLASK_ENV=development

# Postgres config
ENV POSTGRES_HOST=db
ENV POSTGRES_DB=home_budget
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
ENV JWT_SECRET_KEY=super-secret

EXPOSE 5000

CMD ["flask", "run"]
