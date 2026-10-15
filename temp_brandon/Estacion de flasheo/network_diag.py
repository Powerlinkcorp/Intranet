# -*- coding: utf-8 -*-
"""Compatibility wrapper for core.network_diag"""
import os, sys
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path: sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "core") not in sys.path: sys.path.insert(0, os.path.join(PROJECT_ROOT, "core"))
from core.network_diag import *

if __name__ == "__main__":
    from core.network_diag import interactive_network_menu
    interactive_network_menu()
