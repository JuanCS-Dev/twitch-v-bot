# HF Spaces Deploy Runbook (Oficial)

## Contexto validado

O histórico da Space `JuanCS-Dev/twitch-byte-bot` mostra que os deploys bem-sucedidos foram feitos via **Hugging Face Hub API** com commit:

- `Upload folder using huggingface_hub`

Referência recente validada:

- `37ee8954251cb62b05906eeb5d69ccd560375f86`

## Fluxo oficial de deploy

1. Gerar snapshot limpo do `HEAD` (apenas arquivos versionados).
2. Publicar snapshot na raiz da Space usando `HfApi().upload_folder(...)`.
3. Reiniciar runtime da Space com `HfApi().restart_space(...)`.
4. Validar commit remoto e status do runtime.

## Comandos (copiar e executar)

```bash
# 1) Snapshot limpo do commit atual
SNAPSHOT_DIR="$(mktemp -d /tmp/hf-deploy-snapshot.XXXXXX)"
git archive --format=tar HEAD | tar -xf - -C "$SNAPSHOT_DIR"

# 2) Upload + restart
SNAPSHOT_DIR="$SNAPSHOT_DIR" python - <<'PY'
import os
from huggingface_hub import HfApi

repo_id = "JuanCS-Dev/twitch-byte-bot"
snapshot_dir = os.environ["SNAPSHOT_DIR"]
api = HfApi()

api.upload_folder(
    repo_id=repo_id,
    repo_type="space",
    folder_path=snapshot_dir,
    path_in_repo=".",
    revision="main",
    commit_message="Upload folder using huggingface_hub",
)

api.restart_space(repo_id=repo_id)
runtime = api.get_space_runtime(repo_id=repo_id)
print(f"stage={runtime.stage} hardware={runtime.hardware} sleep_time={runtime.sleep_time}")
PY
```

## Validação pós-deploy

```bash
python - <<'PY'
from huggingface_hub import HfApi
api = HfApi()
commits = api.list_repo_commits(repo_id="JuanCS-Dev/twitch-byte-bot", repo_type="space")
print("latest:", commits[0].commit_id, "|", commits[0].title)
PY
```

## O que evitar (causa dor de cabeça)

- `git push hf main`: pode falhar com bloqueio de binários (`use xet`).
- `hf upload-large-folder` (na versão atual da CLI): falha em Space existente com erro de `space_sdk`.

## Regra prática

Para esta Space, considere **`upload_folder + restart_space`** como método padrão de release.
