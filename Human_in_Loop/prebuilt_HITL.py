"""
Legacy entrypoint — kept for backward compatibility.

The system has been refactored into the production `trinetra/` package and is now
connected to the Groww API (real orders in live mode, paper trading by default).
This shim just launches the new CLI so `python Human_in_Loop/prebuilt_HITL.py`
keeps working. Prefer running:  `python main.py`

The original single-file simulated version is preserved in git history.
"""

import sys
from pathlib import Path

# Make the project root importable when run as a standalone script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trinetra.cli import run  # noqa: E402

if __name__ == "__main__":
    print("ℹ️  Trinetra now runs from the `trinetra/` package. Launching… "
          "(next time you can use `python main.py`)\n")
    run()
