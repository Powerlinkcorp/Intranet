# -*- coding: utf-8 -*-
"""Compatibility wrapper for core.profiles"""
import os, sys
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path: sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "core") not in sys.path: sys.path.insert(0, os.path.join(PROJECT_ROOT, "core"))
from flasheo.core.profiles import *
