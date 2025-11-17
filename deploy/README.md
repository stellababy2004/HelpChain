# Nginx static cache setup

- Include `nginx_static_cache.conf` in your server block for HelpChain. For example, add this line inside your site config (e.g. `/etc/nginx/sites-available/helpchain`):

  include snippets/helpchain_static_cache.conf; # or path/to/deploy/nginx_static_cache.conf

- This snippet applies `Cache-Control` headers only for `/static/` asset requests. Fingerprinted assets (with a hash in the filename) are set to long, immutable caching; non-fingerprinted static files get a shorter TTL.

- What to expect in response headers:

  - Static assets: `Cache-Control: public, max-age=<value>` (staging default in `STAGING_VALIDATION.md` uses 3600). Fingerprinted assets will show `immutable` and a long max-age (e.g. 31536000).
  - HTML/API endpoints: no long public `max-age` (either no `Cache-Control` or short/no-store/private as configured by your app/nginx).
  - Admin/login pages: should be explicitly not publicly cacheable (e.g. `Cache-Control: no-store` or `private`).

- See `docs/STAGING_VALIDATION.md` for exact `curl -I` checks to run against staging after deployment.

Notes and quick tips

- If you use a proxy_pass to an upstream app server, keep `try_files` / static-serving logic or ensure the proxy preserves `Cache-Control` headers added by nginx.
- If using containers or a non-root nginx layout, copy `deploy/nginx_static_cache.conf` into your container image or into the host path referenced by your nginx configuration.
- For production behind a CDN: keep long TTLs only for fingerprinted/immutable assets and set shorter TTLs or cache-bypass rules for dynamic content and authenticated paths.
