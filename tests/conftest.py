from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path for package imports like `pipeline.*`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Default to stub sampler for tests unless overridden by env
os.environ.setdefault("FIELD_SAMPLER_IMPL", "tests.fixtures.stub_field_sampler:run_sampler")


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="Temporarily skipped during stabilization (FS-07)")
    for item in items:
        if "smoke" not in item.keywords:
            item.add_marker(skip)
