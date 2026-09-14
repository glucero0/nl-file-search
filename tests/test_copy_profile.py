import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from copy_profile import copy_examples, profile_dir


def test_copy_examples_creates_and_does_not_overwrite(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert copy_examples(home=home) == 0
    dest = profile_dir(home)
    config = dest / "config.yaml"
    env = dest / ".env"
    assert config.is_file()
    assert env.is_file()
    assert "sources:" in config.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=" in env.read_text(encoding="utf-8")

    config.write_text("keep-config\n", encoding="utf-8")
    env.write_text("keep-env\n", encoding="utf-8")
    assert copy_examples(home=home) == 0
    assert config.read_text(encoding="utf-8") == "keep-config\n"
    assert env.read_text(encoding="utf-8") == "keep-env\n"
