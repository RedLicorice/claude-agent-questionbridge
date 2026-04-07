import sys
import os

# Ensure the project root is importable so main.py / build.py can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def start() -> None:
    from main import cli
    cli()
