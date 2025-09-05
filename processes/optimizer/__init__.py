"""Optimizer process package.

Contains a thin, headless adapter around a solver implementation. The adapter
does not import Streamlit and is testable in isolation. A legacy UI lives in
`processes/optimizer/_legacy` but is not used by the adapter.
"""
