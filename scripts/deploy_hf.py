#!/usr/bin/env python3
"""
IncidentOps - HuggingFace Spaces Deployment Script v15.0

Pushes the IncidentOps Docker image to a HuggingFace Space.

Usage:
    # Interactive (reads HF_TOKEN from environment or prompts)
    python scripts/deploy_hf.py

    # With explicit space ID
    python scripts/deploy_hf.py --space-id incidentops/incidentops

    # Dry run (validate everything without pushing)
    python scripts/deploy_hf.py --dry-run

Required env vars:
    HF_TOKEN - HuggingFace write token (from https://huggingface.co/settings/tokens)

The script:
1. Builds the Docker image locally
2. Tags it for HF Container Registry (ghcr.io/namespace/space_name:tag)
3. Pushes to HF Container Registry
4. Triggers HF Spaces rebuild via API
"""

import argparse
import os
import subprocess
import sys
import time


DEFAULT_SPACE = "incidentops/incidentops"
REGISTRY = "ghcr.io"

SPACE_REPO_MAP = {
    "incidentops/incidentops": "ghcr.io/incidentops/incidentops",
}


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, printing it first."""
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def build_image(tag: str, dockerfile: str = "Dockerfile") -> None:
    """Build the Docker image."""
    run(["docker", "build", "-t", tag, "-f", dockerfile, "."])


def tag_image(source: str, target: str) -> None:
    """Tag the Docker image for HF Container Registry."""
    run(["docker", "tag", source, target])


def push_image(target: str) -> None:
    """Push the Docker image to HF Container Registry."""
    run(["docker", "push", target])


def get_space_info(space_id: str, token: str) -> dict | None:
    """Fetch space info from HF Hub API."""
    try:
        from huggingface_hub import HfApi

        api = HfApi(token=token)
        return api.get_space_info(space_id)
    except Exception as e:
        print(f"[WARN] Could not fetch space info: {e}")
        return None


def trigger_rebuild(space_id: str, token: str, docker_repo: str, tag: str = "latest") -> None:
    """Trigger HF Spaces rebuild via API."""
    try:
        from huggingface_hub import HfApi

        api = HfApi(token=token)
        # Set the space's docker image
        api.upload_space_dockerfile(
            space_id=space_id,
            docker_repo=docker_repo,
            docker_image_tag=tag,
            exists_ok=True,
        )
        print(f"[OK] Triggered rebuild for {space_id} using {docker_repo}:{tag}")
    except Exception as e:
        print(f"[WARN] Could not trigger rebuild via API: {e}")
        print("  -> Space rebuild will be triggered automatically by HF when you push the image.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy IncidentOps to HuggingFace Spaces")
    parser.add_argument("--space-id", default=DEFAULT_SPACE, help="HF Space ID (e.g. incidentops/incidentops)")
    parser.add_argument("--tag", default="latest", help="Docker image tag (default: latest)")
    parser.add_argument("--dockerfile", default="Dockerfile", help="Path to Dockerfile")
    parser.add_argument("--dry-run", action="store_true", help="Validate without building/pushing")
    parser.add_argument("--skip-build", action="store_true", help="Skip Docker build (use existing image)")
    args = parser.parse_args()

    space_id = args.space_id
    tag = args.tag
    token = os.environ.get("HF_TOKEN", "").strip()

    if not token:
        print("[ERROR] HF_TOKEN environment variable not set.", file=sys.stderr)
        print("  Set it via: export HF_TOKEN=hf_...", file=sys.stderr)
        print("  Get a token at: https://huggingface.co/settings/tokens", file=sys.stderr)
        sys.exit(1)

    # Normalize space_id
    if "/" not in space_id:
        print(f"[ERROR] Space ID must be in format 'namespace/space_name', got: {space_id}", file=sys.stderr)
        sys.exit(1)

    # Compute registry target
    namespace = space_id.split("/", 1)[0]
    space_name = space_id.split("/", 1)[1]
    registry_repo = f"{REGISTRY}/{namespace}/{space_name}"
    full_target = f"{registry_repo}:{tag}"

    print("=" * 60)
    print(f"  IncidentOps HF Spaces Deployment")
    print("=" * 60)
    print(f"  Space ID   : {space_id}")
    print(f"  Target     : {full_target}")
    print(f"  Tag        : {tag}")
    print(f"  Dry run    : {args.dry_run}")
    print(f"  Skip build : {args.skip_build}")
    print("=" * 60)

    # Validate: check if space exists (read-only check, no auth needed for info)
    print(f"\n[1/4] Validating space {space_id}...")
    info = get_space_info(space_id, token)
    if info is None:
        print(f"[ERROR] Cannot access space {space_id}. Does it exist and do you have write access?", file=sys.stderr)
        print("  Make sure to create the Space first at: https://huggingface.co/new-space", file=sys.stderr)
        print("  Select 'Docker' as the SDK and set the hardware to 'CPU basic' or 'T4 small'.", file=sys.stderr)
        sys.exit(1)
    print(f"[OK] Space exists: {info.id} (sdk={info.sdk})")

    # Check Docker
    print("\n[2/4] Checking Docker...")
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        print(f"[OK] {result.stdout.strip()}")
    except FileNotFoundError:
        print("[ERROR] Docker not found. Is Docker installed and in PATH?", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("\n[OK] Dry run complete. No changes made.")
        return

    # Build
    if args.skip_build:
        print("\n[3/4] Skipping Docker build (--skip-build set).")
    else:
        print(f"\n[3/4] Building Docker image as incidentops:{tag}...")
        build_image(f"incidentops:{tag}", args.dockerfile)
        print("[OK] Docker image built.")

        print(f"\n[3.5/4] Tagging image for HF Container Registry...")
        tag_image(f"incidentops:{tag}", full_target)
        print(f"[OK] Tagged as {full_target}.")

    # Push
    print(f"\n[4/4] Pushing {full_target} to HF Container Registry...")
    print("  (This may take 5-10 minutes on first push)")
    push_image(full_target)
    print("[OK] Image pushed.")

    # Trigger rebuild
    print(f"\n[Bonus] Triggering space rebuild...")
    trigger_rebuild(space_id, token, registry_repo, tag)

    print("\n" + "=" * 60)
    print(f"  Deployment triggered!")
    print("=" * 60)
    print(f"  Check your space at: https://huggingface.co/spaces/{space_id}")
    print(f"  Build logs: https://huggingface.co/spaces/{space_id}/settings")
    print("=" * 60)
    print("\nNote: HF Spaces may take 3-5 minutes to rebuild the image.")
    print("      The space will be available at the URL above once ready.")


if __name__ == "__main__":
    main()
