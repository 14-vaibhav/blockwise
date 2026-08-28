"""
Vercel build step (invoked via pyproject.toml's [tool.vercel.scripts]).

Builds frontend/dist before api.py is bundled, since api.py mounts that
directory as static files at "/" - see the bottom of api.py.
"""

import subprocess
from pathlib import Path

FRONTEND = Path(__file__).parent / "frontend"


def main():
    subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)


if __name__ == "__main__":
    main()
