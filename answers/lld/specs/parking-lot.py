#!/usr/bin/env python3
# The parking lot is the GOLD page and is NOT engine-built: all of its content lives in
# ../_build_pl_wb.py (a self-contained script with the same helpers as lld_engine.py).
# This shim exists only so `python3 _verify.py parking-lot [shots]` works like every other slug.
# EDIT ../_build_pl_wb.py, never this file.
import subprocess, sys, pathlib
L = pathlib.Path(__file__).resolve().parent.parent
sys.exit(subprocess.run([sys.executable, str(L / "_build_pl_wb.py")], cwd=str(L)).returncode)
