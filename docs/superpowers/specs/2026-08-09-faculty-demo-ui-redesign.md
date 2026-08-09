# Faculty Demo UI Redesign

**Date:** 2026-08-09  
**Status:** Approved  
**Branch:** `feature/faculty-demo`  
**Demo:** 2026-08-10

## Goal

Replace the fragmented Dashboard / Targets / Live / Results chrome with a **two-act faculty demo UI** that:

1. Tells one clear story (Demo → Live).
2. Keeps the happy path short.
3. Puts **dense, Q&A-ready explanations** behind every major block.
4. Presents live results in a fixed 9-cell matrix **without saying “3×3” on screen**.
5. Uses a light “lab instrument” visual system suitable for projector screenshots.

## Navigation

| Nav | Route | Role |
|---|---|---|
| **AIT** (brand) | `/demo` | Home |
| **Demo** | `/demo` | Act 1 — mock CRM assessment |
| **Live** | `/live` | Act 2 — real SaaS probes + results board |

Deep links (not in nav): `/runs/:id` (demo run detail).  
Redirect `/` → `/demo`. Optional redirects: `/targets` → `/demo#advanced`, `/live/results` → `/live#results`.

## Act 1 — `/demo` story order

1. Act pill + **Why this exists** (+ Explain disclosure)
2. **This act** — mock CRM (+ Explain)
3. **Policy in play** — seeded `demo-integration` allowlist vs undeclared billing (+ Explain)
4. Primary CTA — **Start demo assessment**
5. **Outcome** — risk, findings, HTML report, recent demo runs (+ Explain)
6. **Next** — continue to Live
7. **Advanced** (collapsed) — create target, open run by id, demo mode (+ Explain)

## Act 2 — `/live` story order

1. Act pill + **Transition** from demo (+ Explain)
2. **Probe form** — auto-filled provider/plan/YAML + token; help under fields (+ Explain per field group)
3. **Live probe results** board — 9-cell matrix layout (GitHub/Google/Notion × readonly/smoke/smoke-extended); **never label it “3×3”** (+ Explain)
4. Screenshot mode — hide nav + explanations; keep title + matrix + detail cards
5. **Advanced** (collapsed) — prior-run dump / raw ids (+ Explain)

## Explanation system

Every major section:

- **Lead:** 1–2 sentences always visible
- **Explain control:** opens dense panel with:
  - What this is
  - Why it matters
  - What AIT does here

Optional **Hide explanations** (nav) collapses all panels. Per-panel **Hide** removes that box.  
Screenshot mode forces explanations hidden.

## Visual system

- Light cool gray page wash; white surfaces; slate borders; minimal shadow
- Accent steel blue `#1f4b7a` (not purple)
- Risk chips: green / amber / red
- Fonts: Source Serif 4 (display), IBM Plex Sans (UI), IBM Plex Mono (paths/ids)
- Max width ~1040px; clear section rhythm; 2–3 light motions only

## Non-goals

- Rewriting backend APIs
- Hiding probe form fields
- Inventing live results
- Marketing landing-page chrome

## Success criteria

- [ ] Faculty can follow Demo → Live without visiting Targets/Results as separate nav items
- [ ] Every primary control has a dense Explain panel
- [ ] Live results show all nine plan cells when artifacts exist
- [ ] Screenshot mode yields a clean slide capture
- [ ] `npm run dev` still starts full stack
