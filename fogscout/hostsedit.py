"""Server-region selection through the Windows hosts file.

Used in two ways:

* imported by the program: reading and analysing the hosts file (no admin
  rights needed),
* started with administrator rights (Windows asks via UAC) to write it:
      pythonw.exe -I -S hostsedit.py <job.json> <result.json>

Only our own, clearly marked section is written, and only for Dead by
Daylight's GameLift server names (fixed list below – the job file cannot add
other names). Entries of other tools for the same servers (e.g. Make Your
Choice) are removed, because the first entry for a name wins and they would
otherwise override the selection. Before the first change the original file
is copied to ``hosts.fogscout-backup`` next to it (``hosts.dbdmapscout-backup`` from before 1.9 counts).

Only the standard library is used (the elevated helper runs isolated).
"""
from __future__ import annotations

import json
import os
import shutil
import sys

BEGIN = "# >>> Fog Scout: server regions (managed section, do not edit) >>>"
END = "# <<< Fog Scout: server regions <<<"
# 1.9: the section the program wrote until 1.8.91 under its old name – still ours, replaced on the next write
OLD_BEGIN = "# >>> DbD Map Scout: server regions (managed section, do not edit) >>>"
OLD_END = "# <<< DbD Map Scout: server regions <<<"
BACKUP_SUFFIX = ".fogscout-backup"
OLD_BACKUP_SUFFIX = ".dbdmapscout-backup"      # 1.9: the original from before the first change, if made then
MYC_MARK = "# --+ Make Your Choice +--"
BLOCK_IPS = {"0.0.0.0", "127.0.0.1", "::", "::1", "0:0:0:0:0:0:0:0"}

# GameLift regions Dead by Daylight plays on, and regions it does not use (blocked as well)
VISIBLE_CODES = ["eu-central-1", "eu-west-1", "eu-west-2", "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                 "ca-central-1", "sa-east-1", "ap-northeast-1", "ap-northeast-2", "ap-south-1", "ap-southeast-1",
                 "ap-east-1", "ap-southeast-2"]
UNUSED = ["eu-north-1", "eu-west-3", "eu-south-1", "af-south-1", "me-south-1", "ap-northeast-3",
          "ap-southeast-5", "ap-southeast-7", "cn-north-1", "cn-northwest-1"]
ALL_CODES = VISIBLE_CODES + UNUSED


def hosts_for(code: str) -> list:
    """[service name, UDP ping beacon name] of a GameLift region."""
    if code == "ap-east-1":
        svc = "ec2.ap-east-1.amazonaws.com"
    elif code.startswith("cn-"):
        svc = f"gamelift.{code}.amazonaws.com.cn"
    else:
        svc = f"gamelift.{code}.amazonaws.com"
    return [svc, f"gamelift-ping.{code}.api.aws"]


MANAGED = [h for c in ALL_CODES for h in hosts_for(c)]
MANAGED_SET = frozenset(MANAGED)


def hosts_path() -> str:
    override = os.environ.get("DBDMS_HOSTS_FILE")          # tests only, never on Windows (elevated helper!)
    if override and sys.platform != "win32":
        return override
    root = os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"
    return os.path.join(root, "System32", "drivers", "etc", "hosts")


def read_text(path: str | None = None) -> str:
    """The hosts file as text. latin-1 maps every byte 1:1, so writing it back keeps
    whatever encoding the file had."""
    with open(path or hosts_path(), "rb") as fh:
        return fh.read().decode("latin-1")


# ------------------------------------------------------------------ parsing
def _lines(text: str) -> list:
    """Lines split at LF only (CR removed). str.splitlines would also split at bytes
    like 0x85 or 0x0c that can be part of legitimately encoded text."""
    lines = [l[:-1] if l.endswith("\r") else l for l in text.split("\n")]
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _entries(lines):
    """(index, ip, [names]) of every active (not commented) entry."""
    for i, raw in enumerate(lines):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            yield i, parts[0], [p.lower() for p in parts[1:]]


def _ours(line: str) -> bool:
    """Blank, comment or an entry that only names managed servers."""
    body = line.split("#", 1)[0].split()
    return not body or (len(body) >= 2 and all(p.lower() in MANAGED_SET for p in body[1:]))


def _section(lines, begin, end):
    """(first, last) index of a marked section. Without an end marker the section
    only extends over the directly following lines that belong to it."""
    try:
        a = next(i for i, l in enumerate(lines) if l.strip() == begin)
    except StopIteration:
        return None
    for j in range(a + 1, len(lines)):
        if lines[j].strip() == end:
            return a, j
    j = a
    while j + 1 < len(lines) and _ours(lines[j + 1]):
        j += 1
    return a, j


def _own_section(lines):
    """Our section: the current markers, else (1.9) the ones written under the old name."""
    return _section(lines, BEGIN, END) or _section(lines, OLD_BEGIN, OLD_END)


def analyse(text: str, managed=MANAGED) -> dict:
    """What the hosts file currently does with the managed server names."""
    managed = {m.lower() for m in managed}
    lines = _lines(text)
    own = _own_section(lines)
    myc = _section(lines, MYC_MARK, MYC_MARK)
    out = {"own": own is not None, "myc": myc is not None, "blocked_own": set(), "blocked_foreign": set(),
           "redirected_foreign": set(), "foreign_lines": 0}
    for i, ip, names in _entries(lines):
        hits = [n for n in names if n in managed]
        if not hits:
            continue
        if own and own[0] <= i <= own[1]:
            if ip in BLOCK_IPS:
                out["blocked_own"].update(hits)
            continue
        out["foreign_lines"] += 1
        (out["blocked_foreign"] if ip in BLOCK_IPS else out["redirected_foreign"]).update(hits)
    return out


def build(text: str, block, managed=MANAGED, remove_foreign: bool = True, note: str = "") -> str:
    """New hosts text: our section blocks exactly ``block`` (empty = no section)."""
    managed = {m.lower() for m in managed}
    lines = _lines(text)
    for begin, end in ((BEGIN, END), (OLD_BEGIN, OLD_END)):      # 1.9: an old-name section goes as well
        own = _section(lines, begin, end)
        if own:
            del lines[own[0]:own[1] + 1]
    if remove_foreign:
        myc = _section(lines, MYC_MARK, MYC_MARK)
        if myc:
            del lines[myc[0]:myc[1] + 1]
        keep = []
        for raw in lines:
            body, sep, comment = raw.partition("#")
            parts = body.split()
            if len(parts) >= 2 and any(p.lower() in managed for p in parts[1:]):
                rest = [p for p in parts[1:] if p.lower() not in managed]
                if not rest:
                    continue                                  # only our servers on this line -> drop it
                raw = " ".join([parts[0]] + rest) + (f" {sep}{comment}" if sep else "")
            keep.append(raw)
        lines = keep
    while lines and not lines[-1].strip():
        lines.pop()
    block = [b.lower() for b in block]
    if block:
        lines += ["", BEGIN,
                  "# Written by Fog Scout. Blocked names = Dead by Daylight does not use these server regions."]
        if note:
            lines.append(f"# {note}")
        lines += [f"0.0.0.0 {h}" for h in block]
        lines.append(END)
    return "\r\n".join(lines) + "\r\n"


# ------------------------------------------------------------------ writing (elevated)
def _set_readonly(path, on):
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32")
    k.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    k.GetFileAttributesW.restype = wintypes.DWORD
    k.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    k.SetFileAttributesW.restype = wintypes.BOOL
    attrs = k.GetFileAttributesW(path)
    if attrs == 0xFFFFFFFF:
        return False
    was = bool(attrs & 1)
    k.SetFileAttributesW(path, (attrs | 1) if on else (attrs & ~1))
    return was


def flush_dns() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        if ctypes.WinDLL("dnsapi").DnsFlushResolverCache():
            return True
    except Exception:
        pass
    try:
        import subprocess
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=15,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


# 1.8.45: the helper runs as a standalone elevated script without the program's i18n – it answers in German and
# names the text with its values; regions.HELPER_TEXTS (same texts) shows them in the UI language
BAD_NAME = "Ungültiger Servername im Auftrag: {name}"
CHANGED_AFTER = ("Die hosts-Datei wurde direkt nach dem Schreiben wieder verändert (Virenschutz oder ein anderes "
                 "Programm?).")
NO_RIGHTS = "Keine Schreibrechte auf die hosts-Datei (Administratorrechte?)."


def _failed(text: str, **args) -> dict:
    return {"ok": False, "error": text.format(**args), "error_text": text, "error_args": args}


def apply_job(job: dict) -> dict:
    """job = {"block": [server names], "allowed": [region codes] (comment only), "remove_foreign": bool}"""
    block = [str(n).lower() for n in job.get("block", [])]
    bad = [n for n in block if n not in MANAGED_SET]
    if bad:
        return _failed(BAD_NAME, name=repr(bad[0]))
    allowed = [c for c in job.get("allowed", []) if c in ALL_CODES]
    note = ("allowed: " + ", ".join(allowed)) if allowed else ""
    path = hosts_path()
    text = read_text(path)
    new = build(text, block, MANAGED, bool(job.get("remove_foreign", True)), note)
    if new.replace("\r\n", "\n").rstrip() == text.replace("\r\n", "\n").rstrip():
        return {"ok": True, "changed": False, "backup": ""}          # nothing to do
    data = new.encode("latin-1")                                     # before the file is opened
    backup = path + BACKUP_SUFFIX
    if not os.path.exists(backup) and os.path.exists(path + OLD_BACKUP_SUFFIX):
        backup = path + OLD_BACKUP_SUFFIX           # 1.9: the original was saved under the old name
    elif not os.path.exists(backup):
        shutil.copy2(path, backup)
    was_ro = _set_readonly(path, False)
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    finally:
        if was_ro:
            _set_readonly(path, True)
    if read_text(path) != new:
        return _failed(CHANGED_AFTER)
    flushed = flush_dns()
    return {"ok": True, "changed": True, "backup": backup, "dns_flushed": flushed}


def main(argv):
    if len(argv) != 3:
        print("usage: hostsedit.py <job.json> <result.json>")
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            job = json.load(fh)
        res = apply_job(job)
    except PermissionError:
        res = _failed(NO_RIGHTS)
    except Exception as e:  # report everything to the program
        res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    try:
        # the file was created by the (non-elevated) program; "w" keeps its owner, so it can read it back
        with open(argv[2], "w", encoding="utf-8") as fh:
            json.dump(res, fh)
    except OSError:
        pass
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
