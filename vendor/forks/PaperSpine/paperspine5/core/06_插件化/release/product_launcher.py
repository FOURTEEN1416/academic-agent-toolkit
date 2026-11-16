"""Relocatable entry point; runs only with the product's embedded interpreter."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
