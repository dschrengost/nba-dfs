# PRP-UX-SHELL-01 — UI Shell Scaffold (Next + Tailwind + shadcn/ui)

**Owner:** Agent  
**Repo:** `nba-dfs` (Next.js app)  
**Scope:** Implement the initial *UX shell* matching the Figma wireframes (Drawer Closed / Drawer Open), using **shadcn/ui** for core layout. No business logic.

---

## Why / Objective
Create a clean, navigable UI skeleton so we can iterate on the pipeline flow (Optimizer → Variants → Field → Simulator) without blocking on data plumbing. Upload dropzone is always visible; metrics drawer toggles on the right.

---

## Inputs
- **Figma wireframes:** two frames (Drawer Closed / Drawer Open). If MCP is unavailable, use spec below.
- **Layout spec (fallback if Figma MCP isn’t used):**
  - Frame: 1440×900 baseline.
  - Top bars: 40px **Live Status** (placeholder), 60px **Tabs** (Optimizer | Variants | Field | Simulator).
  - **Upload dropzone**: 350×40 card at **top-left** of main panel.
  - **Main panel**: large lineup/results grid placeholder occupying remaining space.
  - **Controls bar** (bottom): 80–100px tall.
  - **Metrics drawer** (right): start with **450px** width (test 280px later).

---

## Constraints & Guardrails
- **Do not** wire real data; **stubs only** (placeholders/text).
- Keep styling **Tailwind + shadcn tokens**.
- **Accessibility:** keyboard focusable tabs, drawer, and buttons.
- **Allowed paths only:** `./app`, `./components`, `./lib`, `./styles`.

---

## Components to Use
- **shadcn/ui:** Tabs, Separator, Card, Button, Input, ScrollArea, Sheet.
- **Optional polish later:** Aceternity effects behind a wrapper.

---

## Deliverables
- **Layout only** (no data): functional tabs; right drawer opens/closes; upload card visible across tabs.
- Pages/components created:
  - `app/layout.tsx` (global shell)  
  - `app/page.tsx` (redirect to Optimizer)  
  - `app/(studio)/{optimizer,variants,field,simulator}/page.tsx`  
  - `components/ui/{TopStatusBar,TopTabs,UploadDropzone,LineupGridPlaceholder,ControlsBar,MetricsDrawer,PageContainer}.tsx`
- Minimal styles: `styles/globals.css` (Tailwind layers + shadcn vars)
- Tokens/helpers: `lib/ui/{constants,layout}.ts`

---

## Acceptance Criteria
1. **Tabs** switch between four pages (Optimizer default).  
2. **Upload dropzone** visible on all tabs and anchored top-left (350×40).  
3. **Main panel** shows a large placeholder grid area.  
4. **Controls bar** anchored bottom and visible on all tabs.  
5. **Metrics drawer** toggles from right, **450px** width.  
6. No console errors; keyboard navigation works.

---

## GitHub Actions (beginning → end)

**Start:** `git checkout -b feature/ui-shell-prp-01`  
**During:** commits per step.  
**End:** open PR, squash-merge, tag `v0.10.0`.
