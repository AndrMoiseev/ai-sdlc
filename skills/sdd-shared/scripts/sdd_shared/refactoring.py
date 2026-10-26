"""Version-one refactoring record vocabulary, separate from change records."""

FIELDS = {
    "criterion": ({"purpose", "scope", "conditions", "expected"}, {"parent", "source"}, "AC"),
    "decision": ({"criteria"}, {"supersedes"}, "DEC"),
    "task": ({"number", "scope", "contributes_to", "preserves", "depends_on", "status", "verification"},
             {"cannot_parallel_with", "preservation_reason", "test_changes"}, "TASK"),
    "acceptance": ({"task", "conditions", "expected", "lifetime"}, {"until_task", "replaced_by"}, "AC"),
    "verification": ({"criteria", "test_description", "location", "run"}, {"setup_task"}, "CHECK"),
}

KINDS = {"proposal": set(), "design": {"criterion", "decision"},
         "tasks": {"task", "acceptance", "verification"}}
