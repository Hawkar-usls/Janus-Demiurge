"""JANUS database buffer lock regression. Synthetic SQLite files ONLY.

The production module is imported with its config dependency pointed at a
temporary directory, never the owner's personal Janus database.
"""
import importlib
from contextlib import closing
import pathlib
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

COLUMNS=(
 "timestamp TEXT, gpu_load REAL, gpu_temp REAL, cpu_load REAL, "
 "cache_ratio REAL, igpu_load REAL, android_mag REAL, android_loss REAL, "
 "android_entropy REAL, audio_volume REAL, audio_spectrum TEXT, "
 "user_active INTEGER, top_processes TEXT, audio_active_inputs INTEGER, "
 "audio_active_outputs INTEGER, audio_avg_output_volume REAL, "
 "audio_device_changes_count INTEGER"
)

def new_module(tmp):
    dummy=types.ModuleType("config")
    dummy.RAW_LOGS_DIR=tmp
    with patch.dict(sys.modules,{"config":dummy}):
        sys.modules.pop("janus_db",None)
        return importlib.import_module("janus_db")

def prepare_db(file):
    with closing(sqlite3.connect(file)) as conn:
        conn.execute("CREATE TABLE system_metrics ("+COLUMNS+")")

def fake_metrics(index):
    return (str(index),)+tuple(float(index%10) for _ in range(16))

class BufferedMetricsTests(unittest.TestCase):
    def test_threshold_flush_releases_lock(self):
        with tempfile.TemporaryDirectory() as root:
            db=str(pathlib.Path(root)/"synthetic.db")
            prepare_db(db)
            module=new_module(root)
            module.BUFFER_SIZE=2
            buffer=module.DatabaseBuffer(db)
            done=threading.Event()
            def worker():
                buffer.add("",fake_metrics(0))
                buffer.add("",fake_metrics(1))
                done.set()
            thread=threading.Thread(target=worker,daemon=True)
            thread.start()
            self.assertTrue(done.wait(4),"ADD_SELF_DEADLOCK")
            with closing(sqlite3.connect(db)) as conn:
                count=conn.execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0]
            self.assertEqual(count,2)

    def test_parallel_producers_keep_all_records(self):
        with tempfile.TemporaryDirectory() as root:
            db=str(pathlib.Path(root)/"synthetic.db")
            prepare_db(db)
            module=new_module(root)
            module.BUFFER_SIZE=7
            buffer=module.DatabaseBuffer(db)
            workers=[]
            for shift in range(4):
                t=threading.Thread(target=lambda n=shift: [
                  buffer.add("",fake_metrics(n*100+i)) for i in range(27)],
                  daemon=True)
                workers.append(t)
                t.start()
            for t in workers:
                t.join(timeout=8)
                self.assertFalse(t.is_alive(),"PARALLEL_ADD_HANG")
            buffer.flush()
            with closing(sqlite3.connect(db)) as conn:
                count=conn.execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0]
            self.assertEqual(count,108)
            self.assertEqual(buffer._size,0)

    def test_error_preserves_buffer_then_manual_retry(self):
        with tempfile.TemporaryDirectory() as root:
            module=new_module(root)
            module.BUFFER_SIZE=2
            failed=str(pathlib.Path(root)/"missing"/"bad.db")
            good=str(pathlib.Path(root)/"synthetic.db")
            buffer=module.DatabaseBuffer(failed)
            buffer.add("",fake_metrics(0))
            buffer.add("",fake_metrics(1))
            self.assertEqual(buffer._size,2)
            prepare_db(good)
            buffer.db_path=good
            buffer.flush()
            self.assertEqual(buffer._size,0)
            with closing(sqlite3.connect(good)) as conn:
                count=conn.execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0]
            self.assertEqual(count,2)

if __name__=="__main__":
    unittest.main()
