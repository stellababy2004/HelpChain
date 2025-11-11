# Staging validation checklist — CDN & Cache headers

## Goal

Validate app-level cache headers + nginx static cache snippet on a staging/preview environment before enabling a global CDN.

## Summary

1. Deploy current branch to staging/preview.
2. Enable the nginx snippet `deploy/nginx_static_cache.conf` (or equivalent) on the staging host.
3. Set `HELPCHAIN_STATIC_MAX_AGE=3600` (staging) as an environment fallback.
4. Run the checks below and fix any endpoints that are incorrectly cached.

## Pre-deploy notes

- The app already sets a Cache-Control header for static-like requests via `HELPCHAIN_STATIC_MAX_AGE` (default 86400). Nginx headers take precedence if you add them in the server config.
- We included an nginx example at `deploy/nginx_static_cache.conf` and docs at `docs/CDN_AND_CACHE.md`.

## Enable nginx snippet (example)

On the staging host (SSH), drop the snippet into your nginx site conf or include it and reload nginx:

```bash
# Copy the provided snippet to the server
scp deploy/nginx_static_cache.conf user@staging:/tmp/nginx_static_cache.conf

# On the staging server (sudo if required)
sudo cp /tmp/nginx_static_cache.conf /etc/nginx/snippets/helpchain_static_cache.conf

# Include it in your site conf (example location /etc/nginx/sites-available/helpchain):
#   include snippets/helpchain_static_cache.conf;

# Test and reload nginx
sudo nginx -t && sudo systemctl reload nginx
```

## Set staging environment variable (example for systemd or your host panel)

- HELPCHAIN_STATIC_MAX_AGE=3600

## Quick validation checklist (copy/paste)

Replace `staging.YOUR_DOMAIN` below with your staging URL.

1. Static file — should have Cache-Control and appropriate max-age:

```powershell
# header-only check
curl -I https://staging.YOUR_DOMAIN/static/app.js

# Expect: Cache-Control: public, max-age=3600  (or >= configured TTL)
```

2. Another asset types check (.css, .png):

```powershell
curl -I https://staging.YOUR_DOMAIN/static/styles.css
curl -I https://staging.YOUR_DOMAIN/static/images/logo.png
```

3. App HTML / API should not have a long max-age:

```powershell
curl -I https://staging.YOUR_DOMAIN/
curl -I https://staging.YOUR_DOMAIN/requests
# Expect: no long public max-age (Cache-Control absent or short-lived)
```

4. Admin & login pages must not be cached publicly (no public long max-age):

```powershell
curl -I https://staging.YOUR_DOMAIN/admin
curl -I https://staging.YOUR_DOMAIN/admin/login
# Expect: Cache-Control: no-store, private or no public,max-age header
```

5. Validate via browser: open DevTools -> Network, load a static asset and check Response headers -> Cache-Control / Expires. Toggle the network/disable cache to re-test.

## Failure cases & fixes

- If static assets do not have Cache-Control, ensure nginx snippet is included and that the site configuration serves `/static/` from that alias.
- If HTML/API have long max-age:
  - Check nginx rules; ensure the location for dynamic content does not set `add_header Cache-Control ...` globally.
  - Add per-route headers in `backend/appy.py` for sensitive endpoints (e.g., admin) using `@app.after_request` to set `Cache-Control: no-store` or `private`.

Example per-route protection (Flask):

```python
@app.after_request
def prevent_caching_for_sensitive(response):
    if request.path.startswith('/admin') or request.endpoint in ('login', 'admin_login'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response
```

## Acceptance criteria

- `curl -I /static/app.js` returns `Cache-Control` with expected `max-age` >= staging TTL.
- `curl -I /` and `curl -I /requests` do not return long public `max-age` values.
- `curl -I /admin` and login pages return `Cache-Control: no-store` or otherwise not publicly cacheable.

## Next steps after successful validation

- Add CDN in front of staging/production (Cloudflare/CloudFront) with rules:
  - Cache static assets with long TTL (fingerprinted files immutable).
  - Do not cache cookies/authenticated paths.
  - Configure origin shielding or allowlist.
- Optionally implement CI job for S3 upload + CloudFront invalidation (nice-to-have after staging passes).

If you want, I can:

- Create a PR that includes `deploy/nginx_static_cache.conf` and a short `deploy/README.md` explaining how to enable it on staging, or
- Run the curl checks myself if you provide the staging URL / access.

\*\*\* End of checklist
