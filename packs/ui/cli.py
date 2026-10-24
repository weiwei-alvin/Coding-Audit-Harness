"""ui-pack entry shim: run the absorbed, stateless UI CLI from any project cwd.

The kernel's typed verification commands execute with the operator's project as
cwd, so the pack is invoked by absolute script path: [python, <repo>/packs/ui/cli.py, ...].
The CLI itself is unchanged (exit codes 0/1/2 unchanged); bootstrap sys.path to
the packs/ui directory and hand over to the package's own main.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui_design_harness.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
