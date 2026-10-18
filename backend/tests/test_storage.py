import uuid
from pathlib import Path

import pandas as pd
import pytest
from app.config import get_settings
from app.storage import (
    get_data_dir,
    get_dataset_parquet_path,
    get_parquet_dir,
    get_relative_parquet_key,
    validate_dataset_id,
    verify_dataset_parquet_exists,
)


def test_storage_paths_deterministic(tmp_path, monkeypatch):
    test_dir = str(tmp_path / "custom_data")
    monkeypatch.setenv("DATA_DIR", test_dir)
    get_settings.cache_clear()

    dataset_id = str(uuid.uuid4())
    data_dir = get_data_dir()
    parquet_dir = get_parquet_dir()
    dataset_parquet = get_dataset_parquet_path(dataset_id)

    assert str(data_dir) == str(Path(test_dir).resolve())
    assert str(parquet_dir) == str(Path(test_dir).resolve() / "parquet")
    assert str(dataset_parquet) == str(
        Path(test_dir).resolve() / "parquet" / dataset_id / "data.parquet"
    )

    get_settings.cache_clear()


def test_path_traversal_prevented():
    with pytest.raises(ValueError):
        validate_dataset_id("../../etc/passwd")

    with pytest.raises(ValueError):
        validate_dataset_id("../some_other_folder")


def test_verify_dataset_parquet_exists(tmp_path, monkeypatch):
    test_dir = str(tmp_path / "test_data_verify")
    monkeypatch.setenv("DATA_DIR", test_dir)
    get_settings.cache_clear()

    dataset_id = str(uuid.uuid4())

    # 1. Before creation: missing
    exists, reason = verify_dataset_parquet_exists(dataset_id)
    assert not exists
    assert "missing" in reason.lower()

    # 2. After empty file creation: empty
    parquet_path = get_dataset_parquet_path(dataset_id)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.touch()

    exists, reason = verify_dataset_parquet_exists(dataset_id)
    assert not exists
    assert "empty" in reason.lower()

    # 3. After real parquet write: valid
    df = pd.DataFrame({"billed_cost": [10.0, 20.0]})
    df.to_parquet(parquet_path, engine="pyarrow")

    exists, reason = verify_dataset_parquet_exists(dataset_id)
    assert exists
    assert reason is None

    get_settings.cache_clear()


def test_relative_parquet_key():
    dataset_id = str(uuid.uuid4())
    key = get_relative_parquet_key(dataset_id)
    assert key == f"parquet/{dataset_id}/data.parquet"
