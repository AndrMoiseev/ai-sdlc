"""Code Maat coupling semantics with unrounded support retained."""

import math
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from itertools import combinations
from pathlib import PurePosixPath

HEADER = re.compile(r"^--([0-9a-f]+)--(\d{4}-\d{2}-\d{2})--(.*)$")


def parse_history(text):
    if text.lstrip().startswith("{"):
        value = json.loads(text)
        if value.get("format") != "git-history" or value.get("first_parent") is not True or value.get("renames") is not True:
            raise ValueError("History requires first-parent collection with rename tracking")
        if date.fromisoformat(value["since"]) > date.fromisoformat(value["until"]):
            raise ValueError("Invalid history window")
        revisions = set()
        for commit in value["commits"]:
            if commit["revision"] in revisions:
                raise ValueError("History contains duplicate revisions")
            revisions.add(commit["revision"])
            date.fromisoformat(commit["date"])
            if type(commit["production_files"]) is not int or not 0 <= commit["production_files"] <= len(commit["changes"]):
                raise ValueError("Invalid production changeset size")
            for name, change in commit["changes"].items():
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name or re.match(r"^[A-Za-z]:", name):
                    raise ValueError("History path must be repository-relative")
                if type(change["binary"]) is not bool or any(
                    (value is not None if change["binary"] else type(value) is not int or value < 0)
                    for value in (change["added"], change["deleted"])
                ):
                    raise ValueError("Invalid history numstat")
        return value["commits"]
    commits, current = [], None
    for number, line in enumerate(text.splitlines(), 1):
        match = HEADER.match(line)
        if match:
            current = {"revision": match[1], "date": match[2], "author": match[3], "changes": {}}
            date.fromisoformat(current["date"])
            commits.append(current)
        elif line.strip():
            parts = line.split("\t")
            if current is None or len(parts) != 3:
                raise ValueError(f"git.log line {number}: expected numstat or --revision--date--author")
            added, deleted, path = parts
            if path.startswith('"') or " => " in path:
                raise ValueError(f"git.log line {number}: export with -c core.quotePath=false --no-renames")
            normalized = path.replace("\\", "/")
            source_path = PurePosixPath(normalized)
            if source_path.is_absolute() or re.match(r"^[A-Za-z]:", normalized) or ".." in source_path.parts or not source_path.name:
                raise ValueError(f"git.log line {number}: expected a repository-relative file path")
            path = source_path.as_posix()
            if path in current["changes"]:
                raise ValueError(f"git.log line {number}: duplicate path in commit")
            binary = added == "-" or deleted == "-"
            if not binary and (int(added) < 0 or int(deleted) < 0):
                raise ValueError(f"git.log line {number}: negative numstat")
            current["changes"][path] = {"added": None if binary else int(added),
                                       "deleted": None if binary else int(deleted), "binary": binary}
    if len({c["revision"] for c in commits}) != len(commits):
        raise ValueError("git.log contains duplicate revisions")
    return commits


def collect_history(config, root, run, policy, sources):
    """Track Git-detected renames backwards to current paths, retaining whole changesets."""
    from datetime import datetime, timezone
    from fnmatch import fnmatchcase
    days = policy["measurements"]["quality_indicators"]["history_days"]
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    if run(["git", "rev-parse", "--is-shallow-repository"], root, policy).decode().strip() == "true":
        raise ValueError("History is shallow; obtain the required history before auditing")
    argv = ["git", "-c", "core.quotePath=false", "log", "--first-parent", "--no-merges", "--find-renames",
            "--numstat", "-z", "--format=%x1e%H%x09%cs%x00", "--since=" + start.isoformat() + "T00:00:00Z",
            "--until=" + end.isoformat() + "T23:59:59Z"]
    text = run(argv, root, policy).decode("utf-8")
    aliases, commits = {}, []
    def production(path):
        return (path.endswith(".kt") and any(path.startswith(prefix.rstrip("/") + "/") for prefix in config["source_roots"])
                and not any(fnmatchcase(path, pattern) for pattern in config.get("exclude_paths", [])))
    for block in text.split("\x1e"):
        if not block.strip("\0\r\n"):
            continue
        header, _, content = block.partition("\0")
        revision, timestamp = header.split("\t")
        parts, index = content.split("\0"), 0
        changes, renames = {}, []
        production_count = 0
        while index < len(parts):
            entry = parts[index].lstrip("\r\n")
            index += 1
            if not entry:
                continue
            added, deleted, path = entry.split("\t", 2)
            old = None
            if not path:
                old, path = parts[index:index + 2]
                index += 2
                renames.append((old, path))
            production_count += int(production(path) or bool(old and production(old)))
            current = aliases.get(path, path)
            if current in changes:
                raise ValueError("Ambiguous historical path identity after rename tracking")
            binary = added == "-" or deleted == "-"
            changes[current] = {"added": None if binary else int(added), "deleted": None if binary else int(deleted), "binary": binary}
        commits.append({"revision": revision, "date": timestamp, "author": "", "changes": changes, "production_files": production_count})
        for old, new in renames:
            aliases[old] = aliases.get(new, new)
            aliases.pop(new, None)
    return json.dumps({"format": "git-history", "first_parent": True, "renames": True,
                       "since": start.isoformat(), "until": end.isoformat(), "commits": commits}).encode(), argv


def history_view(commits, policy):
    max_changeset = policy["measurements"]["history"]["maximum_changeset_size"]
    revisions, filtered, shared = Counter(), Counter(), Counter()
    churn = defaultdict(lambda: {"added": 0, "deleted": 0, "binary_changes": 0})
    for commit in commits:
        paths = sorted(commit["changes"])
        revisions.update(paths)
        for path, change in commit["changes"].items():
            churn[path]["added"] += change["added"] or 0
            churn[path]["deleted"] += change["deleted"] or 0
            churn[path]["binary_changes"] += int(change["binary"])
        if len(paths) <= max_changeset:
            filtered.update(paths)
            shared.update(combinations(paths, 2))
    coupling = []
    for (left, right), support in sorted(shared.items()):
        average = (filtered[left] + filtered[right]) / 2
        degree = math.floor(200 * support / (filtered[left] + filtered[right]))
        coupling.append({"left": left, "right": right, "left_revisions": filtered[left],
                         "right_revisions": filtered[right], "shared": support,
                         "average_revisions": average, "degree": degree})
    return {"window": {"start": min((c["date"] for c in commits), default=None),
                       "end": max((c["date"] for c in commits), default=None)},
            "filters": {"max_changeset": max_changeset},
            "revisions": dict(sorted(revisions.items())), "churn": dict(sorted(churn.items())),
            "coupling": sorted(coupling, key=lambda row: (-row["degree"], -row["average_revisions"], row["left"], row["right"]))}


def group_activity(commits, owner_for_file, policy):
    if not commits:
        return {}
    cutoff = date.fromisoformat(max(c["date"] for c in commits)) - timedelta(days=policy["measurements"]["history"]["recent_days"])
    groups = defaultdict(lambda: {"commits": 0, "recent_commits": 0, "file_occurrences": 0})
    for commit in commits:
        counts = Counter(owner_for_file[path] for path in commit["changes"] if owner_for_file.get(path) is not None)
        for owner, count in counts.items():
            groups[owner]["commits"] += 1
            groups[owner]["recent_commits"] += int(date.fromisoformat(commit["date"]) >= cutoff)
            groups[owner]["file_occurrences"] += count
    return dict(sorted(groups.items()))
