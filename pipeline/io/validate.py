from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml
from jsonschema.validators import Draft202012Validator as Validator
from jsonschema import RefResolver


def load_schema(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    Validator.check_schema(schema)
    return schema


def validate_obj(schema: Dict[str, Any], obj: Dict[str, Any], *, schemas_root: Path | None = None, schema_path: Path | None = None) -> None:
    store: Dict[str, Any] = {}
    base_uri = ""
    if schemas_root is not None:
        root = schemas_root.resolve()
        base_uri = root.as_uri() + "/"
        # Preload all schemas in the root into the resolver store by $id and file uri
        for path in root.glob("*.yaml"):
            try:
                with path.open("r", encoding="utf-8") as f:
                    s = yaml.safe_load(f)
                sid = s.get("$id")
                if sid:
                    store[str(sid)] = s
                store[path.resolve().as_uri()] = s
            except Exception:
                continue
    elif schema_path is not None:
        base_uri = schema_path.resolve().parent.as_uri() + "/"
    resolver = RefResolver(base_uri=base_uri, referrer=schema, store=store)
    Validator(schema, resolver=resolver).validate(obj)
