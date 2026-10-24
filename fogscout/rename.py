"""1.9 (user: "ändere den Namen vom Programm, aktuell heisst er gleich wie das andere Programm"): the program was
"DbD Map Scout" (package ``dbdmapscout``) until 1.8.91 and is "Fog Scout" since.

What the old name left in the program folder is taken over once at start (``migrate``): the crash files are
renamed, the old log removed (made anew on every start), and the old package folder goes once git has left only
``__pycache__`` in it (an update cannot remove ignored files). The old icon stays until autostart.install has
replaced the old shortcuts that show it. Everything else that carries a name migrates where it is used – the
scheduled tasks and shortcuts (autostart.py), the section markers and the backup of the hosts file (hostsedit.py),
the OBS sources and the recording indexes (obsrec.py), the match files of the userscript (official.py). Settings,
rounds.jsonl and official.jsonl never carried the name.
"""
from __future__ import annotations

import os
import shutil

OLD_NAME = "DbD Map Scout"
OLD_PACKAGE = "dbdmapscout"
RENAME = (("dbdmapscout-crash.txt", "fogscout-crash.txt"),
          ("dbdmapscout-crash-last.txt", "fogscout-crash-last.txt"))
REMOVE = ("dbdmapscout.log",)           # the old icon: icon.OLD_FILES, removed by autostart.install after the shortcuts


def migrate(root: str) -> list:
    """Rename or remove the old name's runtime files in ``root``, and the old package folder when only
    ``__pycache__`` is left in it. Returns what was done (names), never raises."""
    done = []
    for old, new in RENAME:
        o, n = os.path.join(root, old), os.path.join(root, new)
        try:
            if os.path.isfile(o):
                if os.path.exists(n):
                    os.remove(o)                      # the new name already has a file: the old one is stale
                else:
                    os.replace(o, n)
                done.append(old)
        except OSError:
            continue
    for old in REMOVE:
        o = os.path.join(root, old)
        try:
            if os.path.isfile(o):
                os.remove(o)
                done.append(old)
        except OSError:
            continue
    done += _drop_old_package(root)
    return done


def _drop_old_package(root: str) -> list:
    """``dbdmapscout/`` with nothing but ``__pycache__`` folders (and .pyc files) in it – what git leaves behind."""
    folder = os.path.join(root, OLD_PACKAGE)
    try:
        if not os.path.isdir(folder):
            return []
        for dirpath, dirnames, filenames in os.walk(folder):
            if dirpath != folder and os.path.basename(dirpath) != "__pycache__":
                return []
            if dirpath == folder and (filenames or any(d != "__pycache__" for d in dirnames)):
                return []
            if dirpath != folder and any(not f.endswith((".pyc", ".pyo")) for f in filenames):
                return []
        shutil.rmtree(folder)
        return [OLD_PACKAGE + "/"]
    except OSError:
        return []
