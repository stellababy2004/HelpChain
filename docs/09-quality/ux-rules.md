# UX Rules

These rules help keep HelpChain interfaces clear, task-oriented, and operationally reliable.

## Core Actions

- Make the primary action of each page immediately visible.
- Do not hide core actions behind secondary controls.

## Simplified Mode

- Keep forms, primary actions, and key statuses visible.
- Hide optional or decorative content when simplified mode is active.
- Use simplified mode to reduce cognitive load, not to remove necessary functionality.

## Forms

- Prefer inline validation.
- Keep validation feedback clear and actionable.
- Move focus to the first invalid field when appropriate.

## CTAs and Lists

- Distinguish actions with clearly different intent.
- Keep card titles and key action buttons explicit.
- Avoid clickable containers that conflict with nested controls.

## Dialogs and Drawers

- Support keyboard access, focus trapping, `Esc` close, and focus return.
- Build dynamic UI content safely without relying on unsafe HTML injection.

## Feedback

- Make success, warning, and error states immediate and unambiguous.
- Ensure statuses imply an understandable next action.

## Internationalisation

- Route user-facing strings through the translation layer.
- Avoid mixed hardcoded languages in a single task flow.
