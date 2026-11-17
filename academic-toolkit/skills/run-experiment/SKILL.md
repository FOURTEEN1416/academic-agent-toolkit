---
name: run-experiment
description: "Deploy and run ML experiments on local or remote GPU servers. Use when user says 'run experiment', 'deploy to server', or 'start training'."
argument-hint: [experiment-description]
allowed-tools: Bash(*), Read, Grep, Glob, Edit, Write, Agent
---

# Run Experiment

Deploy and run ML experiment: $ARGUMENTS

## Workflow

### Step 1: Detect Environment

Read the project's `AGENTS.md` to determine the experiment environment:

- **Local GPU**: Look for local CUDA/MPS setup info
- **Remote server**: Look for SSH alias, conda env, code directory

If no server info is found in `AGENTS.md`, check environment variables (e.g., `$GPU_SERVER`). If still unavailable, log "No server configuration found — running locally if GPU is available, otherwise report the issue" and attempt local execution.

**Environment reuse first.** Read the project's existing server notes before preparing anything: reuse the user's confirmed conda/venv, remote code directory and working invocation. A missing environment ledger is missing bookkeeping, not evidence of a broken environment — do not rebuild a working setup. When no relevant validation is recorded, run one small task-relevant smoke in that environment (exercise the needed imports/kernel, input paths and output writing) and record the command and observed output. Reuse that validation while the environment and execution path stay unchanged; require a fresh spec + import/kernel check + one verbatim documented-invocation pass only for new or rebuilt environments and after substantive install/invocation changes. Prose or log edits alone never trigger a rebuild or recheck, and passing the smoke does not certify the scientific result.

**Preparation failures are not code bugs.** Carry the same failure, attempted fixes and remaining budget across child skills in the existing run notes/tracker. After two targeted repairs to the same environment problem make no new progress, stop repeating preparation and return the exact command and error to the main owner for takeover or an authorized alternative. Missing permissions, authentication, network access or a compatible driver are environment prerequisites — never reasons to rewrite the training script. The code-sanity retry budget and reviewer gates below stay intact.

### Step 2: Pre-flight Check

Check GPU availability on the target machine:

**Remote:**
```bash
ssh <server> nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader
```

**Local:**
```bash
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader
# or for Mac MPS:
python -c "import torch; print('MPS available:', torch.backends.mps.is_available())"
```

Free GPU = memory.used < 500 MiB.

### Step 3: Sync Code (Remote Only)

Check the project's `AGENTS.md` for a `code_sync` setting. If not specified, default to `rsync`.

#### Option A: rsync (default)

Prefer the project's existing deployment command or an explicit file list. Otherwise allow directory traversal and include the configuration/small resources the actual experiment command reads, alongside Python sources:

```bash
rsync -avz --prune-empty-dirs \
  --exclude='.*' --exclude='__pycache__/' --exclude='/venv/' --exclude='/env/' \
  --exclude='data/' --exclude='datasets/' --exclude='weights/' \
  --exclude='checkpoints/' --exclude='outputs/' --exclude='wandb/' \
  --include='*/' --include='*.py' \
  --include='/configs/sanity.json' --include='/assets/vocab.json' \
  --exclude='*' <local_src>/ <server>:<remote_dst>/
```

Replace the two explicit config/resource paths with those your command needs and add other required small files explicitly. Keep exclusions before directory/file includes, and put project-specific private paths in the excludes. Hidden agent/config files, data, weights and outputs stay out; sync from the project source root, never the user's home directory, and never replace these rules with an unfiltered copy. A successful sync exit is not a launch check: run the smallest actual experiment from the configured remote code directory and inspect its log and result file.

#### Option B: git (when `code_sync: git` is set in AGENTS.md)

Push local changes to remote repo, then pull on the server:
```bash
# 1. Push from local — add explicit paths only (code, scripts, configs you changed).
#    Follow the git governance rules of the repo you are working in: in repos with
#    L1 audit hooks (e.g. academic-toolkit), `git add .` / `-A` / `--all` are denied (exit 2).
git add src/ scripts/ train.py && git commit -m "sync: experiment deployment" && git push

# 2. Pull on server
ssh <server> "cd <remote_dst> && git pull"
```

Benefits: version-tracked, multi-server sync with one push, no rsync include/exclude rules needed.

### Step 3.5: W&B Integration (when `wandb: true` in AGENTS.md)

**Skip this step entirely if `wandb` is not set or is `false` in AGENTS.md.**

Before deploying, ensure the experiment scripts have W&B logging:

1. **Check if wandb is already in the script** — look for `import wandb` or `wandb.init`. If present, skip to Step 4.

2. **If not present, add W&B logging** to the training script:
   ```python
   import wandb
   wandb.init(project=WANDB_PROJECT, name=EXP_NAME, config={...hyperparams...})

   # Inside training loop:
   wandb.log({"train/loss": loss, "train/lr": lr, "step": step})

   # After eval:
   wandb.log({"eval/loss": eval_loss, "eval/ppl": ppl, "eval/accuracy": acc})

   # At end:
   wandb.finish()
   ```

3. **Metrics to log** (add whichever apply to the experiment):
   - `train/loss` — training loss per step
   - `train/lr` — learning rate
   - `eval/loss`, `eval/ppl`, `eval/accuracy` — eval metrics per epoch
   - `gpu/memory_used` — GPU memory (via `torch.cuda.max_memory_allocated()`)
   - `speed/samples_per_sec` — throughput
   - Any custom metrics the experiment already computes

4. **Verify wandb login on the target machine:**
   ```bash
   ssh <server> "wandb status"  # should show logged in
   # If not logged in:
   ssh <server> "wandb login <WANDB_API_KEY>"
   ```

> The W&B project name and API key come from `AGENTS.md` (see example below). The experiment name is auto-generated from the script name + timestamp.

### Step 4: Deploy

#### Remote (via SSH + screen)

For each experiment, create a dedicated screen session with GPU binding:
```bash
ssh <server> "screen -dmS <exp_name> bash -c '\
  eval \"\$(<conda_path>/conda shell.bash hook)\" && \
  conda activate <env> && \
  CUDA_VISIBLE_DEVICES=<gpu_id> python <script> <args> 2>&1 | tee <log_file>'"
```

#### Local

```bash
# Linux with CUDA
CUDA_VISIBLE_DEVICES=<gpu_id> python <script> <args> 2>&1 | tee <log_file>

# Mac with MPS (PyTorch uses MPS automatically)
python <script> <args> 2>&1 | tee <log_file>
```

For local long-running jobs, use `run_in_background: true` to keep the conversation responsive.

### Step 5: Verify Launch

**Remote:**
```bash
ssh <server> "screen -ls"
```

**Local:**
Check process is running and GPU is allocated.

### Step 6: Feishu Notification (if configured)

After deployment is verified, check the project's notification configuration (e.g., the Feishu/webhook config file agreed in the project's `AGENTS.md`, if any):
- Send `experiment_done` notification: which experiments launched, which GPUs, estimated time
- If config absent or mode `"off"`: skip entirely (no-op)

## Key Rules

- ALWAYS check GPU availability first — never blindly assign GPUs
- Each experiment gets its own screen session + GPU (remote) or background process (local)
- Use `tee` to save logs for later inspection
- Run deployment commands with `run_in_background: true` to keep conversation responsive
- Report back: which GPU, which screen/process, what command, estimated time
- If multiple experiments, launch them in parallel on different GPUs

## AGENTS.md Example

Users should add their server info to their project's `AGENTS.md`:

```markdown
## Remote Server
- SSH: `ssh my-gpu-server`
- GPU: 4x A100 (80GB each)
- Conda: `eval "$(/opt/conda/bin/conda shell.bash hook)" && conda activate research`
- Code dir: `/home/user/experiments/`
- code_sync: rsync          # default. Or set to "git" for git push/pull workflow
- wandb: false              # set to "true" to auto-add W&B logging to experiment scripts
- wandb_project: my-project # W&B project name (required if wandb: true)
- wandb_entity: my-team     # W&B team/user (optional, uses default if omitted)

## Local Environment
- Mac MPS / Linux CUDA
- Conda env: `ml` (Python 3.10 + PyTorch)
```

> **W&B setup**: Run `wandb login` on your server once (or set `WANDB_API_KEY` env var). The skill reads project/entity from AGENTS.md and adds `wandb.init()` + `wandb.log()` to your training scripts automatically. Dashboard: `https://wandb.ai/<entity>/<project>`.
