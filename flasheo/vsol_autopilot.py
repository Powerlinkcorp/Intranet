# -*- coding: utf-8 -*-
"""Compatibility wrapper for core.vsol_autopilot"""
import os, sys, asyncio
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path: sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "core") not in sys.path: sys.path.insert(0, os.path.join(PROJECT_ROOT, "core"))
from core.vsol_autopilot import *

if __name__ == "__main__":
    from core.vsol_autopilot import main
    asyncio.run(main())