from fire import Fire
import time
import json
import docker
import requests
from rich.console import Console
from rich.progress import Progress
from rich import print as rprint

MAX_IMAGE_SIZE = 80 # GB

def verify_on_dockerhub(push_name: str, retries: int = 3, backoff: float = 10.0) -> bool:
    if ":" in push_name.rsplit("/", 1)[-1]:
        repo, tag = push_name.rsplit(":", 1)
    else:
        repo, tag = push_name, "latest"
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}/"
    delay = backoff
    for _ in range(retries):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
        except requests.RequestException:
            time.sleep(delay)
            delay *= 2
    return False


def main(dataset: str,
        clear_after_push: str):
    console = Console()
    client = docker.from_env()
    
    with open(dataset, "r") as f:
        instances = [json.loads(line) for line in f]

    existing_images: set[str] = set()
    for img in client.images.list():
        if img.tags:
            existing_images.update(img.tags)
    
    with Progress() as progress:
        task = progress.add_task("Pushing images...", total=len(instances))
        
        for instance in instances:
            image_key = instance["docker_image"]
            
            if image_key not in existing_images:
                rprint(f"[yellow]Warning: Image {image_key} not found locally[/yellow]")
                progress.advance(task)
                continue
            
            try:
                image = client.images.get(image_key)
                if image.attrs.get("Size", 0) > MAX_IMAGE_SIZE * 1024 ** 3:
                    rprint(f"[yellow]Image size {image_key}> {MAX_IMAGE_SIZE}GB, skip")
                    progress.advance(task)
                    continue
                rprint(f"[blue]Pushing {image_key}[/blue]")

                resp: list[dict[str, str]] = client.images.push(image_key, stream=True, decode=True)
                push_error = None
                for line in resp:
                    if "error" in line:
                        push_error = line["error"]
                        break
                if push_error is not None:
                    rprint(f"[red]Error pushing {image_key}: {push_error}[/red]")
                    progress.advance(task)
                    continue
                if not verify_on_dockerhub(image_key):
                    rprint(f"[red]Error pushing {image_key}: not found on Docker Hub after push, skipping[/red]")
                    progress.advance(task)
                    continue
                rprint(f"[green]Successfully pushed {image_key}[/green]")
            except Exception as e:
                rprint(f"[red]Error pushing {image_key}: {str(e)}[/red]")
            try:
                if int(clear_after_push):
                    client.images.remove(image_key)
                    rprint(f"[green]Successfully cleared {image_key}[/green]")
            except Exception as e:
                rprint(f"[red]Error clearing {image_key}: {str(e)}[/red]")
            
            progress.advance(task)

if __name__ == "__main__":
    Fire(main)
