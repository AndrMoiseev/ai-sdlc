"""Project task helper. Supply a runner that returns stdout bytes in the project root."""

from datetime import timedelta


def history_report(source_roots, exclude_paths, days, run):
    """Track Git-detected renames backwards to current paths, retaining whole changesets."""
    from datetime import datetime, timezone
    from fnmatch import fnmatchcase
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    if run(["git", "rev-parse", "--is-shallow-repository"]).decode().strip() == "true":
        raise ValueError("History is shallow; obtain the required history before auditing")
    argv = ["git", "-c", "core.quotePath=false", "log", "--first-parent", "--no-merges", "--find-renames",
            "--numstat", "-z", "--format=%x1e%H%x09%cs%x00", "--since=" + start.isoformat() + "T00:00:00Z",
            "--until=" + end.isoformat() + "T23:59:59Z"]
    text = run(argv).decode("utf-8")
    aliases, commits = {}, []
    def production(path):
        return (path.endswith(".kt") and any((prefix == "." or path.startswith(prefix.rstrip("/") + "/")) for prefix in source_roots)
                and not any(fnmatchcase(path, pattern) for pattern in exclude_paths))
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
    return {"format": "git-history", "first_parent": True, "renames": True,
                       "since": start.isoformat(), "until": end.isoformat(), "commits": commits}
