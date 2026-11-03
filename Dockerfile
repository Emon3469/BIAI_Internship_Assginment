# ==============================================================================
# Stage 1: Build the Next.js static frontend
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app

# Install dependencies using clean lockfile
COPY package.json package-lock.json* ./
RUN npm ci || npm install

# Copy frontend configuration and source files
COPY app ./app
COPY postcss.config.mjs tailwind.config.ts tsconfig.json next.config.mjs ./

# Disable Next.js telemetry and export static build to /app/out
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ==============================================================================
# Stage 2: Python Backend & Unified Production Server
# ==============================================================================
FROM python:3.12-slim AS runner

# Ensure logs flush immediately and pyc files are skipped
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and dataset directories
COPY src ./src
COPY task1-crm ./task1-crm
COPY task2-corporate-leads ./task2-corporate-leads
COPY main.py demo.py ./

# Copy exported frontend assets from Stage 1 into /app/out
COPY --from=frontend-builder /app/out ./out

# Default port (Railway and Render provide $PORT dynamically at runtime)
EXPOSE 8000

# Health check endpoint for cloud platforms
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

# Launch the unified application
CMD ["python", "main.py"]
