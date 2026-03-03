#!/bin/bash
set -e
SNAPSHOT_DIR="$(mktemp -d /tmp/hf-deploy-snapshot.XXXXXX)"
git archive --format=tar HEAD | tar -xf - -C "$SNAPSHOT_DIR"

SNAPSHOT_DIR="$SNAPSHOT_DIR" python3 - <<'PY'
import os
from huggingface_hub import HfApi

repo_id = "JuanCS-Dev/twitch-byte-bot"
snapshot_dir = os.environ["SNAPSHOT_DIR"]
api = HfApi()

print(f"Uploading snapshot from {snapshot_dir} to {repo_id}...")
api.upload_folder(
    repo_id=repo_id,
    repo_type="space",
    folder_path=snapshot_dir,
    path_in_repo=".",
    revision="main",
    commit_message="Deploying CLI completion and HF Token auth support",
)

print("Restarting space...")
api.restart_space(repo_id=repo_id)
runtime = api.get_space_runtime(repo_id=repo_id)
print(f"stage={runtime.stage} hardware={runtime.hardware}")
PY

rm -rf "$SNAPSHOT_DIR"
echo "Deploy triggered successfully."
