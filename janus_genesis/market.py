#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKET v2.0 — система торговли артефактами с динамическими ценами,
стратегиями агентов, обучением, аналитикой и интеграцией с экосистемой Януса.
"""

import random
import json
import os
import time
import math
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any, Tuple

from config import RAW_LOGS_DIR

# Для работы с предметами (импорт из inventory, если нужно)
# В реальной системе Item определён в другом модуле, но для автономности определим здесь
class Item:
    def __init__(self, name, effect=None, weight=1, value=10, unique=False, knowledge=None, fake=False):
        self.name = name
        self.effect = effect or {}
        self.weight = weight
        self.value = value
        self.unique = unique
        self.knowledge = knowledge or {}   # словарь гиперпараметров: {'lr': 0.001, ...}
        self.fake = fake

class Market:
    def __init__(self, world, save_file=None, social_engine=None, visionary=None, language_engine=None):
        self.world = world
        self.social_engine = social_engine   # для обучения стратегиям
        self.visionary = visionary
        self.language_engine = language_engine
        self.listings = []  # каждый элемент: (seller_id, item, price, created_tick)
        self.price_history = defaultdict(list)  # item.name -> список цен
        self.transaction_log = deque(maxlen=1000)  # для аналитики
        self.tick = 0  # глобальный счётчик времени (обновляется из мира)
        if save_file is None:
            self.save_file = os.path.join(RAW_LOGS_DIR, "market_listings.json")
        else:
            self.save_file = save_file
        self.load()

    # ---------- Вспомогательные ----------
    def _get_current_tick(self):
        """Возвращает текущий тик из мира или локальный счётчик."""
        return getattr(self.world, 'tick', self.tick)

    def _estimate_price(self, item, demand_factor=1.0):
        """
        Динамическая цена на основе истории сделок и текущего спроса.
        demand_factor – дополнительный множитель от стратегии покупателя.
        """
        history = self.price_history.get(item.name, [])
        if not history:
            base_price = item.value
        else:
            avg = sum(history) / len(history)
            # цена колеблется около среднего
            base_price = avg * random.uniform(0.9, 1.1)

        # Учёт количества выставленных лотов (предложение)
        supply = len([l for l in self.listings if l[1].name == item.name])
        scarcity = 1.0 / (1.0 + supply)  # чем больше предложение, тем меньше множитель
        # Итоговая цена с учётом спроса/предложения
        price = base_price * (0.8 + scarcity * 0.6) * demand_factor
        return max(1, int(price))

    # ---------- Публичные методы (основные) ----------
    def list_item(self, seller_id, item, price=None, created_tick=None):
        """Выставить предмет на продажу. Если price не указан, используется динамическая."""
        if price is None:
            price = self._estimate_price(item)
        created = created_tick if created_tick is not None else self._get_current_tick()
        self.listings.append((seller_id, item, price, created))
        self.save()
        return True

    # Метод для обратной совместимости со старым Market
    def add_listing(self, item, price, seller_id):
        """Алиас для list_item, сохраняет обратную совместимость."""
        return self.list_item(seller_id, item, price)

    def remove_listing(self, index):
        """Удаляет листинг по индексу (обратная совместимость)."""
        if 0 <= index < len(self.listings):
            return self.listings.pop(index)
        return None

    def buy_item(self, buyer_id, listing_index):
        """Покупка по индексу листинга (старый метод, для обратной совместимости)."""
        if listing_index >= len(self.listings):
            return False, "Invalid listing"
        seller_id, item, price, created = self.listings[listing_index]
        return self._complete_transaction(buyer_id, seller_id, item, price)

    def buy_best_deal(self, buyer_id):
        """Умная покупка: выбирает лучший лот для покупателя."""
        buyer = self.world.get_agent_by_id(buyer_id)
        if not buyer:
            return False, "Agent not found"
        best_score = -1
        best_idx = None
        for idx, (seller_id, item, price, created) in enumerate(self.listings):
            if seller_id == buyer_id:
                continue
            if not buyer.can_afford(price):
                continue
            if item.unique and any(i.name == item.name for i in buyer.inventory):
                continue
            if buyer.weight + item.weight > buyer.max_weight:
                continue
            # Оценка выгоды: полезность / цена
            utility = self._item_utility(item, buyer)
            score = utility / (price + 1)
            # Учёт стратегии покупателя
            if hasattr(buyer, 'trade_strategy'):
                if buyer.trade_strategy.get("greed", 0) > 0.7:
                    score *= 1.2  # жадные больше ценят выгоду
                if buyer.trade_strategy.get("risk", 0) > 0.7 and price < item.value * 0.7:
                    score *= 1.5  # рискованные любят дешёвое
                if buyer.trade_strategy.get("collector", False) and item.unique:
                    score *= 2.0
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            return False, "No suitable deals"
        seller_id, item, price, created = self.listings[best_idx]
        return self._complete_transaction(buyer_id, seller_id, item, price)

    def _item_utility(self, item, buyer):
        """Оценивает полезность предмета для покупателя."""
        base = item.value
        # Если предмет содержит знания, полезность выше
        if item.knowledge:
            # оцениваем, насколько знания полезны для агента (можно сравнить с его текущей конфигурацией)
            # упрощённо: считаем, что любое знание полезно
            base += 50
        # Уникальные предметы могут иметь большую ценность для коллекционера
        if item.unique:
            base *= 2
        return base

    def _complete_transaction(self, buyer_id, seller_id, item, price):
        """Выполняет сделку, обновляет состояние, логирует."""
        buyer = self.world.get_agent_by_id(buyer_id)
        seller = self.world.get_agent_by_id(seller_id)
        if not buyer or not seller:
            return False, "Agent not found"
        if not buyer.can_afford(price):
            return False, "Not enough gold"
        if item.unique and any(i.name == item.name for i in buyer.inventory):
            return False, "Already have unique item"
        if buyer.weight + item.weight > buyer.max_weight:
            return False, "Inventory full"

        # Проверка на фейк
        if item.fake:
            # Шанс обнаружить фейк в зависимости от интеллекта агента
            intelligence = getattr(buyer, 'intelligence', 0.5)
            if random.random() < intelligence:
                return False, "Item is fake! You detected the fraud."

        # Совершаем сделку
        if buyer.spend(price) and seller.gold >= 0:
            seller.gold += price
            seller.remove_item(item)
            buyer.add_item(item)
            # Применяем знания, если есть
            if item.knowledge:
                # Используем метод агента для применения гиперпараметров
                buyer.apply_hyper_effect(item.knowledge)
            # Убираем из листинга
            self.listings = [l for l in self.listings if not (l[0]==seller_id and l[1]==item)]
            self.save()
            # Логируем транзакцию
            self.transaction_log.append({
                "buyer": buyer_id, "seller": seller_id, "item": item.name,
                "price": price, "tick": self._get_current_tick()
            })
            self.price_history[item.name].append(price)
            # Оповещаем мир через event_bus
            if hasattr(self.world, 'event_bus'):
                self.world.event_bus.emit("trade", buyer=buyer, seller=seller, item=item, price=price)
            # Обучение стратегии через SocialEngine
            if self.social_engine:
                # Агенты могут учиться на успешных сделках
                self.social_engine.add_success(buyer)  # можно добавить свою логику
            # Генерация нарратива через Visionary/LanguageEngine
            if self.visionary and random.random() < 0.1:
                prompt = f"trade of {item.name} between {buyer.id[:4]} and {seller.id[:4]}"
                # Асинхронно, но можно синхронно
                # Здесь просто вызываем, предполагая, что у visionary есть метод on_event
                # self.visionary.on_event("TRADE", {"item": item.name, "buyer": buyer.id, "seller": seller.id}, self.world)
                pass
            if self.language_engine:
                # Учим языковую модель на описании сделки
                text = f"{buyer.id[:4]} bought {item.name} from {seller.id[:4]} for {price} gold."
                self.language_engine.train_step(text, lr=0.005)
            return True, "Purchase successful"
        return False, "Transaction failed"

    def get_agent_listings(self, agent_id):
        """Возвращает список предметов, выставленных агентом."""
        return [(idx, item, price) for idx, (sid, item, price, _) in enumerate(self.listings) if sid == agent_id]

    def clear_expired(self, max_age_cycles=100):
        """Удаляет старые листинги (старше max_age_cycles тиков)."""
        current_tick = self._get_current_tick()
        self.listings = [(sid, item, price, created) for (sid, item, price, created) in self.listings
                         if current_tick - created < max_age_cycles]
        self.save()

    def get_market_stats(self):
        """Возвращает аналитику рынка."""
        if not self.transaction_log:
            return {"total_trades": 0, "most_traded": None, "avg_price": 0}
        item_counts = defaultdict(int)
        total_price = 0
        for t in self.transaction_log:
            item_counts[t["item"]] += 1
            total_price += t["price"]
        most_traded = max(item_counts, key=item_counts.get) if item_counts else None
        avg_price = total_price / len(self.transaction_log)
        return {
            "total_trades": len(self.transaction_log),
            "most_traded": most_traded,
            "avg_price": avg_price,
            "unique_items_traded": len(set(t["item"] for t in self.transaction_log))
        }

    def update_tick(self):
        """Вызывается из мира при каждом тике."""
        self.tick += 1
        # Периодически чистим старые лоты
        if self.tick % 50 == 0:
            self.clear_expired()

    def save(self):
        data = []
        for seller_id, item, price, created in self.listings:
            data.append({
                'seller_id': seller_id,
                'item': {
                    'name': item.name,
                    'effect': item.effect,
                    'weight': item.weight,
                    'value': item.value,
                    'unique': item.unique,
                    'knowledge': item.knowledge,
                    'fake': item.fake
                },
                'price': price,
                'created_tick': created
            })
        tmp_file = self.save_file + ".tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_file, self.save_file)

    def load(self):
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.listings = []
                for entry in data:
                    item = Item(
                        name=entry['item']['name'],
                        effect=entry['item']['effect'],
                        weight=entry['item']['weight'],
                        value=entry['item']['value'],
                        unique=entry['item']['unique'],
                        knowledge=entry['item'].get('knowledge', {}),
                        fake=entry['item'].get('fake', False)
                    )
                    self.listings.append((entry['seller_id'], item, entry['price'], entry.get('created_tick', 0)))
            except Exception as e:
                print(f"Ошибка загрузки рынка: {e}")

    # ---------- Методы для агентов (стратегии) ----------
    def get_trade_strategy(self, agent):
        """Возвращает текущую торговую стратегию агента."""
        if not hasattr(agent, 'trade_strategy'):
            # инициализируем случайную стратегию
            agent.trade_strategy = {
                "greed": random.uniform(0.3, 0.9),
                "risk": random.uniform(0.2, 0.8),
                "collector": random.choice([True, False])
            }
        return agent.trade_strategy

    def learn_trade_strategy(self, agent, other_agent, success):
        """
        Обучение стратегии на основе успеха других агентов.
        Использует social_engine для копирования.
        """
        if self.social_engine and success:
            # Копируем стратегию успешного агента
            agent.trade_strategy = other_agent.trade_strategy.copy()
            return True
        return False