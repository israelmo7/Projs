#!/usr/bin/env python3
"""Live wake word detection — thin wrapper around shared inference engine."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Re-use the canonical live test implementation
from test_model_live import main

if __name__ == "__main__":
    main()
