FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ /app/

# Create directories
RUN mkdir -p /app/data /app/loot

EXPOSE 5000

CMD ["python", "main.py"]
