# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed by Playwright and Chromium, and Tcl/Tk for customtkinter
# List from Playwright documentation for Debian/Ubuntu, plus tk-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    tk-dev \
    # Clean up apt cache
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file from the app_files directory into the container at /app
COPY app_files/requirements.txt /app/

# Install Python dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium in this case)
# --with-deps might be redundant here as system deps are handled by apt-get, but it's harmless.
RUN playwright install --with-deps chromium

# Copy configuration and credential files from the project root to /app in the container
COPY .env /app/
COPY credentials.json /app/
COPY token.pickle /app/

# Copy the entire app_files directory content into the container at /app
# This will include app.py, automation_runner.py, templates/, static/, etc.
COPY app_files/ /app/

# The app will be run from the /app directory, where app.py is now located.
# Waitress by default serves on port 8080 if PORT env var isn't set.
# Render sets the PORT environment variable, which Waitress should pick up.
# Flask's default is 5000, but your app.py uses os.environ.get("PORT", 10000)
# and then Waitress serves on that port. Render will route external port 80/443 to this internal PORT.
CMD ["python", "app.py"] 