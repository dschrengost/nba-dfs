# PRP-UX-STATES-02 — Core UI States & Accessibility (pre‑polish)

**Owner:** Agent  
**Repo:** `nba-dfs` (Next.js + Tailwind + shadcn/ui)  
**Scope:** Implement **functional states** (empty / drag-over / loading / success / error) and **accessibility** (keyboard, roles, focus, reduced motion) across the shell. No business logic or API calls — purely front-end behavior with placeholders or mock timers.

---

## Functional States

### Upload Dropzone
- Idle / drag-over / loading / success / error
- CSV extension guard
- Keyboardable: Enter/Space open, Esc cancel
- `aria-live="polite"`, `aria-busy` during loading
- Toasts via **sonner**; mount `<Toaster />` in `app/layout.tsx`

### Lineup Grid Placeholder
- Empty / Loading (skeleton rows) / Loaded
- Local toggle for QA (dev-only in ControlsBar)
- ARIA: `role="grid"`, row/col counts

### Metrics Drawer
- Skeleton-on-open then “No metrics yet”
- Trigger: `aria-expanded` + `aria-controls="metrics-panel"`
- Focus to heading on open; Esc closes

---

## A11y & Reduced Motion
- Add **Skip to main content** link as first focusable element; target `<main id="content">`.
- Honor `prefers-reduced-motion`: tame skeleton/transition.
- Ensure visible focus rings for tabs and controls.

---

## Deliverables
- `components/ui/{UploadDropzone,LineupGridPlaceholder,MetricsDrawer,ControlsBar,skeleton,sonner}.tsx`
- `app/layout.tsx` (skip link + Toaster)
- `styles/globals.css` (skip link utilities + reduced-motion rules)
- `lib/ui/{constants,a11y}.ts`

---

## Acceptance Criteria
- Upload shows drag-over/loading/success/error; keyboard + toasts.
- Grid toggles Empty→Loading→Loaded (dev-only controls).
- Drawer opens with skeleton then empty message; a11y attributes OK.
- Skip link works; reduced motion honored.  
- No runtime errors; no network calls.

**Start:** `git checkout -b feature/ux-states-a11y-02` → PR → tag `v0.11.0`.
