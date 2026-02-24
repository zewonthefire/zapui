# PDF Service (`docker/pdf`)

Internal PDF rendering service used by scan reporting.

---

## Purpose

Converts generated report HTML into downloadable PDF artifacts.

It is internal-only in compose by default and is consumed by backend task/report logic.

---

## API

### `POST /render`

Request body:

```json
{
  "html": "<html>...</html>",
  "options": {
    "encoding": "UTF-8",
    "margin-top": "10mm"
  }
}
```

Response:

- content type: `application/pdf`
- body: raw PDF bytes

### `GET /health`

Simple health probe endpoint.

---

## Implementation

- base image: `python:3.12-alpine`,
- framework: Flask,
- renderer: `wkhtmltopdf`.

---

## Troubleshooting

If PDF output is missing or invalid:

1. check `docker compose logs pdf`,
2. validate generated HTML payload,
3. validate `wkhtmltopdf` option compatibility,
4. confirm fonts/language support for rendered content.
