import sys
from pathlib import Path

# Ensure project root is on sys.path so `fatsecret`, `tools`, and `schemas`
# are importable when pytest runs from any working directory.
sys.path.insert(0, str(Path(__file__).parent))
