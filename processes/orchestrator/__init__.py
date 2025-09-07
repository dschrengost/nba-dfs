"""Orchestrator for chaining pipeline stages end-to-end.

This package provides a small, deterministic driver that coordinates the
ingest → optimizer → variants → field → gpp_sim stages using their adapters
and the run registry for discovery where applicable.

CLI usage is available via `python -m processes.orchestrator`.
"""
