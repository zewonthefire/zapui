# Nginx Image (`docker/nginx`)

Container image for reverse proxy and TLS termination.

## Files

- `Dockerfile`

## Build details

- Base image: `nginx:1.27-alpine`
- Installs `openssl` for temporary cert generation support
- Copies host script `nginx/scripts/entrypoint.sh` to `/entrypoint.sh`
- Uses `/entrypoint.sh` as container entrypoint

## Runtime behavior source

Most runtime behavior is implemented in:

- `nginx/scripts/entrypoint.sh`
- `nginx/state/setup_complete`
- mounted cert files under `/certs`

See `nginx/README.md` for full behavior details.
