from pathlib import Path

import yaml
from jsonschema.validators import Draft202012Validator as Validator


def test_all_schemas_are_valid_jsonschema() -> None:
    schema_dir = Path("pipeline/schemas")
    schema_files = sorted(schema_dir.glob("*.yaml"))
    assert schema_files, "No schema files found under pipeline/schemas"
    for path in schema_files:
        with path.open("r", encoding="utf-8") as f:
            schema = yaml.safe_load(f)
        # Will raise on invalid schema; otherwise passes
        Validator.check_schema(schema)
