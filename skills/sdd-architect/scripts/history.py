"""Code Maat coupling semantics with unrounded support retained."""

import math
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from itertools import combinations
from pathlib import PurePosixPath

HEADER = re.compile(r"^--([0-9a-f]+)--(\d{4}-\d{2}-\d{2})--(.*)$")


def parse_history(text):
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
