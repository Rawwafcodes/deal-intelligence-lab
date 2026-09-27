# Task 19.6 (M19): one image for both hosted services (D25: Railway).
#   web service:    default command (python server.py)
#   worker service: start command "python worker.py"
# Configuration comes only from the environment - see .env.example.

# --- 1. Build the React app (the Clerk publishable key is public and is
#        baked in at build time; leave it empty for a local-style build).
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_CLERK_PUBLISHABLE_KEY=""
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}
RUN npm run build

# --- 2. Python runtime.
FROM python:3.10-slim
# Secure by default: hosted sign-in (Clerk). The local dev identity mode
# would give every visitor the admin identity, and server.py refuses to run
# it on a non-loopback address anyway.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEAL_LAB_HOST=0.0.0.0 \
    DEAL_LAB_AUTH_MODE=clerk \
    DEAL_LAB_DATA_DIR=/data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
# Legacy static pages still served by server.py, then the fresh React build
# over the top (the same copy scripts/build-frontend-into-static.sh does).
COPY static/ ./static/
COPY --from=frontend /app/frontend/dist/index.html ./static/index.html
COPY --from=frontend /app/frontend/dist/favicon.svg ./static/favicon.svg
COPY --from=frontend /app/frontend/dist/icons.svg ./static/icons.svg
RUN rm -rf ./static/assets
COPY --from=frontend /app/frontend/dist/assets ./static/assets
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
USER app
EXPOSE 8080
CMD ["python", "server.py"]
