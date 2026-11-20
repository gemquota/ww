# Optional Docker deployment

The primary supported Android setup is Termux with Debian PRoot-Distro. Docker is an optional local backend deployment, not the default execution environment.

## Start the browser API

From the repository root, create a gitignored `.env` with at least:

```dotenv
WW_DASHBOARD_API_KEY=replace-with-a-long-random-value
WW_CORS_ORIGINS=https://gemquota.github.io
```

Then run:

```bash
docker compose -f deploy/docker-compose.yml up --build -d
```

The API is published on host loopback at `http://127.0.0.1:8080` by default. Set `WW_DASHBOARD_PORT` to change the host port. Set `WW_WORKSPACE_MOUNT` and `WW_COOKIE_FILE_MOUNT` to select host paths. Set `WW_UID` and `WW_GID` to match the owner of the host workspace so the container can write files.

The image excludes `.env`, cookies, local state, tests and historical source from its build context. The container healthcheck uses the unauthenticated API metadata route; protected API endpoints still require the dashboard API key.

To run the terminal client in a one-off container:

```bash
docker compose -f deploy/docker-compose.yml run --rm --entrypoint python ww gemini_bridge.py
```

This Docker configuration has been statically reviewed but is not yet built or exercised in CI. Do not treat it as device-verified.
