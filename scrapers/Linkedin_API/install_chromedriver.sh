#!/bin/bash

# Install ChromeDriver matching the Chrome version
# This runs at container startup, not build time

CHROMEDRIVER_PATH="/usr/local/bin/chromedriver"

# Check if chromedriver already exists
if [ -f "$CHROMEDRIVER_PATH" ]; then
    echo "✅ ChromeDriver already installed at $CHROMEDRIVER_PATH"
    chromedriver --version
    exit 0
fi

echo "📥 Installing ChromeDriver..."

# Get Chrome version
CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+\.\d+')
CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d. -f1)

echo "Chrome version: $CHROME_VERSION (major: $CHROME_MAJOR)"

# Download matching ChromeDriver
DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}")

if [ -z "$DRIVER_VERSION" ]; then
    echo "❌ Failed to get ChromeDriver version"
    exit 1
fi

echo "Downloading ChromeDriver $DRIVER_VERSION..."

DOWNLOAD_URL="https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip"

# Download and install
wget -q "$DOWNLOAD_URL" -O /tmp/chromedriver.zip && \
unzip -q /tmp/chromedriver.zip -d /tmp/ && \
mv /tmp/chromedriver-linux64/chromedriver "$CHROMEDRIVER_PATH" && \
chmod +x "$CHROMEDRIVER_PATH" && \
rm -rf /tmp/chromedriver*

if [ -f "$CHROMEDRIVER_PATH" ]; then
    echo "✅ ChromeDriver installed successfully"
    chromedriver --version
else
    echo "❌ ChromeDriver installation failed"
    exit 1
fi
