'''
usage:
export GITHUB_TOKEN=... # for linux
$env:GITHUB_TOKEN=...   # for windows
python -m launch.scripts.adjacent_commit_run --config-path ...
'''

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os, json
from pathlib import Path
import tempfile
import threading
from typing import Literal, Optional, TypedDict, DefaultDict
from urllib.parse import quote
from fire import Fire
import requests

from launch.scripts.parser import run_parser
from launch.run import run_setup, run_organize
from launch.core.runtime import SetupRuntime
from launch.utilities.config import Config, load_config
from launch.scripts import collect

MAX_ITERATION = 8
COMMIT_RELATIONSHIP_CACHE_DIR = str(Path(__file__).resolve().parents[2] / ".cache" / "adjacent_commit_run")

_commit_relationship_cache_lock = threading.Lock()

class SWEInstance(TypedDict):
    instance_id: str
    repo: str
    base_commit: str
    created_at: str
    test_status: dict[str, Literal['pass', 'fail', 'skip']]
    log_parser: str
    rebuild_cmds: list[str]
    test_cmds: list[str]
    print_cmds: list[str]
    docker_image: str
    docker_image_layers: dict[str, list[str]]
    per_test_command_generator: Optional[str]
    pertest_command: Optional[str]

class Group(TypedDict):
    before: list[SWEInstance]
    medium: SWEInstance
    after: list[SWEInstance]

def launch_one_round(config: Config, dataset: list[SWEInstance], instance_ids: list[str]) -> list[SWEInstance]:
    if config.mode["setup"]:
        run_setup(config, dataset)
        collect.main(config.workspace_root, platform = config.platform, step = "setup", instance_ids = instance_ids)
    if config.mode["organize"]:
        if not os.path.exists(f"{config.workspace_root}/setup.jsonl"):
            raise RuntimeError(f"{config.workspace_root}/setup.jsonl NOT FOUND. You need to finish the setup step first.")
        with open(f"{config.workspace_root}/setup.jsonl") as f:
            dataset = [json.loads(line) for line in f]
        run_organize(config, dataset)
        success_repos = collect.main(config.workspace_root, platform = config.platform, step = "organize", instance_ids = instance_ids)
    return success_repos

def split_commits_for_one_repo(instances: list[SWEInstance]) -> Group:
    '''
    returns:
    {
        "before": [instances with commits that are not descendants of medium commits], 
        "medium": instance with timestamp at the medium among instances with max num of overlapped base commits,
        "after": [instances with commits that are descendants of medium commits]
    }
    '''
    if not instances:
        raise ValueError("instances must not be empty")

    repo = instances[0]["repo"]
    if any(instance["repo"] != repo for instance in instances):
        raise ValueError("all instances must belong to the same repository")

    missing_timestamps = [
        instance["instance_id"]
        for instance in instances
        if not instance.get("created_at")
    ]
    if missing_timestamps:
        raise ValueError(
            "instances are missing created_at: " + ", ".join(missing_timestamps)
        )

    overlap_commit_count: DefaultDict[str, list[SWEInstance]] = defaultdict(list)
    for instance in instances:
        overlap_commit_count[instance["base_commit"]].append(instance)
    most_overlap_commit_count = max([len(v) for v in overlap_commit_count.values()])
    candidates: list[SWEInstance] = []
    for v in overlap_commit_count.values():
        if len(v) == most_overlap_commit_count:
            candidates += v
    # sorted() is stable, so equal timestamps retain the caller's order. For an
    # even-sized group, choose the upper median so that `medium` is always an
    # actual instance.
    def timestamp(instance: SWEInstance) -> float:
        try:
            value = datetime.fromisoformat(
                instance["created_at"].replace("Z", "+00:00")
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                f"invalid created_at for {instance['instance_id']}: "
                f"{instance['created_at']!r}"
            ) from error
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    ordered_indices = sorted(
        range(len(candidates)), key=lambda index: timestamp(candidates[index])
    )
    medium_index = ordered_indices[len(ordered_indices) // 2]
    medium = candidates[medium_index]

    before: list[SWEInstance] = []
    after: list[SWEInstance] = []
    with _commit_relationship_cache_lock:
        cache = _load_commit_relationship_cache(repo)
        cache_changed = False
        try:
            for instance in instances:
                if instance["instance_id"] == medium["instance_id"]:
                    continue

                descendant, relationship_was_fetched = _is_descendant(
                    repo,
                    ancestor=medium["base_commit"],
                    descendant=instance["base_commit"],
                    cache=cache,
                )
                cache_changed |= relationship_was_fetched
                (after if descendant else before).append(instance)
        finally:
            # Preserve successful comparisons even when a later API request
            # fails, so retrying can continue from the local cache.
            if cache_changed:
                _write_commit_relationship_cache(repo, cache)

    return {"before": before, "medium": medium, "after": after}


def _commit_relationship_cache_path(repo: str) -> Path:
    # URL encoding keeps each repository in one file without filename
    # collisions or user-controlled subdirectories.
    return COMMIT_RELATIONSHIP_CACHE_DIR / f"{quote(repo, safe='')}.json"


def _load_commit_relationship_cache(repo: str) -> dict[str, dict[str, bool]]:
    cache_path = _commit_relationship_cache_path(repo)
    try:
        with cache_path.open(encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    if (
        not isinstance(payload, dict)
        or payload.get("repo") != repo
        or not isinstance(payload.get("relationships"), dict)
    ):
        return {}

    relationships: dict[str, dict[str, bool]] = {}
    for ancestor, descendants in payload["relationships"].items():
        if not isinstance(ancestor, str) or not isinstance(descendants, dict):
            continue
        relationships[ancestor] = {
            descendant: is_descendant
            for descendant, is_descendant in descendants.items()
            if isinstance(descendant, str) and isinstance(is_descendant, bool)
        }
    return relationships


def _write_commit_relationship_cache(
    repo: str, relationships: dict[str, dict[str, bool]]
) -> None:
    cache_path = _commit_relationship_cache_path(repo)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=cache_path.parent,
            prefix=f".{cache_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            json.dump(
                {"repo": repo, "relationships": relationships},
                temporary_file,
                indent=2,
                sort_keys=True,
            )
            temporary_file.write("\n")
        os.replace(temporary_path, cache_path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _is_descendant(
    repo: str,
    ancestor: str,
    descendant: str,
    cache: dict[str, dict[str, bool]],
) -> tuple[bool, bool]:
    if ancestor == descendant:
        return True, False

    cached_relationship = cache.get(ancestor, {}).get(descendant)
    if cached_relationship is not None:
        return cached_relationship, False

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = (
        f"https://api.github.com/repos/{quote(repo, safe='/')}/compare/"
        f"{quote(ancestor, safe='')}...{quote(descendant, safe='')}"
    )
    try:
        response = requests.get(
            url, headers=headers, params={"per_page": 1}, timeout=30
        )
        response.raise_for_status()
        status = response.json()["status"]
    except (requests.RequestException, KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"could not compare commits {ancestor} and {descendant} in {repo}"
        ) from error

    if status not in {"ahead", "behind", "diverged", "identical"}:
        raise RuntimeError(
            f"GitHub returned an unknown comparison status for {repo}: {status!r}"
        )

    is_descendant = status in {"ahead", "identical"}
    cache.setdefault(ancestor, {})[descendant] = is_descendant

    # A compare response also establishes the reverse relationship, avoiding
    # another API request when a later recursive split reverses the pair.
    reverse_is_descendant = status in {"behind", "identical"}
    cache.setdefault(descendant, {})[ancestor] = reverse_is_descendant
    return is_descendant, True

def apply_res_for_same_commit(
        current_instance: SWEInstance, 
        medium_instance: SWEInstance, 
    ) -> SWEInstance:
    current_instance["rebuild_cmds"] = medium_instance["rebuild_cmds"]
    current_instance["test_cmds"] = medium_instance["test_cmds"]
    current_instance["print_cmds"] = medium_instance["print_cmds"]
    current_instance["log_parser"] = medium_instance["log_parser"]
    current_instance["test_status"] = medium_instance["test_status"]
    if medium_instance.get("per_test_command_generator", False):
        current_instance["per_test_command_generator"] = medium_instance["per_test_command_generator"]
    if medium_instance.get("pertest_command", False):
        current_instance["pertest_command"] = medium_instance["pertest_command"]
    current_instance["docker_image"] = medium_instance["docker_image"]
    current_instance["docker_image_layers"] = medium_instance["docker_image_layers"]
    return current_instance

def run_one_commit_test(
        base_commit: str, 
        medium_instance: SWEInstance, 
        after_medium: bool,
        config: Config,
    ) -> tuple[SWEInstance, bool] :
    success: bool = False
    commands = [
        "git checkout -b wipcheckoutbackup",
        "git add -A",
        "git commit --no-verify -m 'temp'",
        "git checkout main ; git checkout master", 
        f"git reset --hard {base_commit}",
        "git cherry-pick --no-commit -Xours wipcheckoutbackup",
        "git reset",
        "git branch -D wipcheckoutbackup"
    ]
    res: SWEInstance = {}
    res["repo"] = medium_instance["repo"]
    res["base_commit"] = base_commit

    container = SetupRuntime.from_base_image(medium_instance["docker_image"], medium_instance, config.platform, config.timeout)
    for command in commands:
        container.send_command(command)
    container.send_command(" ; ".join(medium_instance["rebuild_cmds"]))
    container.send_command(" ; ".join(medium_instance["test_cmds"]))
    log = container.send_command(" ; ".join(medium_instance["print_cmds"])).output
    status: dict[str, Literal['pass', 'fail', 'skip']] = run_parser(medium_instance["log_parser"], log)
    del container

    if after_medium and len(status) >= len(medium_instance["test_status"]):
        success = True
    if (not after_medium) and len(status) >= int(len(medium_instance["test_status"])*0.80):
        success = True
    if not success:
        return res, False

    container = SetupRuntime.from_base_image(medium_instance["docker_image"], medium_instance, config.platform, config.timeout)
    for command in commands:
        container.send_command(command)
    container.commit(image_name=config.image_prefix, tag=base_commit)
    del container
    res["rebuild_cmds"] = medium_instance["rebuild_cmds"]
    res["test_cmds"] = medium_instance["test_cmds"]
    res["print_cmds"] = medium_instance["print_cmds"]
    res["log_parser"] = medium_instance["log_parser"]
    res["test_status"] = status
    if medium_instance.get("per_test_command_generator", False):
        res["per_test_command_generator"] = medium_instance["per_test_command_generator"]
    if medium_instance.get("pertest_command", False):
        res["pertest_command"] = medium_instance["pertest_command"]
    res["docker_image"] = f"{config.image_prefix}:{base_commit}"
    res["docker_image_layers"] = medium_instance["docker_image_layers"]
    res["docker_image_layers"]["switch_commit_layer"] = commands
    return res, True

def printer(iteration: int, groups: dict[str, Group], give_up_count: int):
    group_count = [len(group["before"])+len(group["medium"])+len(group["after"]) for group in groups.values()]
    print(
        f"Iteration No.{iteration+1}/{MAX_ITERATION}. "
        f"{len(groups)} groups to be processed, "
        f"Max group size: {max(group_count)}, "
        f"Min group size: {min(group_count)}. ",
        f"Num of failed instances: {give_up_count}. ",
        flush=True
    )

def save_res(root: str, instances: list[SWEInstance]):
    res_path = os.path.join(root, "result.jsonl")
    with open(res_path, "w") as f:
        for i in instances:
            f.write(json.dumps(i)+"\n")
    print(f"Saved {len(instances)} successful instances to {res_path}.", flush=True)

def load_res(root: str) -> list[SWEInstance]:
    res_path = os.path.join(root, "result.jsonl")
    if not os.path.exists(res_path):
        return []
    with open(res_path) as f:
        instances = [json.loads(i) for i in f]
    print(f"Load {len(instances)} successful instances from {res_path}.", flush=True)
    return instances

def main(config_path: str):
    all_success_instances: list[SWEInstance] = []
    failed_once: set[str] = set()
    give_up: set[str] = set()
    groups: dict[str, Group]
    todos: list[SWEInstance]
    todo_ids: list[str]
    
    config: Config = load_config(config_path)
    all_success_instances = load_res(config.workspace_root)
    all_success_ids = set([i["instance_id"] for i in all_success_instances])
    with open(config.dataset, "r") as f:
        dataset = [json.loads(line) for line in f]
    dataset = [i for i in dataset if i["instance_id"] not in all_success_ids]

    groups_by_repo: DefaultDict[str, list[SWEInstance]] = defaultdict(list)
    for instance in dataset:
        groups_by_repo[instance["repo"]].append(instance)
    group_list = [split_commits_for_one_repo(repo_group) for repo_group in groups_by_repo.values()]
    groups = {group["medium"]["instance_id"]: group for group in group_list}
    todos = [group["medium"] for group in groups.values()]
    todo_ids = [i["instance_id"] for i in todos]

    for iteration in range(MAX_ITERATION):
        printer(iteration, groups, len(give_up))

        success_repos = launch_one_round(config, todos, todo_ids)
        all_success_instances += success_repos
        success_ids = [i["instance_id"] for i in success_repos]
        new_groups: dict[str, Group] = {}
        for todo in [i for i in todos if i["instance_id"] not in success_ids]:
            if (todo["instance_id"] not in failed_once):
                failed_once.add(todo["instance_id"])
                new_groups[todo["instance_id"]] = groups[todo["instance_id"]]
            else:
                give_up.add(todo["instance_id"])
                group = groups[todo["instance_id"]]
                if not (group["before"]+group["after"]):
                    continue
                new_group = split_commits_for_one_repo(group["before"]+group["after"])
                new_groups[new_group["medium"]["instance_id"]] = new_group

        exec_tasks: dict[tuple[str, str], tuple[str, SWEInstance, bool, Config]] = {}
        instance_group_mapping: dict[tuple[str, str], str] = {}
        base_commit_instance_mapping: DefaultDict[tuple[str, str], list[SWEInstance]] = defaultdict(list)
        for success_repo in success_repos:
            for is_after, instance in \
                [(False, i) for i in groups[success_repo["instance_id"]]["before"]]+\
                [(True, i) for i in groups[success_repo["instance_id"]]["after"]]:
                if instance["base_commit"].strip() == success_repo["base_commit"].strip():
                    all_success_instances.append(apply_res_for_same_commit(instance, success_repo))
                    continue
                exec_tasks[(instance["repo"], instance["base_commit"])] =(instance["base_commit"], success_repo, is_after, config)
                instance_group_mapping[(instance["repo"], instance["base_commit"])] = success_repo["instance_id"]+str(is_after)
                base_commit_instance_mapping[(instance["repo"], instance["base_commit"])].append(instance)
        not_applicable_instances: DefaultDict[str, list[SWEInstance]] = defaultdict(list)
        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            results = executor.map(
                lambda task: run_one_commit_test(task[0], task[1], task[2], task[3]),
                exec_tasks.values(),
            )
            for result, success in results:
                repo_commit_index = (result["repo"], result["base_commit"])
                if success:
                    for instance in base_commit_instance_mapping[repo_commit_index]:
                        all_success_instances.append(apply_res_for_same_commit(instance, result))
                else:
                    not_applicable_instances[
                        instance_group_mapping[repo_commit_index]
                    ].extend(base_commit_instance_mapping[repo_commit_index])
        groups_list = [split_commits_for_one_repo(sub_group) for sub_group in not_applicable_instances.values()]
        for new_group in groups_list:
            new_groups[new_group["medium"]["instance_id"]] = new_group

        groups = new_groups
        todos = [group["medium"] for group in groups.values()]
        todo_ids = [i["instance_id"] for i in todos]
        if not todo_ids:
            break

    save_res(config.workspace_root, all_success_instances)

    return

if __name__ == "__main__":
    Fire(main)