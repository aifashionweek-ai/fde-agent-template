"""Data-triage harness — 'first 15 minutes with any dataset'. Standalone (does not touch the governed
agent core; reuses its PII/injection detectors). profile (read-only, memory-safe) → scan (trust boundary)
→ clean (composable primitives) → report (presentation-grade HTML). Every number is measured (J-02)."""
from .clean import DEFAULT_RECIPE, PRIMS
from .clean import run as clean
from .profile import profile
from .report import render
from .scan import scan

__all__ = ["profile", "scan", "clean", "render", "DEFAULT_RECIPE", "PRIMS"]
