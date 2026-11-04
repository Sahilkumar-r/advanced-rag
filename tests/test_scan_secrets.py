import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("scan_secrets", Path(__file__).resolve().parent.parent / "scripts" / "scan_secrets.py")
scan_secrets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_secrets)


def test_detects_key_shaped_strings_without_returning_the_value(tmp_path):
    f = tmp_path / "a.py"
    f.write_text('ok = 1\nkey = "gsk_' + "A" * 30 + '"\n')
    hits = scan_secrets.scan([f], root=tmp_path)
    assert hits == [("a.py", 2, "groq key")]
    assert "A" * 10 not in str(hits)


def test_clean_files_binary_files_and_short_lookalikes_are_ignored(tmp_path):
    clean = tmp_path / "b.md"
    clean.write_text("Set GROQ_API_KEY in your .env. Example prefix: gsk_xxx and sk-short\n")
    img = tmp_path / "c.png"
    img.write_bytes(b"gsk_" + b"A" * 40)
    assert scan_secrets.scan([clean, img], root=tmp_path) == []


def test_the_repository_itself_is_clean():
    assert scan_secrets.scan(scan_secrets.tracked()) == []
