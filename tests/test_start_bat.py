"""start.bat's first setup (1.8.50): only a Python every pinned package has Windows wheels for."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_setup_asks_the_launcher_for_a_supported_python_newest_first():
    # the user had only Python 3.15: "py -3" took it and pip found no onnxruntime for it
    s = _read("start.bat")
    assert "py -3\"" not in s and "where python" not in s
    tried = re.search(r"for %%V in \(([\d. ]+)\) do if not defined PY \(py -%%V -c \"pass\" <nul", s)
    assert tried and tried.group(1).split() == ["3.14", "3.13", "3.12"]
    # python on PATH only within the same range
    assert "sys.exit(not (3, 12) <= sys.version_info[:2] <= (3, 14))" in s
    # a half-finished .venv (other Python) is rebuilt instead of reused
    assert s.index('rd /s /q "%VENV%"') < s.index('%PY% -m venv "%VENV%"')


def test_readmes_name_the_same_python_range():
    assert "Python 3.12, 3.13 oder 3.14" in _read("start.bat")
    assert "3.12 bis 3.14" in _read("README.md")
    assert "3.12 to 3.14" in _read("README.en.md")
