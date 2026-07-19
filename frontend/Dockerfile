# Build context is the repo ROOT (see docker-compose.yml: context: ., 
# dockerfile: frontend/Dockerfile) so this can reach ../docker/nginx.conf -
# every COPY below is relative to the repo root, not this file's location.

# --- Build stage --------------------------------------------------------
FROM node:22-slim AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/. .
RUN npm run build

# --- Runtime stage: static files served by nginx, which also reverse-
# proxies /api to the backend so the browser only ever talks to one origin --
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1
