# docker/

Shared Docker resources that don't belong to a single service:

- **nginx.conf** - the frontend container's reverse-proxy config (serves
  the built React app, proxies `/api/*` to the backend). Referenced by
  `frontend/Dockerfile`, which is why the frontend image is built with the
  repo root as its context (see `docker-compose.yml`) rather than just
  `./frontend` - it needs to reach this file.
- **docker-compose.override.example.yml** - a starting point for local
  development overrides (hot-reload volume mounts, exposed debug ports).
  Copy to `docker-compose.override.yml` in the repo root (Compose picks
  that filename up automatically alongside `docker-compose.yml`) and
  customize - it's gitignored so your personal overrides don't get committed.

Each actual service's own `Dockerfile` still lives next to that service's
code (`backend/Dockerfile`, `frontend/Dockerfile`) - that's the more
common convention and keeps a service's build instructions colocated with
what it's building. This folder is specifically for cross-cutting
deployment config that more than one thing depends on.
