# HelpChain — User Model Audit

## Classification

`User` is a legacy/general domain model and is not a canonical authentication family.

## Current observations

- `User` has auth-like fields (`username`, `email`, `password_hash`, `role`, `is_active`)
- However, canonical admin authentication uses `AdminUser`
- Volunteer flow uses separate volunteer session logic
- `User` still appears in domain relationships and compatibility paths

## Known usages

- case participants
- push subscriptions
- some admin request/case helper queries
- compatibility checks in social/public flows

## Rules

- Do not introduce new authentication routes based on `User`
- Do not treat `User` as a third canonical login family
- Keep `User` only where legacy/domain references still require it
- Prefer explicit migration or narrowing over silent reuse

## Recommended next step

Document all runtime usages of `User` and decide whether each usage should:
- remain as domain-only
- migrate to `AdminUser`
- migrate to `Volunteer`
- be removed as legacy