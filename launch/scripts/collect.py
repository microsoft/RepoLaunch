import json
from pathlib import Path
from fire import Fire

def main(
    playground,
    output_jsonl,
    platform = "linux"
):
    playground = Path(playground)
    swe_instances = []
    for subfolder in playground.iterdir():
        if not subfolder.is_dir():
            continue

        instance_path = subfolder / "instance.json"
        result_path = subfolder / "result.json"

        if not instance_path.exists() or not result_path.exists():
            continue

        instance = json.loads(instance_path.read_text())
        result = json.loads(result_path.read_text())

        if not result["completed"]:
            continue
        
        swe_instance = {
            **instance,
            "setup_cmds": result["setup_commands"],
            "test_cmds": result["test_commands"],
            "log_parser": result.get("log_parser", "pytest"),
            "docker_image": result.get("docker_image", f"karinali20011210/migbench:{instance["instance_id"]}_{platform}"),
        }

        swe_instances.append(swe_instance)

    with open(output_jsonl, "w") as f:
        for instance in swe_instances:
            f.write(json.dumps(instance) + "\n")
    print(f"Saved {len(swe_instances)} instances to {output_jsonl}")

if __name__ == "__main__":
    Fire(main)