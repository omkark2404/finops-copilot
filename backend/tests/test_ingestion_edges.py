"""Preflight checks must reject malformed input before expensive data loading."""

import pandas as pd
import pytest
from app.ingestion import normalize_to_canonical, read_focus_file
from app.schemas import FocusVersion


def forbidden_load(*args, **kwargs):
    pytest.fail("Data loading was reached before the invalid schema was rejected")


def test_wide_csv_rejected_before_pandas(tmp_path, monkeypatch):
    path = tmp_path / "wide.csv"
    path.write_text(",".join(f"c{i}" for i in range(201)) + "\n" + ",".join(["1"] * 201))
    monkeypatch.setattr(pd, "read_csv", forbidden_load)
    with pytest.raises(ValueError, match="200 input columns"):
        read_focus_file(str(path))


def test_wide_parquet_rejected_before_pandas(tmp_path, monkeypatch):
    path = tmp_path / "wide.parquet"
    pd.DataFrame({f"c{i}": [1] for i in range(201)}).to_parquet(path)
    monkeypatch.setattr(pd, "read_parquet", forbidden_load)
    with pytest.raises(ValueError, match="200 input columns"):
        read_focus_file(str(path))


@pytest.mark.parametrize("header", ["BilledCost,billed_cost", "BilledCost,BilledCost"])
def test_csv_column_collision_rejected_before_pandas(tmp_path, monkeypatch, header):
    path = tmp_path / "collision.csv"
    path.write_text(header + "\n1,2\n")
    monkeypatch.setattr(pd, "read_csv", forbidden_load)
    with pytest.raises(ValueError, match="conflicting column names"):
        read_focus_file(str(path))


def test_parquet_alias_collision_rejected_before_loading(tmp_path, monkeypatch):
    path = tmp_path / "collision.parquet"
    pd.DataFrame({"BilledCost": [1.0], "billed_cost": [2.0]}).to_parquet(path)
    monkeypatch.setattr(pd, "read_parquet", forbidden_load)
    with pytest.raises(ValueError, match="conflicting column names"):
        read_focus_file(str(path))


def test_direct_normalization_rejects_alias_collision():
    with pytest.raises(ValueError, match="conflicting column names"):
        normalize_to_canonical(
            pd.DataFrame({"BilledCost": [1.0], "billed_cost": [2.0]}), FocusVersion.v1_0
        )


def test_excess_fields_in_data_row_rejected_before_pandas(tmp_path, monkeypatch):
    path = tmp_path / "ragged.csv"
    path.write_text("a,b\n" + ",".join(["1"] * 10000))
    monkeypatch.setattr(pd, "read_csv", forbidden_load)
    with pytest.raises(ValueError, match="same number of fields"):
        read_focus_file(str(path))


def test_oversized_multiline_header_rejected_before_pandas(tmp_path, monkeypatch):
    path = tmp_path / "header.csv"
    path.write_text('"' + ("a\n" * 40000) + '"\n1\n')
    monkeypatch.setattr(pd, "read_csv", forbidden_load)
    with pytest.raises(ValueError, match="character limit"):
        read_focus_file(str(path))


def test_quoted_commas_newlines_and_bom_still_parse(tmp_path):
    path = tmp_path / "quoted.csv"
    path.write_text('\ufeffname,cost\n"hello,\nworld",1\n\n', encoding="utf8")
    frame = read_focus_file(str(path))
    assert frame.shape == (1, 2)
    assert frame.iloc[0]["name"] == "hello,\nworld"
