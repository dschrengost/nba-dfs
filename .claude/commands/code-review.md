---
description: Short Zen MCP code review with GPT-5 for a recent feature (glaring issues only)
argument-hint: "[path-or-glob] (optional) — limit review to files under this path/glob"
allowed-tools: Bash(git rev-parse:*), Bash(git log:*), Bash(git diff:*), Bash(git ls-files:*)
---

## Context to load (brief)

- Current HEAD: !`git rev-parse --short HEAD`
- Last commit: !`git log -1 --pretty=format:%h%x20%ad%x20%s --date=short`
- Changed files (HEAD~1..HEAD):
  !`git diff --name-only HEAD~1..HEAD`
- Scope argument (if any): $ARGUMENTS
  <!-- If listing matches is needed and $ARGUMENTS is not empty, you can keep this line; otherwise remove it to avoid huge output -->
  <!-- Tracked files under scope (may be empty): -->
  <!-- !`git ls-files -- "$ARGUMENTS"` -->

> Keep context tight: do **not** paste full file bodies. Rely on Zen’s codereview tool to fetch what it needs.

## Your task (use Zen MCP)

Use the **Zen MCP** `codereview` workflow to perform a **short** review of the recently implemented feature.

**Constraints & tone**
- This app is creator-use only. Prioritize *glaring* issues:
  - logic bugs, broken flows, obvious API misuse
  - data handling pitfalls that would bite even in solo use
  - perf foot-guns (N+1s, O(n²) in hot paths), dangerous defaults
  - missing basic error handling or validation where failure is likely
- De-emphasize enterprise hardening unless egregious even for solo use.
- Be concise. ~10 bullets or fewer.

**Scope**
- Prefer files changed in `HEAD~1..HEAD`.
- If `$ARGUMENTS` is provided, restrict the review to files under that path/glob.

**How to run via MCP**
- Invoke the Zen MCP `codereview` with the above context.
- Ask Zen to keep output focused and short (bullet list + top 3 fixes).
- If needed, request targeted diffs for specific files/regions rather than whole files.

## Output format

**Summary (2–3 lines maximum)**  
- One-liner risk profile  
- Quick confidence level

**Findings (bulleted, highest impact first)**  
- `[Impact] Finding — file:line — brief why-it-matters / quick fix`  

**Top 3 Actions**  
1) …  
2) …  
3) …