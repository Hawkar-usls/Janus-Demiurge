#!/usr/bin/env python3
import argparse, hashlib, json, os, shutil, subprocess, sys, tarfile, time
from pathlib import Path

PORTABLE_MONITOR = r'''\
import time
class CacheProbe:
    def get_metrics(self): return {"ratio": 1.0, "latency": 0.0}
    def stop(self): pass
class SystemMonitor:
    def __init__(self, poll_interval=1.0, audio_device=None, screen_interval=1.0, top_n=5):
        self.cache_probe = CacheProbe()
        self.screen_monitor = None
        self._metrics = {
            "timestamp": time.time(), "gpu": [{}], "igpu": {"load": 0.0}, "cache": {"ratio": 1.0},
            "cpu": {"percent_total": 0.0}, "memory": {}, "disk": [], "network": {},
            "audio_spectrum": [], "keyboard": {}, "mouse": {}, "screen": {}, "top_processes": [],
            "gaming_mode": False, "games": [], "game_name": None, "game_cpu": 0.0, "game_mem": 0.0,
            "game_gpu": 0.0, "predicted": {}, "cpu_temperature": 40.0,
            "hardware_entropy": {"stability_score": 1.0, "timing_jitter": 0.0},
            "temp_f": 104.0, "hw_entropy": 0.005, "purity_score": 0.0, "tachyonic_mode": "CI_PORTABLE",
            "load_scale": 1.0,
        }
    def get_current_metrics(self): return dict(self._metrics)
    def get_game_fps(self): return 0.0
    def stop(self): pass
'''

SITECUSTOMIZE = r'''\
import socket
_orig_connect = socket.socket.connect
_orig_create_connection = socket.create_connection

def _allowed(addr):
    try: host = addr[0]
    except Exception: return False
    return host in ("127.0.0.1", "localhost", "::1")

def _guard_connect(self, address):
    if not _allowed(address):
        raise OSError("JANUS_LEGACY_CI: outbound network disabled")
    return _orig_connect(self, address)

def _guard_create_connection(address, *a, **kw):
    if not _allowed(address):
        raise OSError("JANUS_LEGACY_CI: outbound network disabled")
    return _orig_create_connection(address, *a, **kw)

socket.socket.connect = _guard_connect
socket.create_connection = _guard_create_connection
'''

AIOSQLITE_STUB = r'''\
class _Unavailable:
    def __call__(self, *a, **k):
        raise RuntimeError("aiosqlite disabled in bounded legacy CI")
connect = _Unavailable()
'''

def sha256(p: Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024), b''): h.update(c)
    return h.hexdigest()

def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"compat patch anchor missing: {label}")
    return text.replace(old, new, 1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--bundle', required=True)
    ap.add_argument('--out-dir', default='legacy_v5_22_run')
    ap.add_argument('--max-cycles', type=int, default=1)
    ap.add_argument('--timeout', type=int, default=600)
    a=ap.parse_args()
    if not 1 <= a.max_cycles <= 3:
        raise SystemExit('max-cycles must be between 1 and 3')
    bundle=Path(a.bundle).resolve(); out=Path(a.out_dir).resolve(); out.mkdir(parents=True,exist_ok=True)
    stage=out/'source'; work=out/'work'; runtime=out/'runtime'
    for d in [stage,work,runtime]:
        if d.exists(): shutil.rmtree(d)
        d.mkdir(parents=True)
    with tarfile.open(bundle,'r:gz') as tf:
        tf.extractall(stage)
    manifest=json.loads((stage/'LEGACY_SNAPSHOT_MANIFEST.json').read_text('utf-8'))
    mismatches=[]
    for rec in manifest['files']:
        p=stage/rec['path']
        if not p.exists() or sha256(p)!=rec['sha256']: mismatches.append(rec['path'])
    if mismatches: raise SystemExit('manifest mismatch: '+repr(mismatches[:10]))
    shutil.copytree(stage,work,dirs_exist_ok=True)
    transforms=[]
    (work/'system_monitor.py').write_text(PORTABLE_MONITOR,'utf-8'); transforms.append('system_monitor.py -> portable read-only metrics stub')
    (work/'aiosqlite.py').write_text(AIOSQLITE_STUB,'utf-8'); transforms.append('aiosqlite.py -> disabled import stub')
    (work/'sitecustomize.py').write_text(SITECUSTOMIZE,'utf-8'); transforms.append('sitecustomize.py -> outbound network deny membrane')
    corep=work/'core.py'; core=corep.read_text('utf-8')
    core=replace_once(core, '    try:\n        while True:\n',
                      '    legacy_ci_max_cycles = int(os.environ.get("JANUS_LEGACY_MAX_CYCLES", "0"))\n    legacy_ci_cycles = 0\n\n    try:\n        while True:\n', 'core loop preamble')
    core=replace_once(core, '                patcher.update()\n',
                      '                if os.environ.get("JANUS_LEGACY_CI") == "1":\n                    logger.info("[CI] MonkeyPatcher mutation suppressed")\n                else:\n                    patcher.update()\n', 'patcher suppression')
    core=replace_once(core, '            logger.info(f"--- ЦИКЛ {cycle} ЗАВЕРШЁН, пауза {pause:.2f}с ---")\n',
                      '            logger.info(f"--- ЦИКЛ {cycle} ЗАВЕРШЁН, пауза {pause:.2f}с ---")\n            legacy_ci_cycles += 1\n            if legacy_ci_max_cycles and legacy_ci_cycles >= legacy_ci_max_cycles:\n                logger.info(f"[CI] bounded legacy run reached {legacy_ci_cycles} cycle(s); exiting")\n                break\n', 'bounded cycle exit')
    corep.write_text(core,'utf-8'); transforms += ['core.py -> bounded max cycles', 'core.py -> suppress MonkeyPatcher mutation in CI']
    trainerp=work/'trainer.py'; trainer=trainerp.read_text('utf-8')
    trainer=replace_once(trainer, '        num_samples, gen_len = 100, 100\n',
                         '        if os.environ.get("JANUS_LEGACY_CI") == "1":\n            num_samples, gen_len = 8, 8\n        else:\n            num_samples, gen_len = 100, 100\n', 'trainer sample bound')
    trainerp.write_text(trainer,'utf-8'); transforms.append('trainer.py -> CI-only validation sample bound 8x8')
    matrixp=work/'janus_genesis'/'matrix_mod.py'; matrix=matrixp.read_text('utf-8')
    matrix=replace_once(matrix, 'import threading\n', 'import os\nimport threading\n', 'matrix os import')
    matrix=replace_once(matrix,
        "        self.a = torch.randn(2048, 2048, device='cuda')\n        self.b = torch.randn(2048, 2048, device='cuda')\n        self.c = torch.randn(2048, 2048, device='cuda')\n",
        "        if os.environ.get('JANUS_LEGACY_CI') == '1' or not torch.cuda.is_available():\n            self.a = self.b = self.c = None\n        else:\n            self.a = torch.randn(2048, 2048, device='cuda')\n            self.b = torch.randn(2048, 2048, device='cuda')\n            self.c = torch.randn(2048, 2048, device='cuda')\n",
        'matrix cuda allocation')
    matrixp.write_text(matrix,'utf-8'); transforms.append('janus_genesis/matrix_mod.py -> suppress unconditional CUDA allocation in CI')
    visionp=work/'janus_genesis'/'visionary.py'; vision=visionp.read_text('utf-8')
    marker='    async def on_event(self, event_type, event_data, world):\n'
    if marker not in vision: raise RuntimeError('compat patch anchor missing: visionary on_event')
    vision=vision.replace(marker, marker + "        if os.environ.get('JANUS_LEGACY_CI') == '1':\n            logger.info(f'[CI] Visionary event observed without image generation: {event_type}')\n            return None\n", 1)
    visionp.write_text(vision,'utf-8'); transforms.append('janus_genesis/visionary.py -> observe events without model/image generation in CI')
    raw=runtime/'raw_logs'; raw.mkdir(parents=True,exist_ok=True)
    if (work/'vocab.json').exists(): shutil.copyfile(work/'vocab.json',raw/'vocab.json')
    if (work/'janus_nuclear_emulation_v2.0.json').exists(): shutil.copyfile(work/'janus_nuclear_emulation_v2.0.json',raw/'janus_nuclear_emulation_v2.0.json')
    env=os.environ.copy(); env.update({
      'JANUS_LEGACY_CI':'1','JANUS_LEGACY_MAX_CYCLES':str(a.max_cycles),'JANUS_BASE_DIR':str(runtime),
      'JANUS_TRAIN_SIZE':'64','JANUS_VAL_SIZE':'32','JANUS_STEPS_PER_CYCLE':'1','JANUS_SEEDS_PER_CYCLE':'1','JANUS_BASE_BATCH_SIZE':'8','JANUS_BLOCK_SIZE':'16',
      'JANUS_SWARM_ENABLED':'0','JANUS_BAYES_ENABLED':'0','JANUS_META_ENABLED':'0','JANUS_ADAPTIVE_TEST_ENABLED':'0','JANUS_SUBCONSCIOUS_ENABLED':'0','JANUS_CONVERGENCE_ENABLED':'0','JANUS_FILTER_37':'0',
      'PYTHONUNBUFFERED':'1','PYTHONDONTWRITEBYTECODE':'1'
    })
    start=time.time(); status='error'; rc=None; timed_out=False
    log=out/'legacy_core.log'
    try:
        cp=subprocess.run([sys.executable,'core.py'],cwd=work,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=a.timeout)
        rc=cp.returncode; log.write_text(cp.stdout,'utf-8'); status='pass' if rc==0 and '[CI] bounded legacy run reached' in cp.stdout else 'fail'
    except subprocess.TimeoutExpired as e:
        timed_out=True; data=(e.stdout or '')
        if isinstance(data,bytes): data=data.decode('utf-8','replace')
        log.write_text(data,'utf-8'); status='timeout'
    receipt={
      'schema':'janus.demiurge.legacy_ci_receipt.v1','status':status,'returncode':rc,'timed_out':timed_out,
      'duration_s':round(time.time()-start,3),'bundle_sha256':sha256(bundle),'source_archive_sha256':manifest['source_archive']['sha256'],
      'snapshot_root':manifest['snapshot_root'],'preservation_mode':manifest['preservation_mode'],'compatibility_transforms':transforms,
      'max_cycles':a.max_cycles,'runtime_network':'OUTBOUND_DENIED_LOOPBACK_ONLY','self_mutation':'SUPPRESSED_IN_CI_WORKING_COPY',
      'source_bytes_modified':False,'working_copy_modified':True,'log_path':str(log)
    }
    (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    print('--- LOG TAIL ---')
    print('\n'.join(log.read_text('utf-8',errors='replace').splitlines()[-80:]))
    return 0 if status=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
