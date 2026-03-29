#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS SYSTEM MONITOR v9.1 — TACHYONIC ENTROPY EDITION + БЕЗОПАСНЫЙ АУДИО-ПОТОК
"""

import threading
import time
import psutil
import os
import statistics
import json
import subprocess
import ctypes
import win32gui
import win32process
import win32con
from datetime import datetime
from collections import deque
import numpy as np
import logging

# ========== ПУТИ ИЗ КОНФИГА ==========
from config import CACHE_PROBE_INTERVAL, CACHE_PROBE_SIZE_MB, WORMHOLE_DIR, RAW_LOGS_DIR, MODEL_ZOO_DIR

# ========== НАСТРОЙКА ЛОГГЕРА ==========
logger = logging.getLogger("JANUS")

# ========== ПРОВЕРКА НАЛИЧИЯ МОДУЛЕЙ ==========
WMI_AVAILABLE = False
try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    pass

NVML_AVAILABLE = False
try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
    logger.info("NVML инициализирован")
except Exception:
    pass

# ========== АУДИО, ЭКРАН, ВВОД ==========
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    AUDIO_DEVICES_AVAILABLE = True
except ImportError:
    AUDIO_DEVICES_AVAILABLE = False
try:
    from pynput import keyboard, mouse
    INPUT_AVAILABLE = True
except ImportError:
    INPUT_AVAILABLE = False
try:
    import dxcam
    import cv2
    SCREEN_AVAILABLE = True
except ImportError:
    SCREEN_AVAILABLE = False

# ========== КЭШ-ПРОБА ==========
class CacheProbe:
    def __init__(self, interval=60.0, size_mb=50):
        self.interval = interval
        self.size_mb = size_mb
        self.running = True
        self.baseline = None
        self.current_ratio = 1.0
        self.current_elapsed = 0.0
        self.lock = threading.Lock()
        self._thread = threading.Thread(target=self._probe_loop, daemon=True)
        self._thread.start()
        logger.info(f"📦 CacheProbe запущен. Размер: {self.size_mb} MB")

    def _measure_cache(self):
        try:
            arr_size = (self.size_mb * 1024 * 1024) // 4
            arr = np.random.randint(0, 255, arr_size, dtype=np.int32)
            start = time.perf_counter()
            total = 0
            stride = 16
            for i in range(0, len(arr), stride):
                total += arr[i]
            elapsed = time.perf_counter() - start
            return elapsed, total
        except Exception:
            return -1.0, 0

    def _calibrate(self):
        times = []
        for _ in range(5):
            elapsed, _ = self._measure_cache()
            if elapsed > 0:
                times.append(elapsed)
            time.sleep(0.1)
        if len(times) >= 3:
            times.remove(max(times))
            times.remove(min(times))
            self.baseline = np.median(times)
            logger.info(f"✅ Baseline кэша установлен: {self.baseline:.4f} сек")
        else:
            self.baseline = 0.01

    def _probe_loop(self):
        self._calibrate()
        while self.running:
            elapsed, _ = self._measure_cache()
            if elapsed > 0 and self.baseline and self.baseline > 0:
                ratio = elapsed / self.baseline
                with self.lock:
                    self.current_elapsed = elapsed
                    self.current_ratio = ratio
            time.sleep(self.interval)

    def get_metrics(self):
        with self.lock:
            return {
                'elapsed': self.current_elapsed,
                'ratio': self.current_ratio,
                'baseline': self.baseline
            }

    def stop(self):
        self.running = False

# ========== iGPU МОНИТОР ==========
class IGpuMonitor:
    def __init__(self, interval=10.0):
        self.interval = interval
        self.running = True
        self.load = 0.0
        self.temp = 0.0
        self.lock = threading.Lock()
        if WMI_AVAILABLE:
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
            logger.debug("💻 IGpuMonitor (WMI) запущен.")
        else:
            self.running = False

    def _poll_loop(self):
        import pythoncom
        pythoncom.CoInitialize()
        w = wmi.WMI()
        while self.running:
            try:
                gpu_counters = w.Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapter()
                max_igpu_load = 0.0
                for gpu in gpu_counters:
                    name = gpu.Name.lower()
                    if "nvidia" not in name and "rtx" not in name:
                        load = float(gpu.UtilizationPercentage)
                        if load > max_igpu_load:
                            max_igpu_load = load
                with self.lock:
                    self.load = max_igpu_load
            except Exception as e:
                logger.debug("⚠️ Ошибка чтения WMI iGPU: %s", e)
            time.sleep(self.interval)
        pythoncom.CoUninitialize()

    def get_metrics(self):
        with self.lock:
            return {'load': self.load, 'temp': self.temp}

    def stop(self):
        self.running = False

# ========== АУДИО-АНАЛИЗАТОР (исправленный, безопасный) ==========
class AudioSpectrumAnalyzer:
    def __init__(self, rate=44100, chunk=1024, bands=None, device_index=None):
        self.rate = rate
        self.chunk = chunk
        self.bands = bands if bands is not None else [
            (0, 100), (100, 300), (300, 600), (600, 1200),
            (1200, 2400), (2400, 4800), (4800, 9600), (9600, 20000)
        ]
        self.band_levels = [0.0] * len(self.bands)
        self.running = True
        self._thread = None
        self.device_index = device_index
        self.stream = None
        self.p = None
        if AUDIO_AVAILABLE:
            self.p = pyaudio.PyAudio()
            try:
                self.stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.rate,
                    input=True,
                    input_device_index=self.device_index,
                    frames_per_buffer=self.chunk
                )
                self.stream.start_stream()
                self._thread = threading.Thread(target=self._audio_loop, daemon=True)
                self._thread.start()
                logger.info(f"Аудиоанализатор спектра запущен (устройство: {self.device_index})")
            except Exception as e:
                logger.error(f"Ошибка открытия аудиопотока: {e}")
                self.stream = None
        else:
            self.stream = None

    def _audio_loop(self):
        while self.running:
            # Проверяем, что поток существует и открыт
            if self.stream is None:
                time.sleep(0.1)
                continue
            try:
                if not self.stream.is_active():
                    time.sleep(0.1)
                    continue
            except (OSError, AttributeError):
                # Поток уже закрыт или недоступен
                break

            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                fft = np.fft.rfft(samples)
                magnitude = np.abs(fft) / (self.chunk // 2)
                freqs = np.fft.rfftfreq(self.chunk, 1.0 / self.rate)

                levels = []
                for low, high in self.bands:
                    idx = np.where((freqs >= low) & (freqs < high))[0]
                    level = np.mean(magnitude[idx]) if len(idx) > 0 else 0.0
                    levels.append(float(level))

                max_lvl = max(levels) if max(levels) > 0 else 1.0
                self.band_levels = [lvl / max_lvl for lvl in levels]

            except Exception:
                pass
            time.sleep(0.05)

    def get_levels(self):
        return self.band_levels.copy()

    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass

# ========== МОНИТОР АУДИОУСТРОЙСТВ ==========
class AudioDeviceMonitor:
    def __init__(self):
        self.devices = []
        self.prev_devices = []
        self._refresh_devices()

    def _refresh_devices(self):
        self.devices = []
        if not AUDIO_DEVICES_AVAILABLE:
            return
        try:
            devices = AudioUtilities.GetAllDevices()
            for dev in devices:
                try:
                    dev_id = dev.id
                    name = dev.FriendlyName
                    state = dev.State
                    is_enabled = dev.IsEnabled()
                    data_flow = dev.DataFlow

                    volume_scalar = None
                    muted = None
                    if is_enabled and data_flow == 0:
                        try:
                            endpoint = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                            volume = endpoint.QueryInterface(IAudioEndpointVolume)
                            volume_scalar = volume.GetMasterVolumeLevelScalar()
                            muted = volume.GetMute()
                        except Exception as e:
                            logger.debug(f"Не удалось получить громкость для {name}: {e}")

                    self.devices.append({
                        'id': dev_id,
                        'name': name,
                        'type': 'input' if data_flow == 1 else 'output',
                        'state': state,
                        'is_enabled': is_enabled,
                        'volume': round(volume_scalar, 3) if volume_scalar is not None else None,
                        'muted': muted
                    })
                except Exception as e:
                    logger.debug(f"Ошибка обработки устройства: {e}")
                    continue
        except Exception as e:
            logger.error(f"Ошибка получения аудиоустройств: {e}")

    def _detect_changes(self):
        changes = []
        if not self.prev_devices:
            self.prev_devices = self.devices
            return changes

        prev_dict = {d['id']: d for d in self.prev_devices}
        curr_dict = {d['id']: d for d in self.devices}

        for pid, pdev in prev_dict.items():
            if pid not in curr_dict:
                changes.append({'type': 'removed', 'device': pdev})
                logger.info(f"🔇 Аудиоустройство отключено: {pdev['name']} ({pdev['type']})")

        for cid, cdev in curr_dict.items():
            if cid not in prev_dict:
                changes.append({'type': 'added', 'device': cdev})
                logger.info(f"🎧 Аудиоустройство подключено: {cdev['name']} ({cdev['type']})")
            else:
                pdev = prev_dict[cid]
                if pdev['is_enabled'] != cdev['is_enabled'] or pdev['state'] != cdev['state']:
                    changes.append({'type': 'state_changed', 'device': cdev,
                                    'old_state': pdev['state'], 'new_state': cdev['state']})
                    logger.info(f"🔊 Состояние аудиоустройства изменилось: {cdev['name']}")

        self.prev_devices = self.devices
        return changes

    def _detect_equalizer(self):
        equalizer_names = ["equalizer", "eq", "apo", "voicemeeter", "peace"]
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name'].lower()
                if any(eq in name for eq in equalizer_names):
                    return True
            except:
                pass
        return False

    def get_metrics(self):
        if not AUDIO_DEVICES_AVAILABLE:
            return {'devices': [], 'changes': [], 'equalizer_detected': False}
        self._refresh_devices()
        changes = self._detect_changes()
        equalizer = self._detect_equalizer()
        return {
            'devices': self.devices,
            'changes': changes,
            'equalizer_detected': equalizer
        }

# ========== МОНИТОР КЛАВИАТУРЫ ==========
class KeyboardMonitor:
    def __init__(self, window_size=1.0):
        self.window_size = window_size
        self.key_count = 0
        self.lock = threading.Lock()
        self.running = True
        self._listener = None
        if INPUT_AVAILABLE:
            self._listener = keyboard.Listener(on_press=self._on_press)
            self._listener.start()
            self._thread = threading.Thread(target=self._reset_loop, daemon=True)
            self._thread.start()
            logger.info("Монитор клавиатуры запущен")

    def _on_press(self, key):
        with self.lock:
            self.key_count += 1

    def _reset_loop(self):
        while self.running:
            time.sleep(self.window_size)
            with self.lock:
                self.key_count = 0

    def get_metrics(self):
        with self.lock:
            count = self.key_count
        return {
            'keys_per_sec': count / self.window_size,
            'total_in_window': count
        }

    def stop(self):
        self.running = False
        if self._listener:
            self._listener.stop()

# ========== МОНИТОР МЫШИ ==========
class MouseMonitor:
    def __init__(self, window_size=1.0):
        self.window_size = window_size
        self.click_count = 0
        self.scroll_count = 0
        self.move_distance = 0
        self.lock = threading.Lock()
        self.running = True
        self.last_x = None
        self.last_y = None
        self._listener = None
        if INPUT_AVAILABLE:
            self._listener = mouse.Listener(
                on_move=self._on_move,
                on_click=self._on_click,
                on_scroll=self._on_scroll
            )
            self._listener.start()
            self._thread = threading.Thread(target=self._reset_loop, daemon=True)
            self._thread.start()
            logger.info("Монитор мыши запущен")

    def _on_move(self, x, y):
        with self.lock:
            if self.last_x is not None and self.last_y is not None:
                self.move_distance += abs(x - self.last_x) + abs(y - self.last_y)
            self.last_x, self.last_y = x, y

    def _on_click(self, x, y, button, pressed):
        if pressed:
            with self.lock:
                self.click_count += 1

    def _on_scroll(self, x, y, dx, dy):
        with self.lock:
            self.scroll_count += 1

    def _reset_loop(self):
        while self.running:
            time.sleep(self.window_size)
            with self.lock:
                self.click_count = 0
                self.scroll_count = 0
                self.move_distance = 0
                self.last_x = None
                self.last_y = None

    def get_metrics(self):
        with self.lock:
            return {
                'clicks_per_sec': self.click_count / self.window_size,
                'scrolls_per_sec': self.scroll_count / self.window_size,
                'move_distance_per_sec': self.move_distance / self.window_size
            }

    def stop(self):
        self.running = False
        if self._listener:
            self._listener.stop()

# ========== МОНИТОР ЭКРАНА ==========
class ScreenMonitor:
    def __init__(self, interval=1.0, hist_bins=10, snapshot_dir=None):
        self.interval = interval
        self.hist_bins = hist_bins
        self.running = True
        self.lock = threading.Lock()
        self.last_frame = None
        self.metrics = {
            'brightness': 0.0,
            'histogram': [0.0]*hist_bins,
            'motion': 0.0,
            'entropy': 0.0
        }
        self.snapshot_dir = snapshot_dir or os.path.join(WORMHOLE_DIR, "screenshots")
        self.camera = None
        if SCREEN_AVAILABLE:
            try:
                self.camera = dxcam.create(output_idx=0)
                self.camera.start(target_fps=1)
                self._thread = threading.Thread(target=self._capture_loop, daemon=True)
                self._thread.start()
                logger.info(f"Монитор экрана запущен (интервал {interval} сек)")
            except Exception as e:
                logger.error(f"Не удалось инициализировать камеру: {e}")
                self.camera = None
        else:
            logger.warning("Монитор экрана отключён (dxcam не доступен)")

    def _capture_loop(self):
        while self.running:
            if self.camera is None:
                time.sleep(1)
                continue
            try:
                frame = self.camera.get_latest_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                brightness = np.mean(gray)
                hist = cv2.calcHist([gray], [0], None, [self.hist_bins], [0,256]).flatten()
                hist = hist / hist.sum()

                motion = 0.0
                if self.last_frame is not None:
                    diff = cv2.absdiff(gray, self.last_frame)
                    motion = np.mean(diff) / 255.0
                self.last_frame = gray

                entropy = -np.sum(hist * np.log2(hist + 1e-12))

                with self.lock:
                    self.metrics = {
                        'brightness': float(brightness) / 255.0,
                        'histogram': hist.tolist(),
                        'motion': float(motion),
                        'entropy': float(entropy)
                    }
            except Exception as e:
                logger.error(f"Ошибка захвата экрана: {e}")
            time.sleep(self.interval)

    def get_metrics(self):
        with self.lock:
            return self.metrics.copy()

    def get_snapshot_metadata(self, reason="auto"):
        with self.lock:
            return {
                'timestamp': datetime.now().isoformat(),
                'reason': reason,
                'brightness': self.metrics['brightness'],
                'motion': self.metrics['motion'],
                'entropy': self.metrics['entropy'],
                'histogram': self.metrics['histogram']
            }

    def save_snapshot(self, reason="auto"):
        if self.camera is None:
            return None
        try:
            frame = self.camera.get_latest_frame()
            if frame is None:
                return None
            os.makedirs(self.snapshot_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{timestamp}_{reason}.png"
            filepath = os.path.join(self.snapshot_dir, filename)
            cv2.imwrite(filepath, frame)
            meta = {
                'timestamp': timestamp,
                'reason': reason,
                'metrics': self.get_metrics()
            }
            meta_path = os.path.join(self.snapshot_dir, f"snapshot_{timestamp}_{reason}.json")
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2)
            logger.info(f"💾 Снапшот сохранён: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Ошибка сохранения снапшота: {e}")
            return None

    def stop(self):
        self.running = False
        if self.camera:
            self.camera.stop()

# ========== ДИНАМИЧЕСКИЙ ДЕТЕКТОР ИГР ==========
class GameDetector:
    def __init__(self):
        self.known_game_paths = [
            "steamapps", "epic games", "ubisoft", "origin games", "battlenet",
            "program files (x86)\\steam", "program files\\steam"
        ]
        self.game_history = deque(maxlen=100)
        self.peak_game_cpu = 0.0
        self.peak_game_gpu = 0.0
        self.avg_game_cpu = 0.0
        self.avg_game_gpu = 0.0

    def is_game(self, proc):
        try:
            name = proc.info['name'].lower()
            pid = proc.info['pid']

            if pid == os.getpid():
                return False

            system_procs = ['explorer.exe', 'dwm.exe', 'csrss.exe', 'winlogon.exe', 'services.exe', 'svchost.exe']
            if name in system_procs:
                return False

            launchers = ['steam.exe', 'steamwebhelper.exe', 'epicgameslauncher.exe', 'origin.exe', 'battlenet.exe']
            if name in launchers:
                return False

            try:
                exe_path = proc.exe()
                exe_lower = exe_path.lower()
                if any(path in exe_lower for path in self.known_game_paths):
                    return True
            except:
                pass

            def enum_windows_callback(hwnd, pids):
                if win32gui.IsWindowVisible(hwnd):
                    tid, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid == pid:
                        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                        if style & win32con.WS_CAPTION == 0 or style & win32con.WS_SIZEBOX == 0:
                            return False
            pids = []
            win32gui.EnumWindows(enum_windows_callback, pids)
            if pid in pids:
                return True

            if WMI_AVAILABLE:
                gpu_usage = self._get_gpu_usage_for_process(pid)
                if gpu_usage > 30:
                    return True

        except Exception as e:
            logger.debug(f"Ошибка при проверке процесса {pid}: {e}")
        return False

    def _get_gpu_usage_for_process(self, pid):
        if not WMI_AVAILABLE:
            return 0
        try:
            w = wmi.WMI()
            query = f"SELECT * FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine WHERE Name LIKE '%pid_{pid}%'"
            items = w.query(query)
            total_util = 0
            for item in items:
                total_util += float(item.UtilizationPercentage)
            return total_util
        except:
            return 0

    def scan_games(self):
        games = []
        current_game_cpu = 0.0
        current_game_gpu = 0.0
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if self.is_game(proc):
                    cpu = proc.info['cpu_percent']
                    gpu = self._get_gpu_usage_for_process(proc.info['pid'])
                    games.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu': cpu,
                        'memory': proc.info['memory_percent'],
                        'gpu': gpu
                    })
                    current_game_cpu += cpu
                    current_game_gpu += gpu
            except:
                pass

        if games:
            self.game_history.append({
                'total_cpu': current_game_cpu,
                'total_gpu': current_game_gpu
            })
            if len(self.game_history) > 5:
                recent = list(self.game_history)[-5:]
                self.avg_game_cpu = np.mean([x['total_cpu'] for x in recent])
                self.avg_game_gpu = np.mean([x['total_gpu'] for x in recent])
                self.peak_game_cpu = max([x['total_cpu'] for x in recent])
                self.peak_game_gpu = max([x['total_gpu'] for x in recent])

        return games

    def get_game_stats(self):
        return {
            'avg_cpu': self.avg_game_cpu,
            'peak_cpu': self.peak_game_cpu,
            'avg_gpu': self.avg_game_gpu,
            'peak_gpu': self.peak_game_gpu
        }

# ========== HARDWARE ENTROPY ==========
class HardwareEntropy:
    def __init__(self, samples=30):
        self.samples = samples

    def _test_operation(self):
        x = 0
        for i in range(10000):
            x += i * i
        return x

    def measure(self):
        timings = []
        for _ in range(self.samples):
            start = time.perf_counter()
            self._test_operation()
            timings.append(time.perf_counter() - start)

        if len(timings) < 2:
            return {'timing_jitter': 0.0, 'execution_variance': 0.0, 'stability_score': 1.0}

        mean = statistics.mean(timings)
        variance = statistics.variance(timings)
        jitter = max(timings) - min(timings)

        stability = 1.0 / (1.0 + variance * 1000)
        return {
            'timing_jitter': round(jitter, 6),
            'execution_variance': round(variance, 8),
            'stability_score': round(stability, 4)
        }

# ========== ПРЕДСКАЗАТЕЛЬ НАГРУЗКИ ==========
class TachyonPredictor:
    def __init__(self):
        self.history = deque(maxlen=100)
        self.peak_history = deque(maxlen=20)

    def add_observation(self, metrics):
        gpu_data = metrics.get('gpu', [{}])
        if isinstance(gpu_data, list) and gpu_data:
            gpu_load = gpu_data[0].get('gpu_util', 0)
            gpu_temp = gpu_data[0].get('temperature', 40)
        else:
            gpu_load = 0
            gpu_temp = 40
        cpu_load = metrics.get('cpu', {}).get('percent_total', 0)
        gaming_mode = metrics.get('gaming_mode', False)
        game_cpu = metrics.get('game_cpu', 0)
        game_gpu = metrics.get('game_gpu', 0)

        self.history.append({
            'gpu_load': gpu_load,
            'gpu_temp': gpu_temp,
            'cpu_load': cpu_load,
            'gaming_mode': gaming_mode,
            'game_cpu': game_cpu,
            'game_gpu': game_gpu
        })

        if gaming_mode:
            self.peak_history.append({'game_cpu': game_cpu, 'game_gpu': game_gpu})

    def predict_next_load(self):
        if len(self.history) < 10:
            return None
        recent = list(self.history)[-5:]
        avg_gpu = np.mean([m['gpu_load'] for m in recent])
        avg_cpu = np.mean([m['cpu_load'] for m in recent])
        avg_temp = np.mean([m['gpu_temp'] for m in recent])
        gaming = any(m['gaming_mode'] for m in recent)

        if gaming and len(self.peak_history) > 0:
            peak_game_cpu = np.max([p['game_cpu'] for p in self.peak_history])
            peak_game_gpu = np.max([p['game_gpu'] for p in self.peak_history])
        else:
            peak_game_cpu = 0
            peak_game_gpu = 0

        return {
            'gpu_load': avg_gpu,
            'cpu_load': avg_cpu,
            'gpu_temp': avg_temp,
            'gaming_mode': gaming,
            'peak_game_cpu': peak_game_cpu,
            'peak_game_gpu': peak_game_gpu
        }

# ========== ТЕРМОДИНАМИЧЕСКИЕ КЛАССЫ ==========
class ThermalEntropyAnalyzer:
    def __init__(self, sample_size=100):
        self.samples = deque(maxlen=sample_size)
        self.lock = threading.Lock()
        logger.info("🧊 Анализатор энтропии инициализирован (Шкала: Фаренгейт)")

    def _measure_jitter(self):
        t0 = time.perf_counter()
        for _ in range(30000):
            pass
        return time.perf_counter() - t0

    def get_metrics(self, cpu_temp_c):
        jitter = self._measure_jitter()
        temp_f = (cpu_temp_c * 9/5) + 32

        with self.lock:
            self.samples.append(jitter)
            entropy = statistics.stdev(self.samples) if len(self.samples) > 2 else 0.001

        purity = 1.0 / (entropy * temp_f + 1e-12)
        purity = min(100.0, purity)

        return {
            'temp_f': round(temp_f, 2),
            'hw_entropy': entropy,
            'purity_score': purity
        }


class TachyonicRegulator:
    def __init__(self, target_temp_f=113.0):
        self.target_temp_f = target_temp_f
        self.load_scale = 1.0
        self.mode = "EXPLORE"

    def process(self, metrics):
        temp_f = metrics['temp_f']
        entropy = metrics['hw_entropy']

        if temp_f > self.target_temp_f or entropy > 0.002:
            self.mode = "CONTRACT"
            self.load_scale = max(0.1, self.load_scale - 0.05)
        elif temp_f < self.target_temp_f - 10:
            self.mode = "FREEZE"
            self.load_scale = min(1.0, self.load_scale + 0.02)
        else:
            self.mode = "STABLE"

        return {
            'tachyonic_mode': self.mode,
            'load_scale': round(self.load_scale, 2)
        }


class JanusVault:
    def __init__(self):
        for p in [RAW_LOGS_DIR, MODEL_ZOO_DIR, WORMHOLE_DIR]:
            os.makedirs(p, exist_ok=True)
        self.best_purity = 0.0
        self.log_file = os.path.join(RAW_LOGS_DIR, "thermal_raw.jsonl")

    def commit(self, metrics, tachy):
        purity = metrics['purity_score'] * tachy['load_scale']
        timestamp = datetime.now().isoformat()

        entry = {**metrics, **tachy, 'purity_final': purity, 'ts': timestamp}

        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        if purity > self.best_purity and tachy['tachyonic_mode'] != "EXPLORE":
            self.best_purity = purity
            zoo_path = os.path.join(MODEL_ZOO_DIR, f"gold_{int(time.time())}.json")
            with open(zoo_path, "w") as f:
                json.dump(entry, f, indent=4)
            logger.info(f"🌟 Найдено Золотое Состояние: purity={purity:.4f}")

        with open(os.path.join(WORMHOLE_DIR, "purity.signal"), "w") as f:
            f.write(str(purity))

    def auto_clean(self, max_mb=500):
        if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > max_mb * 1024 * 1024:
            os.remove(self.log_file)
            logger.info("🧹 Raw logs очищены по лимиту размера")

    def learn(self, regulator):
        files = [os.path.join(MODEL_ZOO_DIR, f) for f in os.listdir(MODEL_ZOO_DIR) if f.endswith('.json')]
        if not files:
            return

        temps = []
        for f in files[-10:]:
            try:
                with open(f, 'r') as jf:
                    data = json.load(jf)
                    temps.append(data['temp_f'])
            except Exception:
                continue
        if temps:
            new_target = sum(temps) / len(temps)
            regulator.target_temp_f = new_target
            logger.info(f"🧠 Обучение завершено. Новая целевая температура: {new_target:.2f}°F")

# ========== ТЕМПЕРАТУРА CPU ==========
def get_cpu_temperature():
    if not WMI_AVAILABLE:
        logger.debug("WMI недоступен, температура не получена")
        return None
    try:
        import pythoncom
        pythoncom.CoInitialize()
        try:
            w = wmi.WMI(namespace="root\\wmi")
            temps = []
            for temp in w.MSAcpi_ThermalZoneTemperature():
                celsius = (temp.CurrentTemperature / 10.0) - 273.15
                temps.append(celsius)
            if temps:
                logger.info(f"🌡️ Температура через MSAcpi: {round(temps[0], 1)}°C")
                return round(temps[0], 1)
        except Exception as e:
            logger.debug(f"MSAcpi не работает: {e}")

        try:
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            sensors = list(w.Sensor())
            logger.info(f"🔍 OpenHardwareMonitor: найдено сенсоров: {len(sensors)}")
            for sensor in sensors:
                if sensor.SensorType == u'Temperature':
                    logger.info(f"   Температурный сенсор: {sensor.Name} = {sensor.Value}°C")
                    if 'CPU' in sensor.Name or 'Package' in sensor.Name or 'Core' in sensor.Name:
                        logger.info(f"✅ Используем: {sensor.Name} = {sensor.Value}°C")
                        return round(sensor.Value, 1)
            for sensor in sensors:
                if sensor.SensorType == u'Temperature':
                    logger.info(f"⚠️ Используем первый найденный: {sensor.Name} = {sensor.Value}°C")
                    return round(sensor.Value, 1)
        except Exception as e:
            logger.warning(f"OpenHardwareMonitor недоступен: {e}")

        pythoncom.CoUninitialize()
    except Exception as e:
        logger.debug(f"Общая ошибка получения температуры: {e}")
    return None

# ========== ОСНОВНОЙ МОНИТОР ==========
class SystemMonitor:
    def __init__(self, poll_interval=25.0, audio_device=None, screen_interval=1.0, top_n=5):
        self.poll_interval = poll_interval
        self.top_n = top_n
        self.running = True
        self.lock = threading.Lock()

        self.cache_probe = CacheProbe(interval=CACHE_PROBE_INTERVAL, size_mb=CACHE_PROBE_SIZE_MB)
        self.igpu_monitor = IGpuMonitor()
        self.spectrum_analyzer = AudioSpectrumAnalyzer(device_index=audio_device) if AUDIO_AVAILABLE else None
        self.audio_device_monitor = AudioDeviceMonitor() if AUDIO_DEVICES_AVAILABLE else None
        self.keyboard_monitor = KeyboardMonitor() if INPUT_AVAILABLE else None
        self.mouse_monitor = MouseMonitor() if INPUT_AVAILABLE else None
        self.screen_monitor = ScreenMonitor(interval=screen_interval) if SCREEN_AVAILABLE else None
        self.game_detector = GameDetector()
        self.predictor = TachyonPredictor()
        self.hw_entropy = HardwareEntropy(samples=30)

        self.thermal_entropy = ThermalEntropyAnalyzer()
        self.regulator = TachyonicRegulator()
        self.vault = JanusVault()

        self._learn_counter = 0
        self._last_learn_time = time.time()

        self.metrics = self._init_metrics_dict()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _init_metrics_dict(self):
        return {
            'timestamp': None,
            'gpu': {},
            'igpu': {},
            'cache': {},
            'cpu': {},
            'memory': {},
            'disk': [],
            'network': {},
            'audio_spectrum': [],
            'audio_devices': {'devices': [], 'changes': [], 'equalizer_detected': False},
            'keyboard': {},
            'mouse': {},
            'screen': {},
            'top_processes': [],
            'gaming_mode': False,
            'games': [],
            'game_name': None,
            'game_cpu': 0.0,
            'game_mem': 0.0,
            'game_gpu': 0.0,
            'idle_cores': 0,
            'total_cores': psutil.cpu_count(logical=True),
            'predicted': {},
            'cpu_temperature': None,
            'hardware_entropy': None,
            'temp_f': None,
            'hw_entropy': None,
            'purity_score': None,
            'tachyonic_mode': None,
            'load_scale': None,
        }

    def _poll_loop(self):
        while self.running:
            try:
                snapshot = self._collect_metrics()
                with self.lock:
                    self.metrics = snapshot
                self.predictor.add_observation(snapshot)

                now = time.time()
                if now - self._last_learn_time > 3600:
                    self.vault.learn(self.regulator)
                    self._last_learn_time = now

                self._learn_counter += 1
                if self._learn_counter % 1000 == 0:
                    self.vault.learn(self.regulator)

                if now % 86400 < self.poll_interval:
                    self.vault.auto_clean()

            except Exception as e:
                logger.error(f"Ошибка в poll_loop: {e}", exc_info=True)
            time.sleep(self.poll_interval)

    def _collect_metrics(self):
        cpu_metrics = self._get_cpu_metrics()
        idle_cores = cpu_metrics.get('idle_cores', 0)

        metrics = {
            'timestamp': datetime.now().isoformat(),
            'gpu': self._get_gpu_metrics(),
            'igpu': self.igpu_monitor.get_metrics(),
            'cache': self.cache_probe.get_metrics(),
            'cpu': cpu_metrics,
            'memory': self._get_memory_metrics(),
            'disk': self._get_disk_metrics(),
            'network': self._get_network_metrics(),
            'audio_spectrum': self.spectrum_analyzer.get_levels() if self.spectrum_analyzer else [],
            'audio_devices': self.audio_device_monitor.get_metrics() if self.audio_device_monitor else {'devices': [], 'changes': [], 'equalizer_detected': False},
            'keyboard': self.keyboard_monitor.get_metrics() if self.keyboard_monitor else {},
            'mouse': self.mouse_monitor.get_metrics() if self.mouse_monitor else {},
            'screen': self.screen_monitor.get_metrics() if self.screen_monitor else {},
            'top_processes': self._get_top_processes(),
            'gaming_mode': False,
            'games': [],
            'game_name': None,
            'game_cpu': 0.0,
            'game_mem': 0.0,
            'game_gpu': 0.0,
            'idle_cores': idle_cores,
            'total_cores': psutil.cpu_count(logical=True),
            'predicted': {},
            'cpu_temperature': get_cpu_temperature(),
            'hardware_entropy': self.hw_entropy.measure(),
        }

        games = self.game_detector.scan_games()
        if games:
            metrics['gaming_mode'] = False
            metrics['games'] = games
            main_game = max(games, key=lambda g: g.get('gpu', 0))
            metrics['game_name'] = main_game['name']
            metrics['game_cpu'] = main_game['cpu']
            metrics['game_mem'] = main_game['memory']
            metrics['game_gpu'] = main_game['gpu']

        pred = self.predictor.predict_next_load()
        if pred:
            metrics['predicted'] = pred

        cpu_temp_c = metrics.get('cpu_temperature')
        if cpu_temp_c is None:
            cpu_temp_c = 40.0

        entropy_metrics = self.thermal_entropy.get_metrics(cpu_temp_c)
        tachyonic_data = self.regulator.process(entropy_metrics)

        metrics.update(entropy_metrics)
        metrics.update(tachyonic_data)

        self.vault.commit(entropy_metrics, tachyonic_data)

        return metrics

    # ---------- Остальные методы (без изменений) ----------
    def _get_gpu_metrics(self):
        if NVML_AVAILABLE:
            try:
                device_count = pynvml.nvmlDeviceGetCount()
                gpus = []
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                    gpus.append({
                        'index': i,
                        'gpu_util': util.gpu,
                        'memory_util': memory.used / memory.total * 100 if memory.total > 0 else 0,
                        'memory_used_mb': memory.used / 1024**2,
                        'memory_total_mb': memory.total / 1024**2,
                        'temperature': temperature,
                        'power_w': power
                    })
                return gpus
            except Exception as e:
                logger.debug(f"Ошибка получения метрик GPU через NVML: {e}, пробуем nvidia-smi")
        return self._get_gpu_metrics_nvidia_smi()

    def _get_gpu_metrics_nvidia_smi(self):
        try:
            cmd = [
                'nvidia-smi',
                '--query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw',
                '--format=csv,noheader,nounits'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)
            output = result.stdout.strip()
            if not output:
                return {}
            gpus = []
            for line in output.split('\n'):
                parts = [x.strip() for x in line.split(',')]
                if len(parts) < 6:
                    continue
                try:
                    idx = int(parts[0])
                    gpu_util = float(parts[1])
                    mem_used = float(parts[2])
                    mem_total = float(parts[3])
                    temp = float(parts[4])
                    power_str = parts[5].strip()
                    power = float(power_str) if power_str and power_str not in ['[N/A]', 'N/A'] else 0.0
                    gpus.append({
                        'index': idx,
                        'gpu_util': gpu_util,
                        'memory_util': (mem_used / mem_total * 100) if mem_total > 0 else 0,
                        'memory_used_mb': mem_used,
                        'memory_total_mb': mem_total,
                        'temperature': temp,
                        'power_w': power
                    })
                except (ValueError, IndexError):
                    continue
            return gpus
        except Exception as e:
            logger.debug(f"Не удалось получить метрики GPU через nvidia-smi: {e}")
            return {}

    def _get_cpu_metrics(self):
        per_core = psutil.cpu_percent(percpu=True)
        total = psutil.cpu_percent()
        count = psutil.cpu_count()
        idle_cores = sum(1 for p in per_core if p < 30)
        return {
            'percent_per_core': per_core,
            'percent_total': total,
            'count': count,
            'freq_current': psutil.cpu_freq().current if psutil.cpu_freq() else None,
            'load_avg': [x / count * 100 for x in psutil.getloadavg()] if hasattr(psutil, "getloadavg") else [],
            'idle_cores': idle_cores
        }

    def _get_memory_metrics(self):
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            'total_gb': mem.total / 1024**3,
            'available_gb': mem.available / 1024**3,
            'percent': mem.percent,
            'used_gb': mem.used / 1024**3,
            'swap_percent': swap.percent,
            'swap_used_gb': swap.used / 1024**3
        }

    def _get_disk_metrics(self):
        disks = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    'device': part.device,
                    'mountpoint': part.mountpoint,
                    'fstype': part.fstype,
                    'total_gb': usage.total / 1024**3,
                    'used_gb': usage.used / 1024**3,
                    'free_gb': usage.free / 1024**3,
                    'percent': usage.percent
                })
            except OSError as e:
                logger.debug(f"Пропускаем том {part.mountpoint}: {e}")
                continue
        return disks

    def _get_network_metrics(self):
        net = psutil.net_io_counters()
        return {
            'bytes_sent': net.bytes_sent,
            'bytes_recv': net.bytes_recv,
            'packets_sent': net.packets_sent,
            'packets_recv': net.packets_recv,
            'errin': net.errin,
            'errout': net.errout,
            'dropin': net.dropin,
            'dropout': net.dropout
        }

    def _get_top_processes(self):
        processes = []
        cpu_count = psutil.cpu_count()
        my_pid = os.getpid()
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    name = proc.info['name'].lower()
                    pid = proc.info['pid']
                    if name == 'system idle process' or pid == my_pid:
                        continue
                    pinfo = proc.info
                    pinfo['cpu_percent_norm'] = pinfo['cpu_percent'] / cpu_count if cpu_count else pinfo['cpu_percent']
                    processes.append(pinfo)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            processes.sort(key=lambda x: x['cpu_percent_norm'], reverse=True)
            top = processes[:self.top_n]
            for p in top:
                p['cpu_percent_norm'] = round(p['cpu_percent_norm'], 1)
            return top
        except Exception as e:
            logger.debug(f"Не удалось получить информацию о процессах: {e}")
            return []

    def get_current_metrics(self):
        with self.lock:
            return self.metrics.copy()

    def stop(self):
        self.running = False
        self.cache_probe.stop()
        self.igpu_monitor.stop()
        if self.spectrum_analyzer:
            self.spectrum_analyzer.stop()
        if self.keyboard_monitor:
            self.keyboard_monitor.stop()
        if self.mouse_monitor:
            self.mouse_monitor.stop()
        if self.screen_monitor:
            self.screen_monitor.stop()
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except:
                pass