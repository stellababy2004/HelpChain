# HelpChain — Social Requests Identity Note

## Current state

`social_requests.py` contains legacy/general actor resolution through the `User` model.

This is a compatibility path and must not be interpreted as a canonical authentication family.

## Resolution order

Current social request actor labeling resolves in this order:

1. `AdminUser`
2. legacy/general `User`
3. `system`

## Rule

- `User` in social requests is a legacy/domain actor fallback
- it is not a canonical login family
- no new auth logic must be built on this path

## Naming rule

Legacy/general actor labels should be explicit, e.g. `legacy-user:*`, to avoid confusion with canonical auth actors.