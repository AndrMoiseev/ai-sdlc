"""Compatibility diagnostic for the removed byte-manifest API."""
from .documents import InputError


def snapshot(project_root, change_id, stage, work_kind="change"):
    raise InputError("migration_required", "Byte manifests are retired. Run checkpoint.py inspect --project-root <project> --work-kind <kind> --change <id>; accept the current clean HEAD explicitly, then migrate legacy evidence to commit references.")