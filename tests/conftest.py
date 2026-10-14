"""Tests expect the German texts (the keys); the system language must not matter.

On Windows the tests must never reach the real hosts file: hostsedit.hosts_path() ignores
DBDMS_HOSTS_FILE there on purpose (security of the elevated helper), so any test that would end up
there fails at once instead of writing C:\\Windows\\System32\\drivers\\etc\\hosts.
"""
import os
import sys

import pytest

os.environ.setdefault("DBDMS_LANG", "de")
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")      # Qt window tests without a display

WIN = sys.platform == "win32"
only_linux_hosts = pytest.mark.skipif(WIN, reason="would write the real hosts file on Windows")


@pytest.fixture(autouse=True)
def _never_the_real_hosts_file(monkeypatch):
    if WIN:
        from dbdmapscout import hostsedit

        def refuse():
            pytest.fail("test reached the real hosts file")
        monkeypatch.setattr(hostsedit, "hosts_path", refuse)
    yield
