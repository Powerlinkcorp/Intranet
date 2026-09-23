#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compatibility wrapper for cli.flasheo"""
import os, sys
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path: sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "cli") not in sys.path: sys.path.insert(0, os.path.join(PROJECT_ROOT, "cli"))
from cli.flasheo import *

if __name__ == "__main__":
    from cli.flasheo import main
    main()