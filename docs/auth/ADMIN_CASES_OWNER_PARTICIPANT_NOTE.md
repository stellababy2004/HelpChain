# HelpChain — Admin Cases Owner Participant Note

## Current issue

`admin_case_assign_owner()` assigns `owner_user_id` from `AdminUser`, but still upserts a case participant using:

- `participant_type="admin_user"`
- `user_id=owner_id`

This is semantically ambiguous because `CaseParticipant.user_id` points to `users.id`, not `admin_users.id`.

## Current rule

This path must not be treated as resolved identity alignment.

## Next step

Decide one canonical approach for admin-owner participant representation:
- separate admin participant reference
- domain-only owner without participant mirror
- explicit compatibility mapping