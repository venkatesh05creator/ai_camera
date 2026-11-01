"""
scripts/jarvis_voice.py - Production-Ready Cross-Platform Live Voice & Audio Loop
Integrated with Project JARVIS & Aegis AI Camera Assistant.
"""

from __future__ import annotations

import os
import sys

# Ensure project root is on Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from jarvis_voice import listen_loop, speak, dispatch_query

if __name__ == "__main__":
    listen_loop()
