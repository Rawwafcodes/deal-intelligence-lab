# Deal Intelligence Lab

Read `AGENTS.md` before acting. It contains the repository-wide product,
architecture, safety and verification rules. This file adds Claude-specific
design guidance and does not replace the canonical product context under
`docs/product/`.

## Design decision-making

This is an M&A intelligence product. Avoid decorative motion or consumer-style
visuals — clarity, accessibility, and professional credibility come first.

Two design skills are installed for this project, each scoped to a different
concern:

- **`ui-ux-pro-max`** — overall usability, information architecture,
  responsive design, accessibility.
- **`emil-design-eng`** (project-local, `.claude/skills/emil-design-eng/`) —
  visual polish, interaction details, animation decisions.

When the two conflict, resolve in favor of clarity, accessibility, and
professional credibility over visual flourish.

### taste-skill library (project-local, `.claude/skills/<name>/`)

Thirteen additional skills vendored from
[Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) (commit
`e79ca9ec7e071eb3a3b623c4fb752e853fc3ed58`, MIT licensed; each folder's
`SOURCE.md` records exactly where it came from): `taste-skill`,
`taste-skill-v1`, `brutalist-skill`, `minimalist-skill`, `soft-skill`,
`redesign-skill`, `stitch-skill`, `gpt-tasteskill`, `image-to-code-skill`,
`imagegen-frontend-web`, `imagegen-frontend-mobile`, `brandkit`,
`output-skill`.

**Read their own descriptions before reaching for one** — most of them
say up front what they're for, and it usually is not this app. Several
(`taste-skill`, `brutalist-skill`, `soft-skill`, `gpt-tasteskill`,
`redesign-skill`, `stitch-skill`) are explicitly written for landing
pages, portfolios, and marketing sites, not the dashboards / data tables
/ multi-step review workflows this product is actually made of —
`taste-skill`'s own header says so verbatim ("Not dashboards, not data
tables, not multi-step product UI"). Three (`imagegen-frontend-web`,
`imagegen-frontend-mobile`, `brandkit`) generate reference *images*, not
code or copy — useful only for early visual exploration, never as a
literal implementation target. `output-skill` (anti-truncation) is
generically useful and orthogonal to visual taste. Several push toward
things this project's own rule above explicitly avoids — perpetual
micro-motion, GSAP scroll choreography, brutalist/glassy/decorative
aesthetics, "premium agency" flourish.

Applying any of them here still resolves the same way as the rest of this
section: **clarity, accessibility, and professional credibility for an
M&A intelligence tool outrank whatever aesthetic direction a given
taste-skill argues for.** Pull a technique or a piece of judgment from one
of these when it genuinely improves a concrete screen; don't adopt a
skill's whole aesthetic program (motion budget, color intensity, layout
drama) wholesale just because it's installed.
