import sqlite3
from restored.chronos_backup_scavenger import discover_backups, extract_candidates, scavenge_directory


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE thoughts (id INTEGER PRIMARY KEY, content TEXT)")
    conn.execute("INSERT INTO thoughts(content) VALUES (?)", ("first lesson",))
    conn.execute("INSERT INTO thoughts(content) VALUES (?)", ("second lesson",))
    conn.commit(); conn.close()


def test_chronos_extracts_deterministic_candidates_without_memory_authority(tmp_path):
    db = tmp_path / "old.db"
    _make_db(db)
    before = db.read_bytes()
    r1 = extract_candidates(db, limit=8)
    r2 = extract_candidates(db, limit=8)
    assert r1["candidate_count"] == 2
    assert [x["candidate_id"] for x in r1["candidates"]] == [x["candidate_id"] for x in r2["candidates"]]
    assert r1["candidates"][0]["content"] == "first lesson"
    assert r1["candidates"][0]["status"] == "CANDIDATE_ONLY"
    assert r1["candidates"][0]["authority"]["injects_memory"] is False
    assert db.read_bytes() == before


def test_chronos_handles_missing_thoughts_table_and_directory_scan(tmp_path):
    good = tmp_path / "a.db"; _make_db(good)
    empty = tmp_path / "b.sqlite"
    conn = sqlite3.connect(empty); conn.execute("CREATE TABLE other (x TEXT)"); conn.commit(); conn.close()
    assert [p.name for p in discover_backups(tmp_path)] == ["a.db", "b.sqlite"]
    report = scavenge_directory(tmp_path, per_db_limit=4)
    assert report["backup_count"] == 2
    assert report["candidate_count"] == 2
    assert report["authority"]["injects_memory"] is False
    missing = extract_candidates(empty)
    assert "THOUGHTS_TABLE_ABSENT" in missing["findings"]
