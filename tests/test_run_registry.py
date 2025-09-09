import json
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from src.runs import get_run, list_runs, save_run


def test_save_and_list_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    meta = {"foo": "bar"}
    inputs_hash = {"hash": "abc"}
    validation_metrics = {"rows": 10}

    result = save_run(
        slate_key="slate",
        module="mod",
        meta=meta,
        inputs_hash=inputs_hash,
        validation_metrics=validation_metrics,
    )

    run_dir = Path(tmp_path) / "runs" / "slate" / "mod" / result.run_id
    assert json.loads((run_dir / "run_meta.json").read_text())["foo"] == "bar"
    assert json.loads((run_dir / "inputs_hash.json").read_text()) == inputs_hash
    val_metrics = json.loads((run_dir / "validation_metrics.json").read_text())
    assert val_metrics == validation_metrics

    runs = list_runs("slate", "mod")
    assert runs and runs[0]["run_id"] == result.run_id

    loaded = get_run("slate", "mod", result.run_id)
    assert loaded["foo"] == "bar"
