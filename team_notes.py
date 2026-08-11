"""Per-team memory of open update-threads.

When Sean gives context about a team ("Allen has a minor ankle, monitoring it"),
that becomes an OPEN THREAD attached to the team. It persists and resurfaces every
time he opens that team in the workspace, until he marks the subject RESOLVED.
Threads can accumulate follow-up entries over time (a running log per subject).

This is the team's working memory — Sean's private reasoning, not published content.
Stored per team at:  data/team_notes/<ABBR>.json   (gitignored — private)

A thread:
  {
    "id": "<abbr>-<n>",
    "topic": "short subject label, e.g. 'Josh Allen ankle'",
    "status": "open" | "resolved",
    "opened": "<iso>", "resolved_at": "<iso|null>",
    "entries": [ {"when": "<iso>", "text": "..."} , ... ]   # running log
  }

Stdlib only. No timestamps from Date.now in a workflow context — callers pass
`now_iso` (the agent supplies the real time); defaults to "" if unknown.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
NOTES_DIR = os.path.join(DATA, "team_notes")


def _path(abbr):
    return os.path.join(NOTES_DIR, f"{abbr}.json")


def load_doc(abbr):
    p = _path(abbr)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"abbr": abbr, "threads": []}


def _save(abbr, doc):
    os.makedirs(NOTES_DIR, exist_ok=True)
    with open(_path(abbr), "w") as f:
        json.dump(doc, f, indent=2)


def list_threads(abbr, status=None):
    threads = load_doc(abbr).get("threads", [])
    if status:
        threads = [t for t in threads if t.get("status") == status]
    return threads


def open_threads(abbr):
    return list_threads(abbr, status="open")


def add_thread(abbr, topic, text, now_iso=""):
    """Open a new thread with its first entry. Returns the thread."""
    doc = load_doc(abbr)
    n = len(doc.get("threads", [])) + 1
    thread = {
        "id": f"{abbr.lower()}-{n}",
        "topic": topic,
        "status": "open",
        "opened": now_iso,
        "resolved_at": None,
        "entries": [{"when": now_iso, "text": text}] if text else [],
    }
    doc.setdefault("threads", []).append(thread)
    _save(abbr, doc)
    return thread


def add_entry(abbr, thread_id, text, now_iso=""):
    """Append a follow-up entry to an existing thread. Returns (ok, thread|None)."""
    doc = load_doc(abbr)
    for t in doc.get("threads", []):
        if t["id"] == thread_id:
            t.setdefault("entries", []).append({"when": now_iso, "text": text})
            _save(abbr, doc)
            return True, t
    return False, None


def resolve_thread(abbr, thread_id, note="", now_iso=""):
    """Mark a thread resolved (it stops resurfacing). Returns (ok, thread|None)."""
    doc = load_doc(abbr)
    for t in doc.get("threads", []):
        if t["id"] == thread_id:
            t["status"] = "resolved"
            t["resolved_at"] = now_iso
            if note:
                t.setdefault("entries", []).append(
                    {"when": now_iso, "text": f"[resolved] {note}"})
            _save(abbr, doc)
            return True, t
    return False, None


def reopen_thread(abbr, thread_id, now_iso=""):
    doc = load_doc(abbr)
    for t in doc.get("threads", []):
        if t["id"] == thread_id:
            t["status"] = "open"
            t["resolved_at"] = None
            _save(abbr, doc)
            return True, t
    return False, None
