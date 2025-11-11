# CDN & Static Asset Caching

This document explains recommended steps for integrating a CDN and caching
strategy for the HelpChain project.

1. Quick-win: enable Cache-Control headers

---

- The app already sets a default static TTL via the environment variable
  `HELPCHAIN_STATIC_MAX_AGE` (seconds). By default this is 86400 (1 day).
- For local testing you can set:
  - Development: 60 (1 minute)
  - Staging: 3600 (1 hour)
  - Production: 31536000 (1 year)

  Example (PowerShell):

  ```powershell
  $env:HELPCHAIN_STATIC_MAX_AGE='31536000'
  pytest -q tests/test_static_cache.py
  ```

2. Recommended production setup

---

- Host static assets on an origin (S3, object storage, or a dedicated static
  server). Use the CDN provider (CloudFront, Cloudflare, Fastly) to cache and
  serve assets globally.
- Configure long TTLs for immutable assets (fingerprinted filenames) and
  shorter TTLs for non-fingerprinted files. Use cache-control `public, max-age`
  values accordingly.
- Automate asset uploads and CDN invalidation in CI/CD. Invalidation is
  provider-specific; prefer path-based invalidation for releases or use
  filename fingerprinting to avoid invalidations.

3. Server-level config (nginx example)

---

Place static-serving config into your nginx site config (example below).

```
location /static/ {
    alias /path/to/your/app/backend/static/;
    access_log off;
    expires 30d; # adjust per env or use map for env-specific TTL
    add_header Cache-Control "public, max-age=2592000";
}

# For immutable assets (fingerprinted), use a longer TTL:
location ~* /static/.*\.[0-9a-f]{8,}\.(js|css|png|jpg|svg)$ {
    expires 365d;
    add_header Cache-Control "public, max-age=31536000, immutable";
}
```

4. CI/CD and invalidation

---

- If using S3 + CloudFront, add a CI step to upload the build `dist/` folder
  to the S3 bucket and optionally call `aws cloudfront create-invalidation` for
  changed files (or rely on fingerprinted filenames to avoid invalidations).
- For Cloudflare, use the API to purge by URL or by cache tags.

5. Next steps we can help with

---

- Add a CI job that uploads static assets to the chosen origin and optionally
  invalidates the CDN on deploy.
- Add a short integration test that hits the CDN origin URL and checks headers.
