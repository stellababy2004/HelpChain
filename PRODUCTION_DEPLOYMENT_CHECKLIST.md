# 🚀 HelpChain Production Deployment Checklist

Legend: [x] Done • [ ] Pending • Notes may include (in progress)

## Pre-Deployment Verification

### 🔒 Security Readiness

- [ ] **HSTS Preload**: Submit helpchain.live to [hstspreload.org](https://hstspreload.org)
- [ ] **SSL Labs Test**: Achieve A/A+ rating on [ssllabs.com/ssltest](https://www.ssllabs.com/ssltest)
- [ ] **CSP Enforcement**: Monitor reports for 24-48h, then enforce
- [ ] **Branch Protection**: Enable all status checks in GitHub
- [ ] **Secrets Rotation**: Initial rotation completed

### 🏗️ Infrastructure Setup

- [ ] **Render Deployment**: App deployed and accessible
- [ ] **Database**: SQLite/PostgreSQL configured and migrated
- [ ] **Email Service**: Zoho SMTP working
- [ ] **File Uploads**: Directory permissions correct
- [ ] **Environment Variables**: All secrets configured

### 🔍 Security Monitoring
- [x] **GitHub Security**: CodeQL, Bandit, pip-audit enabled (Bandit/pip-audit CI добавени; CodeQL вече активен)
- [ ] **OWASP ZAP**: Baseline scan passing
- [ ] **Trivy**: IaC and repository scans clean
- [ ] **Sentry**: Error monitoring configured
- [ ] **CSP Reports**: Handler deployed and receiving reports

### ⚙️ Vercel Prebuilt & CI Size Safeguards

- [ ] **Prebuilt deploy flow**: Use Vercel prebuilt on CI: run `npx vercel build` on the runner to produce `.vercel/output` and then `npx vercel deploy --prebuilt` for the preview/production deploy.
   - Windows tip (local prebuilt): Install Python 3.11 and ensure the `python3` command resolves. Either enable the launcher alias during install or add a small shim `python3.cmd` that runs `py -3.11 %*`. Also ensure the runtime is set to Python 3.11 in vercel.json (added under `functions: { "api/**/*.py": { "runtime": "python3.11" } }`).
    - Windows known limitation: Local `vercel build` for Python functions may fail on Windows. Prefer one of:
     1) Remote build via `npx vercel deploy --yes` (no prebuilt), or
     2) Build from Linux runner in CI (Ubuntu), or
     3) Use WSL2 Ubuntu locally.
       Runtime is configured as `python3.11` in vercel.json for compatibility.
- [x] **.vercelignore rules**: Ensure `.vercelignore` contains `/.git` and `/.vercel/python/**/_vendor` to avoid uploading vendorized Python binaries (torch, nvidia, triton, etc.). (present in repo)
- [ ] **Upload size target**: Keep prebuilt upload well under the 4 GiB service limit — recommended target: < 3.5 GiB.
- [x] **Split heavy ML deps**: Document and enforce that heavy ML packages live in `requirements-ml.txt` and are NOT installed during the prebuild step. (done)
- [ ] **Early-fail CI check**: Add a lightweight CI job or step that inspects `.vercel/output` size and lists files >100MB; fail the job if total > 3.5G and notify the team.
- [x] **Early-fail CI check**: Add a lightweight CI job or step that inspects `.vercel/output` size and lists files >100MB; fail the job if total > 3.5G and notify the team. (Added as `prebuilt-size-guard` job in [.github/workflows/preview-smoke.yml](.github/workflows/preview-smoke.yml))

Example GitHub Actions check (add as a small job step):

```yaml
- name: Check .vercel/output size
   run: |
      du -sh .vercel/output || true
      find .vercel/output -type f -size +100M -exec ls -lh {} \; || true
      total=$(du -sb .vercel/output | awk '{print $1}' || echo 0)
      # 3758096384 bytes == 3.5 GiB
      if [ "$total" -gt 3758096384 ]; then
         echo "Prebuilt output too large: $total bytes" >&2
         exit 1
      fi
```

Note: adjust the snippet for Windows/PowerShell runners if used; the above is a compact Linux runner example.

### 🔎 Preview Protection Smokes (Vercel)

- [ ] **Preview URL**: Use the public preview domain from Vercel Deployments (the `*.vercel.app` link shown as “Preview”). Example: `https://your-app-abcdefg-your-team.vercel.app`.
- [ ] **Bypass Token**: If Preview Protection is enabled, get the bypass token from the deployment page (or copy the `vercel-protection-bypass` cookie value after unlocking once).
- [ ] **Run smokes against Preview**: From repo root, run:

```powershell
pwsh -NoProfile -File .\scripts\start-and-smoke.ps1 \
   -Port 443 \
   -BaseUrl "https://<preview>.vercel.app" \
   -UseExisting \
   -Strict \
   -HealthTimeoutSec 180 \
   -BypassToken "<token>"
```

- [ ] **Expected**: Health OK, admin smoke 200 (dashboard marker present in Strict), submit-request smoke passes, and overall “All smokes passed.”
- [ ] **Troubleshooting**:
   - Adjust `-HealthPath` if the health endpoint is routed differently.
   - If protected preview still blocks, confirm the token and browser protection toggle, and re-copy the token.

## Deployment Steps

### Phase 1: Infrastructure

1. **Domain Setup**

   - [ ] DNS configured for helpchain.live
   - [ ] SSL certificate auto-renewal enabled
   - [ ] CDN/Proxy headers configured (if applicable)

2. **Application Deployment**

   - [ ] Render service created
   - [ ] Environment variables set
   - [ ] Database initialized
   - [ ] File upload directory created

3. **Security Headers Verification**
   - [ ] HSTS header present
   - [ ] CSP header enforced
   - [ ] Security headers via [securityheaders.com](https://securityheaders.com)

### Phase 2: Security Validation

1. **Automated Scans**

   - [ ] All GitHub Actions workflows passing
   - [ ] Security scans clean (no critical findings)
   - [ ] Dependency vulnerabilities patched

2. **Manual Testing**

   - [ ] Admin login working with 2FA
   - [ ] File uploads with validation
   - [ ] Email notifications sending
   - [ ] CSP not blocking legitimate resources

3. **External Validation**
   - [ ] SSL Labs: A/A+ rating
   - [ ] HSTS Preload: Domain listed
   - [ ] Security Headers: Grade A+

### Phase 3: Monitoring Setup

1. **Error Monitoring**

   - [ ] Sentry configured with alerts
   - [ ] Log aggregation set up
   - [ ] Performance monitoring enabled

2. **Security Monitoring**

   - [ ] CSP violation alerts configured
   - [ ] Failed login attempt monitoring
   - [ ] File upload anomaly detection

3. **Backup & Recovery**
   - [ ] Database backup automation running
   - [ ] Backup restoration tested
   - [ ] Disaster recovery plan documented

## Post-Deployment Monitoring

### Week 1

- [ ] Monitor CSP reports for violations
- [ ] Check SSL Labs rating stability
- [ ] Verify automated backups working
- [ ] Monitor error rates in Sentry

### Ongoing

- [ ] Weekly security scans
- [ ] Monthly secrets rotation
- [ ] Quarterly backup restoration tests
- [ ] Annual security assessment

## Emergency Contacts

- **Security Issues**: security@helpchain.live
- **Technical Issues**: contact@helpchain.live
- **Domain/SSL**: [Hosting provider contact]

## Rollback Plan

If critical issues arise:

1. **Immediate**: Revert to previous deployment
2. **Investigation**: Check logs and monitoring
3. **Fix**: Address root cause
4. **Redeploy**: With fixes applied

---

**Deployment Date**: \***\*\_\_\*\***
**Deployed By**: \***\*\_\_\*\***
**Security Review By**: \***\*\_\_\*\***
