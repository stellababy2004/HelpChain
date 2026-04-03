# Accessibility Checklist

Run this checklist after UI, layout, or interaction changes.

## Accessibility Controls

- [ ] Accessibility controls can be opened with keyboard only.
- [ ] Focus moves into the control surface and returns to the trigger when closed.
- [ ] `Esc` closes modal or drawer interactions.
- [ ] Background scrolling is controlled correctly while overlays are open.

## Preference Persistence

- [ ] High-contrast preference persists after refresh.
- [ ] Larger text preference persists after refresh.
- [ ] Reduced-motion preference persists after refresh.
- [ ] Simplified-mode preference persists after refresh.

## Simplified Mode

- [ ] Primary actions remain visible.
- [ ] Non-essential decorative or secondary sections are hidden.
- [ ] Layout density supports faster scanning without breaking task completion.

## Forms

- [ ] Invalid submissions return the expected validation response.
- [ ] Field-level errors render clearly.
- [ ] Form-level summary is present when needed.
- [ ] Focus moves to the first invalid field.

## Keyboard and Motion

- [ ] No keyboard traps are introduced.
- [ ] Tab order remains logical.
- [ ] Focus indicators remain visible.
- [ ] Reduced-motion mode removes or minimizes unnecessary animation.

## Notes

- Local SQLite schema warnings are environment issues unless they change interaction behavior.
