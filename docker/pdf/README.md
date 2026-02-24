# PDF Service (`docker/pdf`)

Internal-only PDF rendering service used by ZapUI reporting.

## API

- `POST /render`
  - Request body:
    ```json
    {
      "html": "<html>...</html>",
      "options": {
        "encoding": "UTF-8",
        "margin-top": "10mm"
      }
    }
    ```
  - Response: raw PDF bytes (`application/pdf`)

- `GET /health`
  - Basic health response.

## Implementation

- Base image: `python:3.12-alpine`
- Uses `Flask` for HTTP handling.
- Uses `wkhtmltopdf` for HTML->PDF conversion.
- Container is not published externally in `docker-compose.yml`; it is reachable only on the internal compose network as `http://pdf:8092`.

## Troubleshooting

- If PDF generation fails, inspect service logs:
  ```bash
  docker compose logs pdf
  ```
- Common causes:
  - malformed HTML in payload
  - unsupported wkhtmltopdf options
  - missing fonts for rendered language/script
