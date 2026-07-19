import sys

sys.path.insert(0, "/app/scripts")  # eval_config живёт в scripts/, не в пакете app

from eval_config import build_mlflow_tags, model_short, samples_cache_filename


def test_model_short_strips_provider_prefix():
    assert model_short("deepseek/deepseek-v4-flash") == "deepseek-v4-flash"
    assert model_short("qwen3:1.7b") == "qwen3:1.7b"


def test_cache_filename_differs_per_generator():
    # Регрессия бага B4: один source+mode, разные модели → РАЗНЫЕ файлы.
    a = samples_cache_filename("json", "dense", "qwen3.6-plus", 5)
    b = samples_cache_filename("json", "dense", "deepseek-v4-flash", 5)
    assert a != b
    assert a == "samples_json_dense_qwen3.6-plus_k5.json"


def test_cache_filename_differs_per_top_k():
    assert samples_cache_filename("json", "dense", "qwen3.6-plus", 5) != \
        samples_cache_filename("json", "dense", "qwen3.6-plus", 10)


def test_build_mlflow_tags_has_required_keys():
    tags = build_mlflow_tags(
        git_commit="abc123",
        dataset_version="golden_v1",
        judge_model="openai/gpt-5.4",
        purpose="b4-generator-selection",
        stage="1",
        langfuse_session_id="eval-dense-x",
    )
    assert set(tags) >= {"git_commit", "dataset_version", "judge", "purpose", "stage"}
    assert tags["judge"] == "openai/gpt-5.4"


def test_mean_valid_latency_skips_nan():
    from eval_config import mean_valid_latency
    import math
    assert mean_valid_latency([1.0, 2.0, float("nan"), 3.0]) == 2.0
    assert mean_valid_latency([float("nan")]) is None
    assert mean_valid_latency([]) is None
    assert mean_valid_latency([0.5]) == 0.5


def test_mean_valid_latency_all_valid():
    from eval_config import mean_valid_latency
    assert mean_valid_latency([1.0, 3.0]) == 2.0
