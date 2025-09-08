---
description: End the current Claude session by committing changes, updating docs, and preparing CLAUDE.md context
argument-hint: "[commit-message] (optional) — use a custom commit message"
allowed-tools: Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*)
---

## Wrap-up Tasks

Claude, you are ending this session. Do the following in order:

1. **Stage & Commit Changes**
   - Run `git status` to confirm modified files.  
   - Stage all modified + new files with `git add -A`.  
   - Commit with the message:
     - If `$ARGUMENTS` provided → `"session end: $ARGUMENTS"`
     - Else → `"session end: update project and docs"`

2. **Update Relevant Docs**
   - Review if any changes require doc updates:
     - `README.md`
     - `/docs/` folder
     -CLAUDE.md
     -CLAUDE
     - Other feature-related docs
   - Make minimal updates (usage, config, known issues).
   - Stage & amend the same commit if docs updated.

3. **Update CLAUDE.md**
   - Ensure CLAUDE.md has:
     - Current project state (new features, config changes).
     - Any gotchas / quirks future Claude sessions must know.
     - Next-step recommendations.
   - Keep it concise but sufficient for continuity.
   - Amend commit with updated CLAUDE.md.

4. **Push to Repo**
   - Run `git push` to sync changes.

## Output

After finishing, output:

**Session Ended**  
- Commit: `<commit hash>`  
- Updated: `[list of key files]`  
- Notes: “Future Claude sessions should pick up from CLAUDE.md”