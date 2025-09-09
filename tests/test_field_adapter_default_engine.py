from pathlib import Path

import pandas as pd

from processes.field_sampler import adapter as field


def test_adapter_defaults_to_engine(tmp_path: Path) -> None:
    proj_csv = Path("tests/fixtures/mini_slate.csv")
    vc = pd.DataFrame(columns=["players"])  # empty variant catalog
    vc_path = tmp_path / "variant_catalog.parquet"
    vc.to_parquet(vc_path)
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    result = field.run_adapter(
        slate_id="SLATE",
        config_path=None,
        config_kv=["field_size=1", f"projections_csv={proj_csv}"],
        seed=1,
        out_root=out_root,
        input_path=vc_path,
    )

    field_path = Path(result["field_path"])
    assert field_path.exists()
