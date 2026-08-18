FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Add Chrome repository and install
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver (version compatible with installed Chrome)
RUN CHROME_VERSION=$(google-chrome --version | grep -oE "[0-9]+\.[0-9]+\.[0-9]+") \
    && CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d. -f1) \
    && echo "Chrome version: $CHROME_VERSION (major: $CHROME_MAJOR)" \
    && DRIVER_URL="https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}" \
    && DRIVER_VERSION=$(wget -qO- $DRIVER_URL) \
    && echo "ChromeDriver version: $DRIVER_VERSION" \
    && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver* \
    && chromedriver --version

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY selenium-service.py .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Expose port
EXPOSE 10000

# Run with gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --worker-class sync "selenium-service:app"
