# Faculty Demo UI Redesign Implementation Plan

> **For agentic workers:** Implement task-by-task. Prefer executing in one overnight session for the 2026-08-10 faculty demo. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the SPA into a two-act Demo | Live faculty demo with dense Explain panels, embedded live results matrix, and a light lab-instrument visual system.

**Architecture:** Keep existing API hooks and probe/results data loading. Replace nav and page composition: new `ExplainPanel` + copy modules; `/demo` absorbs Dashboard + Targets advanced; `/live` absorbs LiveProbeForm + LiveResults matrix. Restyle via CSS variables and Google Fonts.

**Tech Stack:** React + Vite + React Router, existing `useApiHooks`, Vitest.

## Global Constraints

- Nav only: Demo | Live (+ brand AIT)
- Never say “3×3” on screen
- Accent `#1f4b7a`; Source Serif 4 + IBM Plex Sans/Mono
- Screenshot mode hides nav + explanations
- Do not invent live results; do not put tokens in YAML
- Prefer editing existing pages over large new frameworks

---

### Task 1: ExplainPanel + copy modules

**Files:**
- Create: `frontend/src/components/ExplainPanel.tsx`
- Create: `frontend/src/lib/demoExplainCopy.ts`
- Create: `frontend/src/lib/liveExplainCopy.ts`
- Create: `frontend/src/test/ExplainPanel.test.tsx`

- [ ] Write test: ExplainPanel shows lead; Expand toggles sections What/Why/What AIT does/How to read/If asked
- [ ] Implement ExplainPanel
- [ ] Add copy objects for Demo and Live sections
- [ ] Run `npm test -- ExplainPanel`

### Task 2: Lab visual system + App shell

**Files:**
- Modify: `frontend/src/styles/index.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/index.html` (fonts)

- [ ] Add fonts + CSS variables (cool gray, steel blue `#1f4b7a`)
- [ ] Nav: Demo | Live only; brand → `/demo`
- [ ] Routes: `/` → `/demo`; `/demo`; `/live`; `/runs/:id`; redirects from `/targets`, `/live/results`
- [ ] Optional Expand-all + screenshot mode context at app or page level

### Task 3: Demo page (`/demo`)

**Files:**
- Create: `frontend/src/pages/Demo.tsx` (or heavily rewrite Dashboard)
- Modify: reuse `StartRunButton`, `RecentRuns`, `CreateTargetForm`, `DemoModeToggle`

- [ ] Compose story sections per spec with ExplainPanels
- [ ] Advanced collapsed with Targets form + open-run + demo mode
- [ ] Wire Start demo assessment → seeded `demo-integration`
- [ ] Update/add tests for Demo page smoke

### Task 4: Live page embeds results

**Files:**
- Modify: `frontend/src/pages/Live.tsx`
- Modify: `frontend/src/pages/LiveResults.tsx` (extract board component if needed)
- Modify: `frontend/src/components/LiveProbeForm.tsx` (Explain wrappers)

- [ ] Transition + form + results on one page
- [ ] Keep 9-cell matrix; title “Live probe results” / “Completed sandbox probes”
- [ ] Screenshot mode
- [ ] Update LiveResults tests for embed + no “3×3” string

### Task 5: Verify

- [ ] `cd frontend && npm test`
- [ ] Manual: `npm run dev` — Demo → Live story, explanations, screenshot mode
