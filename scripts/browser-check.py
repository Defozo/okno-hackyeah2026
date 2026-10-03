"""Convenience entry point for the Node Playwright acceptance test."""
from pathlib import Path
import subprocess
raise SystemExit(subprocess.call(['node', str(Path(__file__).with_suffix('.cjs'))]))
