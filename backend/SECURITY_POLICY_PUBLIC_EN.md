# HelpChain – Public Security Summary

Last updated: 2025-11-15

This short summary explains, in non-technical language, how HelpChain protects accounts and data.

## 1. Password Protection

Your password is never stored in plain text. We use a modern hashing method (Argon2id) designed to resist hacking attempts. Old formats are upgraded automatically when you sign in.

## 2. Strong Password Rules

We require longer, mixed-character passwords and block very common ones (like "password123"). This reduces the chance attackers guess a password.

## 3. Two-Factor Authentication (2FA)

Administrators and sensitive accounts can enable one-time codes from an authenticator app. Backup codes exist for emergencies; each one works only once and is stored in secure form.

## 4. Protection Against Automated Attacks

Too many failed logins will temporarily lock an account. This helps prevent brute-force attempts.

## 5. Secure Forms & Requests

We defend against forged requests (CSRF) by requiring hidden tokens in every form that changes data.

## 6. Safe Browser Experience

We send security headers that help block clickjacking, content sniffing, and data leakage. A content security policy is being refined to reduce risk of injected scripts.

## 7. Keeping Software Up to Date

We scan for vulnerable libraries and update them regularly with automated tools. Potential issues are reviewed and fixed promptly.

## 8. Monitoring & Audit Trail

Important actions (like using a backup code or changing roles) are recorded—without storing secrets—so suspicious behavior can be investigated.

## 9. Data Minimization & Privacy

We collect only the data needed to provide the service. We do not expose passwords or sensitive tokens. Old or unused data is scheduled for cleanup.

## 10. Reporting Problems

If you see something unusual or suspect a security issue, use the in-app contact channel or designated security email (if provided). Include steps to reproduce and what you expected.

## 11. Future Improvements

Planned enhancements include stricter content security, centralized alerting, and more automation to identify risky accounts early.

## 12. Transparency

Some details (like internal network rules) are not published to avoid helping attackers, but core protective measures are summarized here for user trust.

---

If you believe something contradicts this summary, please report it so we can correct any gap quickly.
