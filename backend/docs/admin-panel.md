## Architecture diagrams

### SVG (presentation-grade)

![Admin security architecture](assets/admin-security-architecture.svg)

### Mermaid (developer-readable)

```mermaid
flowchart TB
U[Admin user] --> L[/admin/login]
U --> L2[/admin/ops/login]
L --> AUTH[Auth check]
L2 --> AUTH
AUTH -->|success| SESS[Session established]
AUTH -->|failed| ATT[Insert AdminLoginAttempt]
ATT --> LOCK{Lockout threshold?}
LOCK -->|yes| RESP429[429 Retry-After]
LOCK -->|no| RESP403[403]
SESS --> GUARD[Idle timeout guard 20m]
GUARD -->|expired| LOGOUT[Logout]
GUARD -->|active| ROUTER[Admin routes]
ROUTER --> RBAC{Role allowlist}
RBAC -->|allowed| ACT[State-changing action]
RBAC -->|denied POST| DENYLOG[Log security.denied_action]
RBAC -->|denied GET| DENYNOISE[403 no audit]
ACT --> AUDIT[Insert AdminAuditEvent]
AUDIT --> APPEND[Append-only (ORM + PG trigger)]
ROUTER --> SECOV[/admin/security]
ROUTER --> AUDPAGE[/admin/audit]
ROUTER --> ROLESPAGE[/admin/roles]
```
