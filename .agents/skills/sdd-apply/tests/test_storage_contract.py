"""The file and memory implementations share observable storage behavior."""
import pytest
import json

from lib import artifact_storage as artifacts
from lib.state_storage import storage

pytestmark = pytest.mark.parametrize("implementation", [
    "memory", pytest.param("file", marks=pytest.mark.native_state),
])


def test_state_bytes_and_exclusive_lock_survive_exceptions(tmp_path, implementation):
    store = storage(tmp_path)
    assert not store.exists()
    with pytest.raises(FileNotFoundError):
        store.read()
    with store.lock():
        store.replace(b'{"revision": 1}\n')
        with pytest.raises(ValueError, match="state_locked"):
            with storage(tmp_path).lock():
                pytest.fail("A second operation acquired the same state")
        assert store.read() == b'{"revision": 1}\n'
    with pytest.raises(RuntimeError):
        with store.lock():
            raise RuntimeError("interrupted operation")
    with store.lock():
        assert store.read() == b'{"revision": 1}\n'
        store.replace(b"damaged JSON")
    assert storage(tmp_path).read() == b"damaged JSON"
    value = {"text": "Кириллица\n", "nested": [True, None, {"revision": 2}]}
    store.save(value)
    value["nested"][2]["revision"] = 3
    assert json.loads(store.read()) == {"text": "Кириллица\n", "nested": [True, None, {"revision": 2}]}


def test_artifact_bytes_replacement_enumeration_and_removal(tmp_path, implementation):
    storage(tmp_path)  # Registers this execution root for the memory backend.
    path = tmp_path / "runs/one/effects/commit.json"
    assert not artifacts.exists(path)
    with pytest.raises(FileNotFoundError):
        artifacts.read_bytes(path)
    artifacts.write(path, b"\x00\xffbinary")
    assert artifacts.read_bytes(path) == b"\x00\xffbinary"
    assert artifacts.exists(path.parent) and not artifacts.is_file(path.parent)
    assert artifacts.is_file(path)
    artifacts.write(path, "updated\n")
    artifacts.write(path.parent / "another.json", "another")
    artifacts.write(path.parent / "nested/hidden.json", "nested")
    assert artifacts.read_text(path) == "updated\n"
    assert {p.name for p in artifacts.paths(path.parent, "*.json")} == {"commit.json", "another.json"}
    artifacts.remove(path)
    assert not artifacts.exists(path)
    assert artifacts.read_text(path.parent / "another.json") == "another"
    with pytest.raises(FileNotFoundError):
        artifacts.remove(path)
    artifacts.remove(path.parent / "nested/hidden.json")
    assert artifacts.exists(path.parent / "nested")
    assert "nested" in {p.name for p in artifacts.paths(path.parent)}


def test_artifact_paths_stay_in_the_execution_namespace(tmp_path, implementation):
    storage(tmp_path)
    assert artifacts.contained(tmp_path, "runs/one/../two.json") == tmp_path / "runs/two.json"
    for relative, code in [("..", "path_escape"), (".", "path_escape"),
                           ("../outside.json", "path_escape"), ("runs/.Git/config", "git_path")]:
        with pytest.raises(ValueError) as rejected:
            artifacts.contained(tmp_path, relative)
        assert rejected.value.code == code


def test_path_resolution_and_batch_containment(tmp_path, implementation):
    from lib.common import contained_paths
    from lib.path_resolution import resolve
    (tmp_path / "nested").mkdir()
    (tmp_path / "one.txt").write_bytes(b"one")
    assert resolve(tmp_path / "nested/../one.txt", strict=True) == tmp_path / "one.txt"
    with pytest.raises(FileNotFoundError):
        resolve(tmp_path / "missing", strict=True)
    paths = contained_paths(tmp_path, ["one.txt", "nested/../../outside"])
    assert next(paths) == tmp_path / "one.txt"
    with pytest.raises(ValueError) as rejected:
        next(paths)
    assert rejected.value.code == "path_escape"
