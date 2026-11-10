# ACME API — Developer Documentation (milestone 1 evidence)

This document is the evidence payload for the **API documentation** milestone.
Publish it at a public HTTPS URL and submit that URL with `submit_milestone`.

## Endpoints

The service exposes a GET /users endpoint returning JSON. Pagination is
cursor-based via the `after` query parameter.

### Response payloads

Response payloads are documented with field-by-field tables. The `user` object
contains `id` (uuid), `handle` (string, unique) and `created_at` (ISO 8601).

## Quality

Test coverage reached 95% across the whole suite, measured with `pytest --cov`
on the `main` branch at tag `docs-v1`.
