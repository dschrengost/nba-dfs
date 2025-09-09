from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

try:
    # Python 3.9+ zoneinfo
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[misc, assignment]


NY_TZ = ZoneInfo("America/New_York") if ZoneInfo is not None else None


def gen_slate_key(dt: datetime | None = None) -> str:
    """Generate a slate key in YY-MM-DD_HHMMSS using America/New_York local time."""
    if dt is None:
        now = datetime.now(timezone.utc)
    else:
        now = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if NY_TZ:
        now = now.astimezone(NY_TZ)
    # YY-MM-DD_HHMMSS
    return now.strftime("%y-%m-%d_%H%M%S")


def _git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        )
        b = out.decode("utf-8").strip()
        b = re.sub(r"[^A-Za-z0-9_.-]", "-", b)
        return b or "local"
    except Exception:
        return "local"


def gen_run_id(dt: datetime | None = None, branch: str | None = None) -> str:
    ts = gen_slate_key(dt)
    slug = (branch or _git_branch())[:24]
    return f"{ts}__{slug}"


def _safe_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(data, dict | list):
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    elif isinstance(data, str):
        tmp.write_text(data)
    else:
        raise TypeError("Unsupported data type for _safe_write")
    tmp.replace(path)


@dataclass
class SaveResult:
    slate_key: str
    module: str
    run_id: str
    run_dir: Path


def save_run(
    slate_key: str,
    module: str,
    meta: dict[str, Any],
    artifacts: dict[str, Any] | None = None,
    inputs_hash: dict[str, Any] | None = None,
    validation_metrics: dict[str, Any] | None = None,
    keep_last: int = 10,
) -> SaveResult:
    """
    Persist a run under `/runs/<SLATE>/<module>/<RUN_ID>/` with atomic semantics.
    - Writes `run_meta.json` and optional `inputs_hash.json` and
      `validation_metrics.json`.
    - Optional artifacts (lineups.json, diagnostics.json, summary.json)
    - Evicts oldest directories to keep at most `keep_last` runs
    """
    # Respect explicit project root if provided to ensure consistent location when
    # invoked from various working directories
    project_root = os.environ.get("PROJECT_ROOT")
    base_runs = Path(project_root) / "runs" if project_root else Path("runs")
    root = base_runs / slate_key / module
    run_id = str(meta.get("run_id") or gen_run_id())

    tmp_dir = root / f"__tmp__{run_id}"
    final_dir = root / run_id
    artifacts_dir = tmp_dir / "artifacts"
    # write contents to tmp then rename to final
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # normalize meta
    meta = {**meta}
    meta.setdefault("schema_version", 1)
    meta.setdefault("module", module)
    meta.setdefault("run_id", run_id)
    meta.setdefault("slate_key", slate_key)
    meta.setdefault(
        "created_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    # reference artifact paths if we are writing them
    if artifacts and isinstance(artifacts, dict):
        art_ref = meta.setdefault("artifacts", {})
        for k, v in list(artifacts.items()):
            if k.endswith("_json") and isinstance(v, dict | list):
                _safe_write(artifacts_dir / k, v)
                art_ref[k] = f"artifacts/{k}"

    if inputs_hash is not None:
        _safe_write(tmp_dir / "inputs_hash.json", inputs_hash)
    if validation_metrics is not None:
        _safe_write(tmp_dir / "validation_metrics.json", validation_metrics)

    _safe_write(tmp_dir / "run_meta.json", meta)

    # finalize
    tmp_dir.replace(final_dir)

    # evict oldest beyond keep_last
    try:
        _evict_oldest(root, keep_last)
    except Exception:
        # best-effort; do not fail the save on eviction issues
        pass

    return SaveResult(
        slate_key=slate_key, module=module, run_id=run_id, run_dir=final_dir
    )


def _evict_oldest(root: Path, keep_last: int) -> None:
    if keep_last <= 0:
        return
    if not root.exists():
        return
    run_dirs = [
        p for p in root.iterdir() if p.is_dir() and not p.name.startswith("__tmp__")
    ]

    # sort by created_at in meta if present, else mtime
    def _key(p: Path) -> tuple[float, str]:
        meta_p = p / "run_meta.json"
        ts = p.stat().st_mtime
        try:
            meta = json.loads(meta_p.read_text())
            ca = meta.get("created_at")
            if isinstance(ca, str):
                dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                ts = dt.timestamp()
        except Exception:
            pass
        return (ts, p.name)

    run_dirs.sort(key=_key, reverse=True)
    for p in run_dirs[keep_last:]:
        try:
            shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass


def get_run(slate_key: str, module: str, run_id: str) -> dict[str, Any]:
    base = Path("runs") / slate_key / module / run_id
    meta_p = base / "run_meta.json"
    if not meta_p.exists():
        raise FileNotFoundError(str(meta_p))
    return cast(dict[str, Any], json.loads(meta_p.read_text()))


def list_runs(slate_key: str, module: str, limit: int = 10) -> list[dict[str, Any]]:
    base = Path("runs") / slate_key / module
    if not base.exists():
        return []
    rows: list[dict[str, Any]] = []
    for p in base.iterdir():
        if not p.is_dir() or p.name.startswith("__tmp__"):
            continue
        meta_p = p / "run_meta.json"
        meta: dict[str, Any]
        try:
            meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
        except Exception:
            meta = {}
        created_ts = p.stat().st_mtime
        if meta and isinstance(meta.get("created_at"), str):
            try:
                dt = datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00"))
                created_ts = dt.timestamp()
            except Exception:
                pass
        rows.append(
            {
                "run_id": p.name,
                "slate_key": slate_key,
                "module": module,
                "created_at": meta.get("created_at"),
                "path": str(p),
                "meta": meta or None,
                "_ts": created_ts,
            }
        )
    rows.sort(key=lambda r: (r.get("_ts", 0.0), r.get("run_id", "")), reverse=True)
    for r in rows:
        r.pop("_ts", None)
    if limit and limit > 0:
        return rows[:limit]
    return rows


def prune_runs(slate_key: str, module: str, retention_days: int = 14) -> int:
    """Remove non-tagged runs older than retention_days. Returns number removed."""
    base = Path("runs") / slate_key / module
    if not base.exists():
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400.0
    removed = 0
    for p in base.iterdir():
        if not p.is_dir() or p.name.startswith("__tmp__"):
            continue
        if (p / "tag.txt").exists():
            continue
        meta_p = p / "run_meta.json"
        try:
            meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
        except Exception:
            meta = {}
        ts = p.stat().st_mtime
        if isinstance(meta.get("created_at"), str):
            try:
                dt = datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00"))
                ts = dt.timestamp()
            except Exception:
                pass
        if ts < cutoff and not meta.get("tag"):
            try:
                shutil.rmtree(p, ignore_errors=True)
                removed += 1
            except Exception:
                pass
    return removed
