FROM python:3.9

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-venv \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set up Python virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies with specific versions
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p images templates

# Expose port 3636 for Flask
EXPOSE 3636

# Command to run the application
CMD ["python", "app.py"]