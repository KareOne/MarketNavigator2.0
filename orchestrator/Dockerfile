FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 8010

# Run the server
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8010"]
