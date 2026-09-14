from pathlib import Path

import pytest
import yaml

from nl_file_search.config import load_config, normalize_windows_paths_in_yaml

# Python string with single backslashes — the common Windows config mistake.
_UNESCAPED_USERS = 'sources:\n  - path: "C:\\Users\\gluce\\Notes\\Notes"\n'
_UNESCAPED_TEMP = 'sources:\n  - path: "D:\\temp"\n'
_ESCAPED_USERS = 'sources:\n  - path: "C:\\\\Users\\\\you\\\\Pictures"\n'


def test_pyyaml_rejects_unescaped_users_path() -> None:
    with pytest.raises(yaml.YAMLError, match="escape sequence"):
        yaml.safe_load(_UNESCAPED_USERS)


def test_normalize_unescaped_users_path() -> None:
    fixed = normalize_windows_paths_in_yaml(_UNESCAPED_USERS)
    loaded = yaml.safe_load(fixed)
    assert loaded["sources"][0]["path"] == "C:/Users/gluce/Notes/Notes"


def test_normalize_temp_path_does_not_become_tab() -> None:
    # Without the rewrite, YAML turns \t in \temp into a tab character.
    corrupted = yaml.safe_load(_UNESCAPED_TEMP)
    assert corrupted["sources"][0]["path"] == "D:" + "\t" + "emp"
    fixed = normalize_windows_paths_in_yaml(_UNESCAPED_TEMP)
    loaded = yaml.safe_load(fixed)
    assert loaded["sources"][0]["path"] == "D:/temp"


def test_normalize_leaves_already_escaped_paths() -> None:
    assert normalize_windows_paths_in_yaml(_ESCAPED_USERS) == _ESCAPED_USERS
    loaded = yaml.safe_load(_ESCAPED_USERS)
    assert loaded["sources"][0]["path"] == r"C:\Users\you\Pictures"


def test_normalize_leaves_non_path_escapes() -> None:
    text = 'message: "hello\\nworld"\n'
    assert normalize_windows_paths_in_yaml(text) == text
    assert yaml.safe_load(text)["message"] == "hello\nworld"


def test_load_config_accepts_unescaped_windows_path(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(_UNESCAPED_USERS, encoding="utf-8")
    cfg = load_config(path=cfg_file)
    assert len(cfg.sources) == 1
    assert "gluce" in cfg.sources[0].parts or "gluce" in str(cfg.sources[0])


def test_load_config_accepts_local_unescaped_path(tmp_path: Path) -> None:
    folder = tmp_path / "Notes"
    folder.mkdir()
    yaml_text = f'sources:\n  - path: "{folder}"\n'
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml_text, encoding="utf-8")
    cfg = load_config(path=cfg_file)
    assert cfg.sources[0] == folder.resolve()


def test_load_config_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "config.yaml"
    with pytest.raises(ValueError, match="does not create"):
        load_config(path=missing)


def test_load_config_single_quoted_windows_path(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("sources:\n  - path: 'C:\\Users\\you\\Notes'\n", encoding="utf-8")
    cfg = load_config(path=cfg_file)
    assert len(cfg.sources) == 1
    assert "you" in cfg.sources[0].parts or "you" in str(cfg.sources[0])
