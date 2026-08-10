import json

import pytest

from launch.scripts import adjacent_commit_run


def _instance(instance_id: str, commit: str, created_at: str, repo: str = "o/r") -> dict:
    return {
        "instance_id": instance_id,
        "repo": repo,
        "base_commit": commit,
        "created_at": created_at,
    }


class _ComparisonResponse:
    def __init__(self, status: str):
        self.status = status

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, str]:
        return {"status": self.status}


def test_split_uses_timestamp_ancestry_and_disk_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(adjacent_commit_run, "COMMIT_RELATIONSHIP_CACHE_DIR", tmp_path)

    instances = [
        _instance("new", "new-commit", "2026-05-01T00:00:00Z"),
        _instance("old", "old-commit", "2026-01-01T00:00:00Z"),
        _instance("middle", "middle-commit", "2026-03-01T00:00:00Z"),
        _instance("branch", "branch-commit", "2026-02-01T00:00:00Z"),
        _instance("same", "middle-commit", "2026-04-01T00:00:00Z"),
    ]
    statuses = {
        "new-commit": "ahead",
        "old-commit": "behind",
        "branch-commit": "diverged",
    }
    requested_heads = []

    def compare(url, **_kwargs):
        assert _kwargs["params"] == {"per_page": 1}
        assert _kwargs["headers"]["X-GitHub-Api-Version"] == "2026-03-10"
        head = url.rsplit("...", maxsplit=1)[1]
        requested_heads.append(head)
        return _ComparisonResponse(statuses[head])

    monkeypatch.setattr(adjacent_commit_run.requests, "get", compare)

    group = adjacent_commit_run.split_commits_for_one_repo(instances)

    assert [instance["instance_id"] for instance in group["medium"]] == [
        "middle",
        "same",
    ]
    assert [instance["instance_id"] for instance in group["before"]] == [
        "old",
        "branch",
    ]
    assert [instance["instance_id"] for instance in group["after"]] == ["new"]
    assert requested_heads == ["new-commit", "old-commit", "branch-commit"]

    cache = json.loads((tmp_path / "o%2Fr.json").read_text())
    assert cache["relationships"]["middle-commit"] == {
        "branch-commit": False,
        "new-commit": True,
        "old-commit": False,
    }
    assert cache["relationships"]["old-commit"]["middle-commit"] is True

    def unexpected_request(*_args, **_kwargs):
        pytest.fail("the second split should use the disk cache")

    monkeypatch.setattr(adjacent_commit_run.requests, "get", unexpected_request)
    assert adjacent_commit_run.split_commits_for_one_repo(instances) == group


def test_split_validates_its_input(tmp_path, monkeypatch):
    monkeypatch.setattr(adjacent_commit_run, "COMMIT_RELATIONSHIP_CACHE_DIR", tmp_path)

    with pytest.raises(ValueError, match="must not be empty"):
        adjacent_commit_run.split_commits_for_one_repo([])

    with pytest.raises(ValueError, match="same repository"):
        adjacent_commit_run.split_commits_for_one_repo(
            [
                _instance("one", "same", "2026-01-01T00:00:00Z", "o/one"),
                _instance("two", "same", "2026-01-02T00:00:00Z", "o/two"),
            ]
        )

    with pytest.raises(ValueError, match="invalid created_at"):
        adjacent_commit_run.split_commits_for_one_repo(
            [_instance("one", "same", "not-a-timestamp")]
        )
