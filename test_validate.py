import sys
from pathlib import Path
sys.path.append(str(Path.cwd()))
from pydantic import __version__
print("Using pydantic", __version__)
