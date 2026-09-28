"""Tests expect the German texts (the keys); the system language must not matter."""
import os

os.environ.setdefault("DBDMS_LANG", "de")
