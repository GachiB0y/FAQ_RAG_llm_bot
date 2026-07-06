---
name: tracking-experiments-with-mlflow
description: Use when logging, naming, or reviewing MLflow experiment runs — running evals, comparing model/retrieval configurations, or deciding what to log so results stay reproducible and reviewable later.
---

# Tracking Experiments with MLflow

## Overview

A run is reviewable months later only if the **name is short**, the **config is in
params**, the **filter keys are in tags**, and the **conclusion is in the note**.
The common failure: cramming every detail into `run_name` and omitting
reproducibility tags — this produces names like
`clean-hybrid-nemotron-3-super-120b-judge-gpt-oss-120b-k5` that can't be filtered
or reproduced.

## The split: name / params / tags / metrics

| Slot | Holds | Example |
|---|---|---|
| **run_name** | short human label — the ONE thing that differs | `hybrid-k5` |
| **params** | full config to reproduce (fixed inputs) | `chunk_size=512`, `top_k=5`, models |
| **tags** | filter/group keys + reproducibility | `git_commit`, `dataset_version`, `purpose` |
| **metrics** | measured numbers | `mean_faithfulness=0.9` |
| **note** | the conclusion in plain words | "hybrid worse on recall, don't ship" |

Do NOT put models/k/dataset into the name — those go in params/tags so the UI can
filter (`params.retrieval_mode = 'hybrid'`) and group them.

## Mandatory on every run (checklist)

- [ ] Short `run_name` (`hybrid-k5`, not a slug of every parameter)
- [ ] Tag `git_commit` — else the run is not reproducible
- [ ] Tag `dataset_version` — what data/testset it ran on
- [ ] Tag `purpose` — one phrase: why this run exists
- [ ] All `params` needed to re-run (models, chunk_size, top_k, dataset_size)
- [ ] Metrics with clear names (`mean_faithfulness`, not `m1`)
- [ ] Artifact: per-item results file (CSV)
- [ ] After analysis: write the conclusion into `mlflow.note.content`

## Example

```python
import subprocess, mlflow

git = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()

mlflow.set_experiment("rag-eval")                      # meaningful, not "test"
with mlflow.start_run(run_name="hybrid-k5"):           # short: the differentiator
    mlflow.log_params({                                # reproduce
        "retrieval_mode": "hybrid", "top_k": 5, "chunk_size": 512,
        "generator_model": "nemotron-3-super-120b",
        "judge_model": "gpt-oss-120b", "embedding_model": "bge-m3",
        "dataset_size": 15,
    })
    mlflow.set_tags({                                  # filter + reproducibility
        "git_commit": git, "dataset_version": "testset_v2",
        "purpose": "hybrid vs dense baseline",
    })
    mlflow.log_metric("mean_faithfulness", 0.895)      # measure (mean_ prefix)
    mlflow.log_artifact("eval_results.csv")
    mlflow.set_tag("mlflow.note.content", "Hybrid ниже dense по recall. Не внедряем.")
```

## Parameter sweeps → parent/child runs

Sweeping one axis (top_k = 3,5,10)? Nest children under one parent so the UI groups them:

```python
with mlflow.start_run(run_name="topk-sweep") as parent:
    for k in (3, 5, 10):
        with mlflow.start_run(run_name=f"k{k}", nested=True):
            ...  # eval with top_k=k
```

## Reviewing / comparing

- Filter by a tag first (`tags.dataset_version = 'testset_v2'`) so you compare like with like.
- Select 2+ runs → **Compare** → parallel-coordinates / delta table.
- **Only compare runs that share the same dataset AND the same judge.** Changing
  the judge or the testset alongside the thing under test invalidates the comparison.

## Common mistakes

| Mistake | Fix |
|---|---|
| Everything crammed into `run_name` | short name; details → params/tags |
| No `git_commit` tag | can't reproduce → always tag it |
| Comparing runs with different judge/dataset | change ONE variable; keep judge+dataset fixed |
| Metric 0.99–1.00 taken at face value | red flag — usually a broken eval (biased judge / leak) |
| Copying an existing messy convention | don't inherit bad naming; apply this split |

## Real-world impact

In this project the first experiment showed hybrid "winning" by +51% — an artifact
of a biased judge and a noisy corpus. Proper run hygiene (independent judge tagged,
dataset version tracked, conclusion in note) made the regression visible on re-run.
Full write-up: `docs/plans/2026-07-06-mlflow-working-conventions.md`.
