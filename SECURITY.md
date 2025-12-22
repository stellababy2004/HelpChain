# Security Policy

## 🔒 Security Overview

HelpChain takes security seriously. This document outlines our security measures, reporting procedures, and commitment to protecting user data.

## 📞 Contact Information

**Security Team**: security@helpchain.live
**Response Time**: Within 24 hours for critical issues
**Languages**: Bulgarian (preferred), English

## 🚨 Reporting Security Vulnerabilities

If you discover a security vulnerability, please:

1. **DO NOT** create public GitHub issues
2. Email us at security@helpchain.live with:
   - Detailed description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Your contact information for follow-up

## 🛡️ Security Measures

### Web Application Security

- **Content Security Policy (CSP)**: Strict policy with violation reporting
- **HTTPS Only**: All traffic forced to HTTPS with HSTS
- **Secure Headers**: Comprehensive security headers via Talisman
- **CSRF Protection**: CSRF enforced on all forms.
   - When Flask-WTF is available: standard CSRF tokens and validation.
   - When Flask-WTF is unavailable (e.g., minimal preview/serverless boots): app-managed CSRF token stored in session and rendered into hidden input; POST requests validate this token before credentials are processed.
   - CSRF token is rotated after successful login.
- **Rate Limiting**: Progressive rate limits on sensitive endpoints

### Authentication & Authorization

- **Session Security**: Secure cookies with regeneration
- **Password Policies**: Strong password requirements
- **Two-Factor Authentication**: TOTP support for admin accounts
- **Account Lockout**: Progressive delays on failed login attempts

### Data Protection

- **PII Sanitization**: Personal data masked in logs
- **Input Validation**: Server-side validation on all inputs
- **SQL Injection Prevention**: Parameterized queries via SQLAlchemy
- **File Upload Security**: MIME type validation and size limits

### Infrastructure Security

- **Automated Scanning**: Bandit, pip-audit, OWASP ZAP, CodeQL, Trivy
- **Dependency Updates**: Automated via Dependabot
- **Container Security**: Trivy IaC and repository scans
- **Monitoring**: Sentry error tracking and alerting

## 📋 Security Headers

Our application implements the following security headers:

```
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-...'; ...
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Permissions-Policy: camera=(), microphone=(), geolocation=(), ...
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

## 🔄 Security Updates

- **Patch Management**: Critical security patches applied within 48 hours
- **Dependency Scanning**: Daily automated scans for vulnerable dependencies
- **Code Reviews**: Security-focused code reviews for all changes

## 📊 Compliance

- **Data Protection**: GDPR compliant data handling
- **Privacy by Design**: Privacy considerations in all features
- **Audit Logging**: Comprehensive security event logging

## 🎯 Bug Bounty Program

We appreciate security researchers helping us keep HelpChain secure. Responsible disclosure is rewarded with:

- Public acknowledgment (with permission)
- Priority consideration for future security roles
- HelpChain swag

## 📞 Emergency Contact

For critical security incidents requiring immediate attention:

- **Phone**: +359 XX XXX XXX (available 24/7 for emergencies)
- **Email**: security@helpchain.live

## 📖 Additional Resources

- [Security.txt](https://helpchain.live/.well-known/security.txt)
- [Privacy Policy](https://helpchain.live/privacy)
- [Terms of Service](https://helpchain.live/terms)

---

**Last Updated**: October 2025
**Version**: 1.0

## 🔐 Preview/CI Security Notes

- Preview BYPASS_TOKEN grants environment access but does not disable CSRF on admin login or other sensitive routes.
- Stable sessions require `SECRET_KEY` set via environment in serverless/preview deployments to avoid token invalidation.
