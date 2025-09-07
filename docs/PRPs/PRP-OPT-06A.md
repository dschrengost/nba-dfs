# PRP-OPT-06A — Ingest + Penalty Normalization (Local only)

**Goal**: Make the optimizer work with our **house schema** via the Python CLI + API, with:
- Robust CSV/JSON/Parquet ingest
- Header normalization + aliasing (incl. `Own% → own_proj`)
- Optional DK IDs merge from a separate file
- Ownership penalty key normalization in API (`lambda|lambda_ → weight_lambda`)
- JSON sanitation (no `Infinity` in API output)

---

## GitHub actions

**Start**
- Branch already present: `feature/opt-06-integrate-cpsat` (stay on it)
- Commit scope: only files listed below

**End**
- `git add` the touched files
- `git commit -m "OPT-06A: ingest normalization, DK-ID merge, API penalty key normalization, JSON scrub"`
- No push/PR (local only, per instructions)

---

## Changes

### 1) Python CLI: `scripts/pyopt/optimize_cli.py`
**What**
- Accept `players` **or** `projectionsPath`
- Read by extension: CSV/JSON/Parquet
- Normalize headers: `lower → strip → rm '%' → spaces→'_'`
- Aliases:
  - `proj`: `proj_fp|fpts|fieldfpts|proj|projection`
  - `ownership`: `own_proj|own|ownership|ownp|own_percent`
  - `ids`: `dk_id|player_id_dk|player_id|id`
- Merge DK IDs from optional `playerIdsPath` on `(name, team)`
- Drop empty `dk_id` column before merge (prevents false “already present”)
- Scrub non-finite numbers in diagnostics before JSON (avoid `Infinity` parse errors)

**Key diffs (illustrative snippets)**

```diff
+# header normalization
+def _norm_cols(df_in: pd.DataFrame) -> pd.DataFrame:
+    df_in.columns = (df_in.columns.str.strip().str.lower()
+                     .str.replace("%","",regex=False)
+                     .str.replace(" ","_",regex=False))
+    return df_in
```

```diff
+# read projections by extension
+if projections_path:
+    p = os.path.join(_ROOT, projections_path) if not os.path.isabs(projections_path) else projections_path
+    ext = os.path.splitext(p)[1].lower()
+    if ext in (".csv",".txt"): df_raw = pd.read_csv(p)
+    elif ext in (".json",):    df_raw = pd.read_json(p, orient="records")
+    elif ext in (".parquet",".pq"): df_raw = pd.read_parquet(p)
+    else: raise ValueError(f"Unsupported projections file type: {ext}")
+    df_raw = _norm_cols(df_raw)
+    # alias picking → build normalized df: name, team, position, salary, proj_fp, own_proj?, dk_id?
```

```diff
+# drop empty dk_id so matcher runs
+if "dk_id" in df.columns and df["dk_id"].notna().sum()==0:
+    df = df.drop(columns=["dk_id"])
```

```diff
+# merge playerIdsPath (optional)
+player_ids_df = None
+if playerIdsPath:
+    _pid = read_by_ext(playerIdsPath)  # csv/json/parquet
+    _pid = _norm_cols(_pid)
+    # detect c_dkid, c_name, c_team → build slim ids df
+    # uppercase team; merge on (name, team); keep dk_id
+
+# pass through to backend
-lineups, diagnostics = optimize_with_diagnostics(df, cons, seed, site, player_ids_df=None, engine=engine)
+lineups, diagnostics = optimize_with_diagnostics(df, cons, seed, site, player_ids_df=player_ids_df, engine=engine)
```

```diff
+# scrub non-finite JSON
+def _clean_nans(obj):
+    ...
+out = _clean_nans(out)
```

---

### 2) API: `app/api/optimize/route.ts`
**What**
- Normalize ownership penalty keys to our house schema before spawning Python:
  - map `lambda` or `lambda_` → `weight_lambda`
  - default `mode` to `"by_points"`

**Snippet (inserted after** `const payload = await req.json();` **):**
```ts
// normalize ownership penalty knobs to house schema
const consIn = (payload?.constraints ?? {}) as any;
const penIn = (consIn?.ownership_penalty ?? {}) as any;
if (penIn) {
  if (penIn.weight_lambda == null) {
    if (typeof penIn.lambda_ === "number") penIn.weight_lambda = penIn.lambda_;
    else if (typeof penIn.lambda === "number") penIn.weight_lambda = penIn.lambda;
  }
  if (penIn.mode == null) penIn.mode = "by_points";
  payload.constraints = { ...consIn, ownership_penalty: penIn };
}
```

---

## Smoke tests (copy/paste)

### CLI direct (CP‑SAT, with IDs & penalty)
```bash
echo '{"site":"dk","enginePreferred":"cp_sat","constraints":{"N_lineups":5,"ownership_penalty":{"enabled":true,"mode":"by_points","weight_lambda":8}},"seed":42,"projectionsPath":"tests/fixtures/dk/2024-01-15/projections.csv","playerIdsPath":"tests/fixtures/dk/2024-01-15/player_ids.csv"}' | uv run -q python scripts/pyopt/optimize_cli.py | jq '.ok, .diagnostics.matched_players, .diagnostics.ownership_penalty.applied'
# expect: true, "116", true
```

### API (accepts legacy key `lambda`)
```bash
curl -sS -X POST http://localhost:3000/api/optimize   -H 'Content-Type: application/json'   -d '{
    "site":"dk",
    "enginePreferred":"cp_sat",
    "constraints":{"N_lineups":5,"ownership_penalty":{"enabled":true,"mode":"by_points","lambda":8}},
    "seed":42,
    "projectionsPath":"tests/fixtures/dk/2024-01-15/projections.csv",
    "playerIdsPath":"tests/fixtures/dk/2024-01-15/player_ids.csv"
  }' | jq '.ok, .diagnostics.matched_players, .diagnostics.ownership_penalty.lambda_used, .diagnostics.ownership_penalty.applied'
# expect: true, "116", 8, true
```

### JSON sanitation (no Infinity)
```bash
curl -sS -X POST http://localhost:3000/api/optimize   -H 'Content-Type: application/json'   -d '{
    "site":"dk",
    "enginePreferred":"cp_sat",
    "constraints":{"N_lineups":1},
    "seed":42,
    "projectionsPath":"tests/fixtures/dk/2024-01-15/projections.csv",
    "playerIdsPath":"tests/fixtures/dk/2024-01-15/player_ids.csv"
  }' | jq '.diagnostics.params.max_deterministic_time'
# expect: null (was Infinity)
```

---

## Acceptance

- CLI/API accept house schema & CSV headers incl. `Own%`
- DK IDs merged (match rate > 95%; fixtures show 116/116)
- Ownership penalty applied with `weight_lambda`
- API JSON parse-safe (no `Infinity`/`NaN`)

---

## Follow-ups (next PRP)

- **PRP-OPT-06B: Native TS Solver Interfaces**
  - `lib/opt/solver.ts` interface
  - `lib/opt/cpsat.ts` (Node OR-Tools) + `lib/opt/cbc.ts` fallback
  - `lib/opt/translate.ts` (schema → model)
  - Thread via `lib/opt/run.ts`, `workers/optimizer.worker.ts`, `lib/state/run-store.ts`
  - Golden tests (seeded), parity vs CLI bridge

---

## Rollback

- Revert `app/api/optimize/route.ts` and `scripts/pyopt/optimize_cli.py` to previous commit.
- All changes are additive/guarded; no schema changes to callers required.
