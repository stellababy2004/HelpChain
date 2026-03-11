# UI Visual Audit — 2026-03-10

## Scope and Baseline
- Active homepage route renders `templates/home_new_slim.html` (`backend/helpchain_backend/src/routes/main.py:360-401`).
- Primary public shell is `templates/base.html` (shared nav, footer, global CSS includes).
- Current global CSS stack for base-driven pages: `static/css/design-system.css` + `static/css/styles.css`.
- Public pages audited: `home_new_slim.html`, `about.html`, `orienter.html`, `submit_request.html`, `contact.html`, `become_volunteer.html`, `faq.html`, `comment_ca_marche.html`, `collectivites_associations.html`, `cas_usage.html`, `pilotage_indicateurs.html`, `pourquoi_helpchain.html`, `vision_europeenne.html`, `public/pour_les_structures.html`, plus shared files.

## Typography inconsistencies
- Global type is repeatedly redefined in broad selectors, causing unpredictable hierarchy:
  - `static/css/styles.css:5527-5552` sets `body h1/h2/h3/p` globally.
  - `static/css/design-system.css` also defines heading/body typography and token sets.
- Mixed heading systems across public pages:
  - Structured pages use custom classes (`.hc-home__title`, `.hc-about__h2`, `.hc-orienter__title`).
  - Institutional text pages use Bootstrap utility headings (`h3`, `h5`) in `faq.html`, `comment_ca_marche.html`, etc., yielding visibly smaller page titles than the modern pages.
- Language/tonality drift in visible copy impacts perceived consistency (French + Bulgarian + English in legacy page patterns), especially in `templates/index.html` and top of `static/css/styles.css` comments/legacy sections.

## Spacing / rhythm inconsistencies
- Vertical rhythm varies page-by-page because multiple pages inject local inline `<style>` blocks (`templates/home_new_slim.html`, `templates/contact.html`, `templates/base.html`).
- Legacy info pages hardcode layout width via inline style (`style="max-width: 920px;"`) in multiple templates (`faq.html`, `comment_ca_marche.html`, `collectivites_associations.html`, etc.) while newer pages use `.hc-container`.
- `submit_request` wraps a `.card` inside a custom shell (`.hc-sr__shell`) with its own paddings (`static/css/pages/submit_request.css`), creating a denser look than `contact` and `about`.

## Button inconsistencies
- Multiple button naming conventions coexist:
  - `hc-btn--primary` / `hc-btn--ghost` (BEM-ish)
  - `hc-btn-outline` (non-BEM)
  - Bootstrap `btn btn-primary`, `btn-outline-secondary`
  - Local one-offs (`.hc-intake__btn`, `.hc-health-check-btn`).
- The same selector is redefined multiple times in `design-system.css`:
  - `.hc-btn` appears in multiple blocks (e.g. around lines `2614`, `2790`, `4289`).
- Global generic button rules in `static/css/styles.css:59-73` set `button,.btn` padding and force full-width at `max-width: 600px`, affecting all pages unexpectedly.

## Card inconsistencies
- Card model fragmentation:
  - Bootstrap cards (`.card`, `.card-body`) dominate institutional info pages.
  - Custom cards (`.hc-card`, `.hc-home__card`, `.hc-intake__card`, `.hc-trust-card`, `.hc-orienter-card`) coexist with different radii, paddings, shadows.
- `.hc-card` is redefined several times in both global stylesheets:
  - `static/css/design-system.css` (many blocks).
  - `static/css/styles.css` (e.g. lines `818`, `948`, `992`).
- Result: same semantic “card” gets different elevation/rounding depending on cascade order and page context.

## Color / contrast inconsistencies
- Multiple token systems and direct RGBA values coexist:
  - `design-system.css` has many token blocks (`:root` appears 7 times).
  - `styles.css` and inline template styles frequently bypass tokens with raw colors.
- Low-contrast muted text is widely used for small copy (`rgba(..., 0.6-0.72)` in trust lines, hints, metadata), likely to fail in some combinations (especially `0.83rem`+ text in `contact.html` and footer meta text).
- Nav/background treatment is repeatedly overridden (glass/solid variants), creating different contrast states for nav links depending on scroll and cascade (`styles.css` around `5095-5171`, `5326-5340`).

## Navigation inconsistencies
- `base.html` includes a large inline nav style block (mobile panel + breakpoints), while CSS files also contain nav overrides.
- Breakpoints are non-standard and UX-hostile:
  - Desktop CTA hidden at `max-width: 1800px` (`templates/base.html:323-325`), so CTA appears only on ultra-wide displays.
  - Desktop nav replaced by hamburger up to `1700px` (`templates/base.html:331-347`), meaning many desktop/laptop widths show mobile nav.
- Additional duplicated nav logic exists in `static/css/navigation-improvements.css` with repeated sections (`Premium Active Nav Underline`, `Step 9.1` appears twice).
- `templates/partials/navbar_public.html` exists but is not used, signaling legacy nav drift.

## Form inconsistencies
- Three separate form systems are used publicly:
  - Bootstrap form classes (`submit_request.html`, macros in `_forms.html`).
  - Custom contact form classes (`.hc-intake__input`, `.hc-intake__btn`) in `contact.html` inline CSS.
  - Volunteer form classes (`.hc-input`, `.hc-chip`, `.hc-form`) in `become_volunteer.html` with global styles from `styles.css`.
- Focus visuals differ by form family (Bootstrap focus ring vs custom outline styles), causing inconsistent affordance.
- Error/help text styles vary in size, color, and spacing between pages.

## Mobile/responsive issues
- Global `button,.btn { width: 100%; }` at `max-width: 600px` in `styles.css` can break intended inline button groups.
- Public nav switches to mobile too early (`1700px`), reducing discoverability on common desktop widths.
- Footer has many inline links in one nav row (`templates/base.html` footer block); wrapping behavior can become visually dense on smaller screens.
- Multiple page-specific responsive rules are embedded in templates, increasing risk of drift and inconsistent breakpoints.

## Accessibility issues
- Contrast risk on small muted text (trust/meta/helper copy) due low-opacity dark text on light surfaces.
- Mixed focus treatment across button/form systems; some components rely mostly on subtle shadow/transform rather than consistent high-visibility rings.
- Nav compression/hover effects depend heavily on motion and subtle visual cues; can reduce clarity for keyboard-only users if focus state is overridden by later cascade blocks.
- Excessive CSS duplication increases a11y regression risk (a11y fixes can be unintentionally overwritten by later rules).

## Visual hierarchy problems
- Coexistence of two public visual languages:
  - Modern institutional system (`home_new_slim`, `about`, `orienter`, `pour_les_structures`).
  - Legacy Bootstrap-card information pages (`faq`, `comment_ca_marche`, `cas_usage`, etc.).
- CTA emphasis is inconsistent:
  - Some pages use prominent custom pills (`hc-btn--primary`), others use plain Bootstrap buttons or local custom buttons.
- KPI/impact storytelling is inconsistent:
  - Current home (`home_new_slim`) uses static pilotage cards.
  - Legacy `templates/index.html` contains a different KPI/hero system and separate footer/nav style.

## Redundant / dead CSS
- Placeholder CSS files with no real rules:
  - `static/css/mobile-responsiveness.css` (placeholder comment only).
  - `static/css/accessibility.css` (placeholder comment only).
- High-probability unused CSS files (no template reference found):
  - `static/css/custom.css`
  - `static/css/chatbot.css`
  - `static/css/admin_volunteers.css`
  - `static/css/facebook.css`
  - `static/css/pages/home.css`
  - `static/css/pages/uncategorized.css`
  - `static/css/pages/_pass1_extracted.css`
- Legacy standalone stylesheet `static/styles.css` (Comic Sans global reset) appears not used by current base-driven pages.
- `static/css/navigation-improvements.css` contains duplicated sections and appears tied to legacy `templates/index.html`/`dashboard.html`, not the current base-driven public stack.

## Prioritized action plan
### P0 (stability + UX-critical)
- Unify nav behavior in one source: remove conflicting nav overrides and normalize breakpoints (desktop nav for standard desktop widths; mobile nav only at tablet/mobile).
- Standardize button API to one convention (`.hc-btn`, `.hc-btn--primary`, `.hc-btn--ghost`) and stop mixing with page-local button classes unless scoped exceptions are required.
- Freeze and simplify typography scale: remove broad `body h1/h2/h3/p` overrides from `styles.css` and keep heading/body scale in one tokenized source.

### P1 (consistency + maintainability)
- Migrate inline `<style>` blocks from `base.html`, `home_new_slim.html`, `contact.html` into scoped CSS modules.
- Consolidate card system to one base card primitive and variant set; update legacy info pages to use it.
- Harmonize public forms (contact/submit/volunteer) on shared field, label, help, error, and focus styles.

### P2 (cleanup + long-tail quality)
- Remove or archive unused/dead CSS files and unused legacy template fragments (`partials/navbar_public.html`, standalone legacy `index.html` styling path) after route/usage confirmation.
- Normalize trust/meta text contrast and small-text sizes to meet accessibility targets consistently.
- Add a visual regression checklist (desktop + mobile breakpoints + keyboard focus + contrast) before future UI changes.
