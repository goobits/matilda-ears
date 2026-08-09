# Matilda Ears Docker Runtime

The container runs the canonical Ears WebSocket server and its admin dashboard in one process. Both use the same token manager and persisted data volume.

## Start

```bash
cp docker/.env.example docker/.env
# Replace both secrets in docker/.env before exposing the service.
docker compose --env-file docker/.env -f docker/docker-compose.yml up --build
```

Open the dashboard with the admin token in the URL fragment:

```text
http://localhost:8080/#token=YOUR_MATILDA_API_TOKEN
```

The fragment is moved into session storage and is not sent in the page request. Client QR codes target `ws://localhost:8773` and carry their own scoped JWT.

## Endpoints

- Dashboard: `http://localhost:8080`
- WebSocket: `ws://localhost:8773`
- Status: `http://localhost:8080/api/status`

The default image is CPU-oriented and uses the Faster Whisper backend. Set `EARS_MODEL`, `EARS_DEVICE`, and `EARS_COMPUTE_TYPE` in `docker/.env` to change the runtime configuration.

## Dashboard styles

```bash
cd docker
pnpm install --frozen-lockfile
pnpm run build
```
