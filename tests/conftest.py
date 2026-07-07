"""Put the python/ package dir on sys.path so `import zeos_types` works."""

import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "python"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))
