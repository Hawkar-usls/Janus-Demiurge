#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VISIONARY ENGINE v5.0 — Око Януса, адаптивное, эволюционирующее, самосознающее.
- Генерирует изображения в формате WebP с умным сжатием (SSIM)
- Управляет промптами, значимостью событий, учится на эффективности
- Откладывает генерацию при активном игровом режиме (gaming_mode)
- Вносит вклад в поиск P=NP через обновление мета-цели (discovery_progress)
"""

import os
import json
import random
import time
import math
import logging
import sqlite3
from datetime import datetime
from collections import defaultdict, deque
import asyncio
import psutil
import numpy as np
import cv2
from skimage import measure
from skimage.metrics import structural_similarity as ssim
import torch

# Импорты из нашей экосистемы
from config import RAW_LOGS_DIR, WORMHOLE_DIR
from tachyon_engine import TachyonEngine
from counterfactual_engine import CounterfactualEngine
from visionary_critic import VisionaryCritic
from self_model import SelfModel
from regret_engine import RegretEngine
from strategy_engine import StrategyEngine
from janus_narrative import JanusNarrative
import janus_db

logger = logging.getLogger("JANUS.VISIONARY")

CONFIG = {
    'default_steps': 50,
    'steps_range': (20, 80),
    'target_quality': 0.75,
    'webp_quality': 90,
    'webp_quality_min': 10,
    'webp_quality_step': 5,
    'target_size_kb': 200,
    'enhance_upscale_factor': 1.5,
    'denoise_h': 10,
    'denoise_hcolor': 10,
    'denoise_template_window': 7,
    'denoise_search_window': 21,
    'prompt_max_keywords': 15,
    'importance_min': 0.6,
    'size_efficiency_window': 200,
    'quality_weight': 0.7,
    'time_weight': 0.2,
    'size_penalty_log_base': 10,
    'significance_novelty_weight': 0.6,
    'significance_impact_weight': 0.4,
    'significance_threshold': 0.4,
    'quality_update_window': 20,
    'quality_percentile': 90,
    'pnp_contribution_scale': 0.01,
    'pnp_contribution_max_per_generation': 0.1,
}

class VisionaryEngine:
    MODELS = {
        "photoreal": "dreamlike-art/dreamlike-photoreal-2.0",
    }
    IMPORTANT_EVENTS = {"RECORD", "EXTINCTION", "NEW_SPECIES", "RAID", "INSTITUTION_FOUNDED", "WORMHOLE"}

    WORD_IMPORTANCE = {
        "epic": 1.2, "detailed": 1.1, "intricate": 1.1, "complex": 1.0,
        "minimalism": 1.2, "clean": 1.1, "focused": 1.1, "sharp": 1.0,
        "blurry": -1.0, "noise": -1.0, "low quality": -1.5, "ugly": -1.5,
        "distorted": -1.0, "messy": -0.8
    }

    def __init__(self, storyteller, tachyon=None, model_name="photoreal", device=None,
                 save_png=False, webp_quality=90, enable_enhance=True,
                 meta_goal=None):
        """
        meta_goal: объект MetaGoalEngine (для обновления discovery_progress).
        """
        self.storyteller = storyteller
        self.tachyon = tachyon
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.save_png = save_png
        self.enable_enhance = enable_enhance
        self.webp_quality = webp_quality
        self.model_name = model_name
        self.model_id = self.MODELS.get(model_name, self.MODELS["photoreal"])
        self.meta_goal = meta_goal

        self.pipe = None
        self._model_loaded = False

        logger.info(f"🔥 Visionary v5.0 инициализирован (модель будет загружена при первом использовании)")

        # История и статистика
        self.history = deque(maxlen=1000)
        self.history_by_event = defaultdict(list)
        self.quality_by_steps = defaultdict(list)
        self.quality_history = deque(maxlen=CONFIG['quality_update_window'])
        self.size_efficiency = deque(maxlen=CONFIG['size_efficiency_window'])

        self.image_dir = os.path.join(RAW_LOGS_DIR, "EYE")
        os.makedirs(self.image_dir, exist_ok=True)

        self.total_generations = 0
        self.best_quality = 0.0
        self.last_event_type = None
        self.last_event_details = {}
        self.default_steps = CONFIG['default_steps']
        self.steps_range = CONFIG['steps_range']
        self.target_quality = CONFIG['target_quality']
        self.fast_generations = 0
        self.slow_generations = 0

        # Очередь отложенных заданий (всегда работает, но задания добавляются только при gaming_mode=True)
        self.pending_jobs = deque()
        self._processing_lock = asyncio.Lock()

        # Подсистемы
        self.critic = VisionaryCritic()
        self.counterfactual = CounterfactualEngine(tachyon) if tachyon else None
        self.self_model = SelfModel()
        self.regret_engine = RegretEngine()
        self.strategy = StrategyEngine()
        self.narrative = JanusNarrative()

        self.load_history()

    # ---------- Ленивая загрузка модели ----------
    def _load_model(self):
        if self._model_loaded:
            return
        try:
            from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
            logger.info(f"Загрузка модели {self.model_id} на {self.device}...")
            self.pipe = StableDiffusionPipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                safety_checker=None
            ).to(self.device)
            self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(self.pipe.scheduler.config)
            self._model_loaded = True
            logger.info("Модель успешно загружена")
        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}", exc_info=True)
            raise

    # ---------- Системное состояние ----------
    def _get_system_state(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        gpu_mem = 0.0
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated()
            max_alloc = torch.cuda.max_memory_allocated()
            gpu_mem = allocated / max_alloc if max_alloc > 0 else 0.0
        return {"cpu": cpu, "ram": ram, "gpu": gpu_mem}

    # ---------- Метрики ----------
    def _evaluate_quality(self, image):
        img = np.array(image)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
        entropy = measure.shannon_entropy(gray)
        quality = 0.6 * np.clip(laplacian / 1000, 0, 1) + 0.4 * np.clip(entropy / 8, 0, 1)
        return float(quality)

    def _ssim_quality(self, original_img, compressed_img):
        orig_gray = cv2.cvtColor(original_img, cv2.COLOR_BGR2GRAY)
        comp_gray = cv2.cvtColor(compressed_img, cv2.COLOR_BGR2GRAY)
        score, _ = ssim(orig_gray, comp_gray, full=True)
        return float(score)

    def _compute_score(self, quality, time_spent, image_size_kb):
        size_penalty = math.log1p(image_size_kb) / CONFIG['size_penalty_log_base']
        return (quality * CONFIG['quality_weight'] +
                (1.0 / (1.0 + time_spent)) * CONFIG['time_weight'] -
                size_penalty)

    # ---------- Адаптивное сжатие ----------
    def _enhance_and_compress(self, img_bgr):
        if not self.enable_enhance:
            return img_bgr
        h, w = img_bgr.shape[:2]
        new_w = int(w * CONFIG['enhance_upscale_factor'])
        new_h = int(h * CONFIG['enhance_upscale_factor'])
        upscaled = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        denoised = cv2.fastNlMeansDenoisingColored(
            upscaled, None,
            h=CONFIG['denoise_h'], hColor=CONFIG['denoise_hcolor'],
            templateWindowSize=CONFIG['denoise_template_window'],
            searchWindowSize=CONFIG['denoise_search_window']
        )
        return denoised

    def _compress_adaptive(self, img_bgr, target_kb=CONFIG['target_size_kb']):
        best = None
        best_ssim = 0.0
        orig_path = "temp_orig.png"
        cv2.imwrite(orig_path, img_bgr)
        orig_img = cv2.imread(orig_path)

        for q in range(self.webp_quality, CONFIG['webp_quality_min'], -CONFIG['webp_quality_step']):
            tmp_path = f"temp_{q}.webp"
            cv2.imwrite(tmp_path, img_bgr, [int(cv2.IMWRITE_WEBP_QUALITY), q])
            size_kb = os.path.getsize(tmp_path) / 1024
            compressed_img = cv2.imread(tmp_path)
            if compressed_img is None:
                continue
            ssim_val = self._ssim_quality(orig_img, compressed_img)
            if ssim_val > best_ssim:
                best_ssim = ssim_val
            if size_kb <= target_kb and ssim_val >= 0.9 * self.target_quality:
                best = (tmp_path, size_kb, ssim_val, q)
                break

        if os.path.exists(orig_path):
            os.remove(orig_path)
        return best

    # ---------- Промпт-менеджмент ----------
    def _compress_prompt(self, prompt):
        keywords = []
        for word in prompt.split(","):
            word = word.strip()
            if not word:
                continue
            imp = self.WORD_IMPORTANCE.get(word.lower(), 0.0)
            if imp < 0:
                continue
            if len(word) > 2:
                keywords.append(word)
        if len(keywords) > CONFIG['prompt_max_keywords']:
            keywords = keywords[:CONFIG['prompt_max_keywords']]
        if "minimalism" not in [k.lower() for k in keywords]:
            keywords.append("minimalism")
        if "clean composition" not in [k.lower() for k in keywords]:
            keywords.append("clean composition")
        return ", ".join(keywords)

    # ---------- Значимость события ----------
    def _event_significance(self, event_type, event_data):
        novelty = 1.0 / (1.0 + len(self.history_by_event.get(event_type, [])))
        impact = event_data.get("importance", 0.5)
        return (novelty * CONFIG['significance_novelty_weight'] +
                impact * CONFIG['significance_impact_weight'])

    # ---------- Параметры генерации ----------
    def _evolve_parameters(self):
        if len(self.history) < 10:
            return None
        top = sorted(self.history, key=lambda x: x.get("score", 0), reverse=True)[:10]
        parent = random.choice(top)
        new_seed = parent["seed"] + random.randint(-20, 20)
        new_steps = int(parent["steps"] * random.uniform(0.8, 1.2))
        new_steps = max(self.steps_range[0], min(self.steps_range[1], new_steps))
        return new_seed, new_steps

    def _analyze_history_for_event(self, event_type):
        entries = self.history_by_event.get(event_type, [])
        if len(entries) < 3:
            return None
        qualities = [e['quality'] for e in entries]
        avg_qual = np.mean(qualities)
        best_entry = max(entries, key=lambda x: x['quality'])
        if avg_qual < self.target_quality:
            steps = min(self.steps_range[1], int(self.default_steps * (1 + (self.target_quality - avg_qual))))
        else:
            steps = max(self.steps_range[0], int(self.default_steps * (1 - (avg_qual - self.target_quality))))
        seed = best_entry['seed'] + random.randint(-5, 5)
        return {'seed': seed, 'steps': steps, 'avg_quality': avg_qual, 'best_quality': best_entry['quality']}

    def _select_parameters(self, event_type, prompt, style):
        source = 'random'
        seed = random.randint(0, 2**32-1)
        steps = self.default_steps

        evolved = self._evolve_parameters()
        if evolved:
            seed, steps = evolved
            source = 'evolution'
            logger.info(f"🧬 Эволюция: seed={seed}, steps={steps}")
            return seed, steps, source

        rec = self._analyze_history_for_event(event_type)
        if rec:
            seed = rec['seed']
            steps = rec['steps']
            source = 'history'
            logger.info(f"📊 Анализ истории для {event_type}: среднее качество {rec['avg_quality']:.3f}, шаги -> {steps}")
            return seed, steps, source

        if self.tachyon and hasattr(self.tachyon, 'predict_outcome'):
            # можно добавить предсказание
            pass

        if self.history:
            best_global = sorted(self.history, key=lambda x: x.get('score', 0), reverse=True)[:5]
            if best_global:
                base_seed = random.choice(best_global)['seed']
                seed = base_seed + random.randint(-5, 5)
                steps = self.default_steps
                source = 'global_history'

        sys_state = self._get_system_state()
        if sys_state["gpu"] > 0.8 or sys_state["ram"] > 85:
            steps = max(self.steps_range[0], steps - 15)
            logger.info("🧯 Снижение нагрузки: уменьшаем steps")
        return seed, steps, source

    def _refine_prompt(self, prompt_base, suggestions):
        if not suggestions:
            return prompt_base
        add = ", ".join(suggestions)
        return f"{prompt_base}, {add}"

    def _simulate_candidates(self, event_type, prompt, style, importance):
        candidates = []
        sys = self._get_system_state()
        for _ in range(5):
            seed = random.randint(0, 2**32-1)
            steps = random.randint(*self.steps_range)
            features = {
                "event_type": event_type,
                "importance": importance,
                "prompt_len": len(prompt),
                "steps": steps,
                "seed_mod": seed % 1000,
                "cpu": sys["cpu"],
                "ram": sys["ram"],
                "gpu": sys["gpu"],
                "style": style
            }
            if self.tachyon:
                pred = self.tachyon.predict_outcome(features)
            else:
                pred = {"score": 0.5}
            candidates.append((seed, steps, pred))
        return candidates

    # ---------- Основная генерация ----------
    def generate(self, prompt, negative_prompt="", seed=None, steps=None, style=None):
        logger.info(f"🎨 Visionary.generate: prompt='{prompt[:80]}...'")
        self._load_model()
        if style:
            full_prompt = f"{prompt}, {style}"
        else:
            full_prompt = prompt
        full_prompt = self._compress_prompt(full_prompt)

        if seed is None or steps is None:
            seed, steps, source = self._select_parameters(self.last_event_type, full_prompt, style)
        else:
            source = 'manual'

        generator = torch.Generator(device=self.device).manual_seed(seed)
        logger.info(f"🎨 Генерация ({source}): '{full_prompt[:50]}...' seed={seed}, steps={steps}")

        start = time.time()
        with torch.inference_mode():
            image = self.pipe(
                full_prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=steps,
                generator=generator
            ).images[0]
        elapsed = time.time() - start
        quality = self._evaluate_quality(image)
        logger.info(f"✅ Генерация завершена за {elapsed:.2f}с, качество={quality:.4f}")

        self.total_generations += 1
        self.quality_history.append(quality)
        self.quality_by_steps[steps].append(quality)
        if quality > self.best_quality:
            self.best_quality = quality

        if len(self.quality_history) > CONFIG['quality_update_window']:
            sorted_q = sorted(self.quality_history)
            top10 = sorted_q[int(len(sorted_q)*CONFIG['quality_percentile']/100):]
            self.target_quality = np.mean(top10)
            logger.info(f"🎯 Целевое качество обновлено: {self.target_quality:.3f}")

        return image, quality, seed, steps, source, elapsed

    async def async_generate(self, prompt, negative_prompt="", seed=None, steps=None, style=None):
        return await asyncio.to_thread(self.generate, prompt, negative_prompt, seed, steps, style)

    # ---------- Сохранение и вклад в P=NP ----------
    def save(self, image, event_name, prompt, quality, seed, steps, source, generation_time, importance, improvement_gain=0):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = event_name.replace(" ", "_").replace("/", "_")[:30]

        img_np = np.array(image)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        if self.enable_enhance:
            img_bgr = self._enhance_and_compress(img_bgr)

        compressed = self._compress_adaptive(img_bgr, target_kb=CONFIG['target_size_kb'])
        if compressed is None:
            quality_webp = self.webp_quality
            tmp_path = "temp_fallback.webp"
            cv2.imwrite(tmp_path, img_bgr, [int(cv2.IMWRITE_WEBP_QUALITY), quality_webp])
            size_kb = os.path.getsize(tmp_path) / 1024
            orig_path = "temp_orig.png"
            cv2.imwrite(orig_path, img_bgr)
            orig_img = cv2.imread(orig_path)
            compressed_img = cv2.imread(tmp_path)
            ssim_val = self._ssim_quality(orig_img, compressed_img) if compressed_img is not None else 0.0
            os.remove(orig_path)
            os.remove(tmp_path)
        else:
            tmp_path, size_kb, ssim_val, quality_webp = compressed
            filename_webp = f"event_{safe_name}_{timestamp}_q{quality:.3f}_s{seed}_{quality_webp}.webp"
            image_path_webp = os.path.join(self.image_dir, filename_webp)
            os.rename(tmp_path, image_path_webp)

        if self.save_png:
            filename_png = f"event_{safe_name}_{timestamp}_q{quality:.3f}_s{seed}.png"
            image_path_png = os.path.join(self.image_dir, filename_png)
            image.save(image_path_png)
            logger.info(f"📸 PNG (отладка) сохранён: {image_path_png}")

        score = self._compute_score(quality, generation_time, size_kb)
        sys_state = self._get_system_state()

        meta = {
            "timestamp": timestamp,
            "event": event_name,
            "prompt": prompt,
            "seed": seed,
            "steps": steps,
            "quality": quality,
            "source": source,
            "generation_time": generation_time,
            "size_kb": size_kb,
            "ssim": ssim_val,
            "webp_quality": quality_webp,
            "score": score,
            "improvement_gain": improvement_gain,
            "importance": importance,
            "system_state": sys_state,
            "image_file": os.path.basename(image_path_webp),
            "event_details": self.last_event_details
        }
        meta_path = os.path.join(WORMHOLE_DIR, f"vision_{timestamp}.json")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        janus_db.insert_visionary_generation(
            event_type=event_name,
            prompt=prompt,
            seed=seed,
            steps=steps,
            quality=quality,
            generation_time=generation_time,
            source=source,
            image_path=image_path_webp
        )

        logger.info(f"💾 Изображение сохранено: {image_path_webp} (размер: {size_kb:.1f} КБ, SSIM: {ssim_val:.3f})")
        logger.info(f"📄 Метаданные в wormhole: {meta_path}")

        # Обновляем историю эффективности
        eff = quality / (size_kb + 1e-6)
        self.size_efficiency.append(eff)
        if len(self.size_efficiency) > 20:
            avg_eff = np.mean(self.size_efficiency)
            if avg_eff < 0.002 and self.webp_quality > CONFIG['webp_quality_min'] + 5:
                self.webp_quality -= CONFIG['webp_quality_step']
                logger.info(f"📉 Низкая эффективность сжатия, уменьшаем WebP качество до {self.webp_quality}")
            elif avg_eff > 0.005 and self.webp_quality < 90:
                self.webp_quality += CONFIG['webp_quality_step']
                logger.info(f"📈 Хорошая эффективность, увеличиваем WebP качество до {self.webp_quality}")

        # Добавляем в историю лучших
        if len(self.history) > 0:
            scores = [h.get('score', 0) for h in self.history]
            threshold = np.percentile(scores, 80)
            if score > threshold:
                self.history.append(meta)
                self.history_by_event[event_name].append(meta)
                logger.info(f"🏆 Генерация добавлена в историю (score > {threshold:.3f})")
        else:
            self.history.append(meta)
            self.history_by_event[event_name].append(meta)

        # === ВКЛАД В ПОИСК P=NP ===
        if self.meta_goal is not None:
            contribution = min(score * CONFIG['pnp_contribution_scale'], CONFIG['pnp_contribution_max_per_generation'])
            self.meta_goal.discovery_progress += contribution
            self.meta_goal.discovery_progress = min(self.meta_goal.discovery_progress, 1.0)
            logger.info(f"🧠 Visionary внёс вклад в P=NP: +{contribution:.4f} (прогресс: {self.meta_goal.discovery_progress:.4f})")
            if quality > 0.8:
                self.meta_goal.belief_p_equals_np += 0.01
                self.meta_goal.belief_p_equals_np = min(self.meta_goal.belief_p_equals_np, 1.0)
            elif quality < 0.4:
                self.meta_goal.belief_p_equals_np -= 0.005
                self.meta_goal.belief_p_equals_np = max(self.meta_goal.belief_p_equals_np, 0.0)

        return image_path_webp, score, size_kb

    # ---------- Фоновая обработка очереди ----------
    async def _process_single_job(self, job):
        event_type = job['event_type']
        event_data = job['event_data']
        world = job['world']
        significance = job['significance']
        prompt_base = job['prompt_base']
        style = job['style']
        negative = job['negative']
        seed = job['seed']
        steps = job['steps']
        try:
            logger.info(f"🖼️ Начало фоновой генерации для события {event_type} (seed={seed}, steps={steps})")
            self.last_event_type = event_type
            self.last_event_details = event_data

            max_iters = 3
            if self.total_generations > 0:
                avg_time = np.mean([h.get('generation_time', 1) for h in self.history]) if self.history else 5.0
                if avg_time > 6:
                    max_iters = 2
                if avg_time > 8:
                    max_iters = 1

            best = None
            prompt = prompt_base
            all_results = []
            for i in range(max_iters):
                image, quality, seed_i, steps_i, source, elapsed = await self.async_generate(
                    prompt, negative, seed=seed, steps=steps, style=style
                )
                result = {"image": image, "quality": quality, "seed": seed_i, "steps": steps_i,
                          "time": elapsed, "prompt": prompt, "source": source}
                all_results.append(result)

                if best is None or quality > best["quality"]:
                    best = result

                critique = self.critic.analyze(prompt, quality, steps_i, elapsed)

                if critique["status"] == "perfect":
                    logger.info("💎 Достигнут идеал — стоп")
                    break

                if i == max_iters - 1:
                    break

                if quality > self.target_quality and elapsed < 5:
                    logger.info("⚖️ Баланс достигнут — стоп")
                    break

                prompt = self._refine_prompt(prompt_base, critique["suggestions"])
                if seed is None:
                    seed = seed_i + random.randint(-10, 10)
                else:
                    seed += random.randint(-10, 10)
                steps = int(steps_i * random.uniform(0.9, 1.1))
                steps = max(self.steps_range[0], min(self.steps_range[1], steps))

            best_image = best["image"]
            best_quality = best["quality"]
            best_seed = best["seed"]
            best_steps = best["steps"]
            best_elapsed = best["time"]
            best_prompt = best["prompt"]
            best_source = best["source"]

            improvement_gain = best_quality - all_results[0]["quality"] if len(all_results) > 1 else 0.0

            image_path, score, size_kb = self.save(
                best_image, event_type, best_prompt, best_quality,
                best_seed, best_steps, best_source, best_elapsed,
                significance, improvement_gain
            )

            # Контрфакты (если есть)
            if self.counterfactual and self.tachyon:
                sys = self._get_system_state()
                features = {
                    "event_type": event_type,
                    "importance": significance,
                    "prompt_len": len(best_prompt),
                    "steps": best_steps,
                    "seed_mod": best_seed % 1000,
                    "cpu": sys["cpu"],
                    "ram": sys["ram"],
                    "gpu": sys["gpu"],
                    "style": style
                }
                real_outcome = {"quality": best_quality, "time": best_elapsed, "size": size_kb, "score": score}
                sims = self.counterfactual.simulate(features)
                self.counterfactual.learn_from_counterfactuals(features, real_outcome)
                if self.counterfactual.evaluate_decision(real_outcome, sims):
                    logger.info("🤯 Найдено лучшее альтернативное будущее (мы могли сделать лучше)")

            self.self_model.update({"quality": best_quality, "time": best_elapsed, "score": score})

            if self.counterfactual and 'sims' in locals():
                alt_scores = [s['prediction'].get('score',0) for s in sims if s['prediction']]
                regret = self.regret_engine.compute(score, alt_scores)
                logger.info(f"😞 Сожаление: {regret:.3f}")
                new_mode = self.strategy.adjust(self.self_model, regret)
                logger.info(f"🧠 Новая стратегия: {new_mode}")

            if hasattr(world, 'meta') and hasattr(world.meta, 'analyze'):
                state_analysis = world.meta.analyze()
                if state_analysis:
                    reflection = self.narrative.reflect(state_analysis)
                    self.narrative.speak(reflection)

        except Exception as e:
            logger.error(f"Ошибка фоновой генерации для события {event_type}: {e}", exc_info=True)

    async def process_queue(self):
        """Фоновый обработчик очереди заданий. Вызывается в отдельной задаче."""
        while True:
            if self.pending_jobs:
                async with self._processing_lock:
                    if self.pending_jobs:
                        job = self.pending_jobs.popleft()
                        await self._process_single_job(job)
            else:
                await asyncio.sleep(0.5)

    # ---------- Обработка события (основной метод) ----------
    async def on_event(self, event_type, event_data, world, gaming_mode=False):
        logger.info(f"🔮 Visionary.on_event: {event_type}, данные: {event_data}, gaming_mode={gaming_mode}")
        if event_type not in self.IMPORTANT_EVENTS:
            logger.debug(f"Событие {event_type} не в списке важных, пропускаем")
            return

        try:
            if not self.storyteller:
                logger.warning("Нет storyteller, пропускаем событие")
                return

            # Вычисляем значимость
            significance = self._event_significance(event_type, event_data)
            if significance < CONFIG['significance_threshold']:
                logger.info(f"🧊 Событие отфильтровано (significance={significance:.2f})")
                return

            # Подготовка данных для генерации
            extra = self._build_event_context(event_type, event_data, world)
            context = {
                'event_type': event_type,
                'data': event_data,
                'extra': extra,
                'cycle': getattr(world, 'tick', 0),
                'population': len(world.population) if hasattr(world, 'population') else 0,
                'observer': 'Janus'
            }
            prompt_base = self.storyteller.generate_story(context, max_len=60)
            negative = "worst quality, low quality, ugly, deformed, blurry, text, watermark"
            style = self._get_style(event_type)

            # Симуляция кандидатов и выбор лучших параметров
            candidates = self._simulate_candidates(event_type, prompt_base, style, significance)
            seed, steps = None, None
            if candidates:
                valid_candidates = [(s, st, p) for s, st, p in candidates if p is not None]
                if valid_candidates:
                    best_candidate = max(valid_candidates, key=lambda x: x[2].get('score', 0))
                    seed, steps, pred = best_candidate
                    logger.info(f"🔮 Tachyon выбрал будущее: score={pred.get('score',0):.3f}, steps={steps}")
                else:
                    logger.info("⚠️ Tachyon не дал предсказаний, использую стандартный выбор")
            else:
                logger.info("⚠️ Не удалось сгенерировать кандидатов")

            # Если игровой режим – откладываем генерацию
            if gaming_mode:
                logger.info(f"🎮 Игровой режим: откладываем генерацию для события {event_type}")
                job = {
                    'event_type': event_type,
                    'event_data': event_data,
                    'world': world,
                    'significance': significance,
                    'prompt_base': prompt_base,
                    'style': style,
                    'negative': negative,
                    'seed': seed,
                    'steps': steps
                }
                self.pending_jobs.append(job)
                return

            # Иначе – синхронная генерация
            self.last_event_type = event_type
            self.last_event_details = event_data

            max_iters = 3
            if self.total_generations > 0:
                avg_time = np.mean([h.get('generation_time', 1) for h in self.history]) if self.history else 5.0
                if avg_time > 6:
                    max_iters = 2
                if avg_time > 8:
                    max_iters = 1

            best = None
            prompt = prompt_base
            all_results = []

            for i in range(max_iters):
                image, quality, seed_i, steps_i, source, elapsed = await self.async_generate(
                    prompt, negative, seed=seed, steps=steps, style=style
                )
                result = {"image": image, "quality": quality, "seed": seed_i, "steps": steps_i,
                          "time": elapsed, "prompt": prompt, "source": source}
                all_results.append(result)

                if best is None or quality > best["quality"]:
                    best = result

                critique = self.critic.analyze(prompt, quality, steps_i, elapsed)

                if critique["status"] == "perfect":
                    logger.info("💎 Достигнут идеал — стоп")
                    break

                if i == max_iters - 1:
                    break

                if quality > self.target_quality and elapsed < 5:
                    logger.info("⚖️ Баланс достигнут — стоп")
                    break

                prompt = self._refine_prompt(prompt_base, critique["suggestions"])
                if seed is None:
                    seed = seed_i + random.randint(-10, 10)
                else:
                    seed += random.randint(-10, 10)
                steps = int(steps_i * random.uniform(0.9, 1.1))
                steps = max(self.steps_range[0], min(self.steps_range[1], steps))

            best_image = best["image"]
            best_quality = best["quality"]
            best_seed = best["seed"]
            best_steps = best["steps"]
            best_elapsed = best["time"]
            best_prompt = best["prompt"]
            best_source = best["source"]

            improvement_gain = best_quality - all_results[0]["quality"] if len(all_results) > 1 else 0.0

            image_path, score, size_kb = self.save(
                best_image, event_type, best_prompt, best_quality,
                best_seed, best_steps, best_source, best_elapsed,
                significance, improvement_gain
            )

            # Контрфакты
            if self.counterfactual and self.tachyon:
                sys = self._get_system_state()
                features = {
                    "event_type": event_type,
                    "importance": significance,
                    "prompt_len": len(best_prompt),
                    "steps": best_steps,
                    "seed_mod": best_seed % 1000,
                    "cpu": sys["cpu"],
                    "ram": sys["ram"],
                    "gpu": sys["gpu"],
                    "style": style
                }
                real_outcome = {"quality": best_quality, "time": best_elapsed, "size": size_kb, "score": score}
                sims = self.counterfactual.simulate(features)
                self.counterfactual.learn_from_counterfactuals(features, real_outcome)
                if self.counterfactual.evaluate_decision(real_outcome, sims):
                    logger.info("🤯 Найдено лучшее альтернативное будущее (мы могли сделать лучше)")

            self.self_model.update({"quality": best_quality, "time": best_elapsed, "score": score})

            if self.counterfactual and 'sims' in locals():
                alt_scores = [s['prediction'].get('score',0) for s in sims if s['prediction']]
                regret = self.regret_engine.compute(score, alt_scores)
                logger.info(f"😞 Сожаление: {regret:.3f}")
                new_mode = self.strategy.adjust(self.self_model, regret)
                logger.info(f"🧠 Новая стратегия: {new_mode}")

            state_analysis = getattr(world.meta, 'analyze', lambda: None)()
            if state_analysis:
                reflection = self.narrative.reflect(state_analysis)
                self.narrative.speak(reflection)

        except Exception as e:
            logger.error(f"Ошибка в VisionaryEngine.on_event: {e}", exc_info=True)

    # ---------- Вспомогательные методы ----------
    def _build_event_context(self, event_type, event_data, world):
        extra = {}
        if event_type == "EXTINCTION":
            species_names = event_data.get('species', [])
            extra['species_names'] = ', '.join(species_names) if isinstance(species_names, list) else str(species_names)
            extra['mood'] = 'sadness, loss'
        elif event_type == "RECORD":
            agent_id = event_data.get('agent')
            if hasattr(world, 'population'):
                agent = next((a for a in world.population if a.id.startswith(agent_id)), None)
                if agent:
                    extra['agent_name'] = f"{agent.race} {agent.agent_class}"
                    extra['agent_level'] = agent.level
            extra['score'] = event_data.get('score', 0)
            extra['mood'] = 'triumph, joy'
        elif event_type == "NEW_SPECIES":
            extra['new_species_name'] = event_data.get('name', 'неизвестный вид')
            extra['arch_type'] = event_data.get('arch_type', 'неизвестный')
            extra['mood'] = 'wonder, curiosity'
        elif event_type == "RAID":
            extra['boss_name'] = event_data.get('boss_name', 'босс')
            extra['win'] = event_data.get('win', False)
            extra['mood'] = 'victory' if extra['win'] else 'defeat'
        elif event_type == "INSTITUTION_FOUNDED":
            extra['institution_name'] = event_data.get('institution', {}).get('name', 'институт')
            extra['founder'] = event_data.get('founder', {}).get('id', 'неизвестный')
            extra['mood'] = 'hope, order'
        elif event_type == "WORMHOLE":
            extra['text'] = event_data.get('text', '')
            extra['mood'] = 'mystery'
        return extra

    def _get_style(self, event_type):
        styles = {
            "RECORD": "bright colors, celebration, epic, shiny, glowing",
            "EXTINCTION": "dark, gloomy, abandoned, ruins, mist, dramatic",
            "NEW_SPECIES": "birth, emergence, colorful, magical, transformation",
            "WORMHOLE": "mysterious, cosmic, abstract, surreal",
            "RAID": "battle, action, intense, fire, explosion",
            "INSTITUTION_FOUNDED": "architecture, monument, ceremonial, grand",
            "DEFAULT": "fantasy, digital art, epic"
        }
        return styles.get(event_type, styles["DEFAULT"])

    def load_history(self):
        try:
            conn = sqlite3.connect(janus_db.DB_PATH)
            c = conn.cursor()
            c.execute('''SELECT event_type, prompt, seed, steps, quality, generation_time, source
                         FROM visionary_generations ORDER BY id DESC LIMIT 1000''')
            rows = c.fetchall()
            conn.close()
            for row in rows:
                entry = {
                    'event_type': row[0], 'prompt': row[1], 'seed': row[2], 'steps': row[3],
                    'quality': row[4], 'generation_time': row[5], 'source': row[6],
                    'score': self._compute_score(row[4], row[5], 0)
                }
                self.history.append(entry)
                self.history_by_event[row[0]].append(entry)
                self.quality_by_steps[row[3]].append(row[4])
            logger.info(f"📚 Загружено {len(self.history)} записей из БД")
        except Exception as e:
            logger.warning(f"Не удалось загрузить историю из БД: {e}")

        if len(self.history) == 0:
            history_file = os.path.join(WORMHOLE_DIR, "visionary_history.json")
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for entry in data[-1000:]:
                        self.history.append(entry)
                        ev = entry.get('event_type', 'unknown')
                        self.history_by_event[ev].append(entry)
                        self.quality_by_steps[entry.get('steps', 50)].append(entry.get('quality', 0))
                    logger.info(f"📚 Загружено {len(self.history)} записей из wormhole")
                except Exception as e2:
                    logger.error(f"Ошибка загрузки истории из wormhole: {e2}")