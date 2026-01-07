FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System deps + Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    gnupg \
    unzip \
    ca-certificates \
    fonts-liberation \
    # مرورگر و درایور
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

EXPOSE 5001

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
