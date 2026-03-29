#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HRAIN SERVER v78 — ИНТЕГРАЦИЯ С ЖИВЫМ ГРАФОМ (PHYSARUM)
- Использует HrainGraphEngine с инкрементальными обновлениями
- WebSocket для потоковой передачи diff
- Сохранение/восстановление состояния графа
- Полная совместимость с Android, Cardputer и другими устройствами
- Добавлена обратная совместимость с фронтендом через /api/hrain/state и /api/hrain/save
- Атомарная запись в device_data.json с буферизацией для предотвращения гонок
"""

import os
import json
import logging
import asyncio
import time
import random
from aiohttp import web
from config import RAW_LOGS_DIR
import janus_db
from hrain_graph_engine import HrainGraphEngine

logger = logging.getLogger("JANUS")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

HRAIN_STATE_FILE = os.path.join(RAW_LOGS_DIR, "hrain_graph_state.json")
DEVICE_DATA_FILE = os.path.join(RAW_LOGS_DIR, "device_data.json")
DEVICE_COMMANDS_FILE = os.path.join(RAW_LOGS_DIR, "device_commands.json")

active_websockets = set()
state_lock = asyncio.Lock()
graph_engine = None  # будет инициализирован при старте

# ========== БУФЕРИЗАЦИЯ ДАННЫХ УСТРОЙСТВ ==========
pending_data = []
pending_lock = asyncio.Lock()
flush_interval = 2.0  # секунды между сбросом

def normalize_data(data, device_id):
    """Преобразует строковые данные от m5_adv_beacon в словарь."""
    if isinstance(data, str) and device_id == 'm5_adv_beacon':
        # Ожидаемый формат: "timestamp,f1,f2,temp,hum,shock,entropy,m2r,fitness"
        parts = data.split(',')
        if len(parts) >= 9:
            try:
                return {
                    'f1': float(parts[1]),
                    'f2': float(parts[2]),
                    'temp': float(parts[3]),
                    'hum': float(parts[4]),
                    'shock': float(parts[5]),
                    'entropy': float(parts[6]),
                    'm2r': float(parts[7]),
                    'fitness': float(parts[8]),
                    'raw': data  # сохраняем исходную строку для отладки
                }
            except (ValueError, IndexError):
                pass
    return data

async def flush_pending():
    """Фоновый таск: раз в flush_interval сбрасывает накопленные данные в файл."""
    while True:
        await asyncio.sleep(flush_interval)
        async with pending_lock:
            if not pending_data:
                continue
            # Загружаем существующий файл
            try:
                with open(DEVICE_DATA_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    existing = json.loads(content) if content else []
            except (json.JSONDecodeError, FileNotFoundError):
                existing = []
            # Добавляем новые записи
            existing.extend(pending_data)
            # Ограничиваем размер
            if len(existing) > 1000:
                existing = existing[-1000:]
            # Атомарная запись через временный файл
            tmp = DEVICE_DATA_FILE + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2)
            os.replace(tmp, DEVICE_DATA_FILE)
            pending_data.clear()
            logger.debug(f"Сброшено {len(pending_data)} записей в device_data.json")

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
async def broadcast_update(diffs):
    """Рассылает инкрементальные обновления всем WebSocket-клиентам."""
    if not active_websockets:
        return
    message = json.dumps({"type": "DIFF", "data": diffs})
    for ws in active_websockets:
        try:
            await ws.send_str(message)
        except Exception as e:
            logger.error(f"Ошибка отправки WS: {e}")

async def save_graph_state():
    """Периодически сохраняет состояние графа в файл."""
    while True:
        await asyncio.sleep(60)  # раз в минуту
        async with state_lock:
            try:
                state = graph_engine.get_full_state()
                tmp = HRAIN_STATE_FILE + ".tmp"
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(state, f, indent=2)
                os.replace(tmp, HRAIN_STATE_FILE)
                logger.debug("Граф сохранён")
            except Exception as e:
                logger.error(f"Ошибка сохранения графа: {e}")

async def load_graph_state():
    """Загружает состояние графа из файла при старте."""
    if os.path.exists(HRAIN_STATE_FILE):
        try:
            with open(HRAIN_STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            graph_engine.load_full_state(state)
            logger.info(f"Граф загружен: {len(graph_engine.nodes)} узлов, {len(graph_engine.edges)} рёбер")
        except Exception as e:
            logger.error(f"Ошибка загрузки графа: {e}")

# ==============================================================================
# HTTP ОБРАБОТЧИКИ
# ==============================================================================
async def handle_index(request):
    """Отдаёт index.html (HRAIN) из папки templates."""
    index_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if not os.path.exists(index_path):
        return web.Response(text="index.html не найден", status=404)
    return web.FileResponse(index_path)

async def handle_get_state(request):
    """Возвращает текущий граф в формате, совместимом со старым фронтендом."""
    async with state_lock:
        full_state = graph_engine.get_full_state()
        # Преобразуем в формат {nodes, links}
        nodes = []
        for nid, node in full_state['nodes'].items():
            nodes.append({
                'id': nid,
                'label': node['data'].get('label', node['type']),
                'emoji': node['data'].get('emoji', '🔮'),
                'type': node['type'],
                'x': node['data'].get('x', 0),
                'y': node['data'].get('y', 0),
                'parentId': node['data'].get('parentId'),
                'description': node['data'].get('description', ''),
                'chatHistory': node['data'].get('chatHistory', [])
            })
        links = []
        for key, edge in full_state['edges'].items():
            src, dst = key.split('->')
            links.append({'source': src, 'target': dst})
        return web.json_response({'nodes': nodes, 'links': links})

async def handle_save_state(request):
    """Принимает граф от фронтенда и синхронизирует с движком."""
    try:
        data = await request.json()
        # Строим состояние для движка
        new_nodes = {}
        for n in data.get('nodes', []):
            new_nodes[n['id']] = {
                'id': n['id'],
                'type': n.get('type', 'default'),
                'data': {
                    'label': n.get('label', 'Node'),
                    'emoji': n.get('emoji', '🔮'),
                    'x': n.get('x', 0),
                    'y': n.get('y', 0),
                    'parentId': n.get('parentId'),
                    'description': n.get('description', ''),
                    'chatHistory': n.get('chatHistory', [])
                },
                'energy': 1.0,
                'last_used': graph_engine.tick,
                'cluster': None
            }
        new_edges = {}
        for l in data.get('links', []):
            src = l['source']
            dst = l['target']
            key = f"{src}->{dst}"
            new_edges[key] = {
                'weight': 1.0,
                'direction': 'bidir',
                'last_traversal': graph_engine.tick
            }
        async with state_lock:
            graph_engine.nodes = new_nodes
            graph_engine.edges = new_edges
            # Обновляем счётчик ID
            max_id = 0
            for nid in new_nodes:
                if '_' in nid:
                    try:
                        num = int(nid.split('_')[1])
                        if num > max_id:
                            max_id = num
                    except:
                        pass
            graph_engine.node_counter = max_id + 1
            graph_engine.tick += 1
            # Сохраняем состояние в файл
            state = graph_engine.get_full_state()
            tmp = HRAIN_STATE_FILE + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, HRAIN_STATE_FILE)
        await broadcast_update([])  # не отправляем diff, так как весь граф обновлён
        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка сохранения графа: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_janus_action(request):
    """Принимает команды от HRAIN (синтез и т.д.)."""
    try:
        data = await request.json()
        prompt = data.get('text', '')
        logger.info(f"[HRAIN ACTION] Получен промпт: {prompt[:50]}...")
        # Здесь можно вызвать функцию ядра, например, через HRAINAsyncDaemon
        return web.json_response({"result": True, "message": "Сигнал синтеза принят ядром."})
    except Exception as e:
        logger.error(f"Ошибка обработки action: {e}")
        return web.json_response({"result": False}, status=500)

async def handle_hrain_event(request):
    """Принимает события от core и обновляет граф."""
    try:
        event = await request.json()
        logger.info(f"[HRAIN EVENT] {event.get('type')}")

        diffs = graph_engine.update([event])
        await broadcast_update(diffs)

        # Записываем в БД (для истории)
        if event.get('type') == 'genesis_step':
            janus_db.insert_genesis_event(
                event_type="GENESIS_STEP",
                description=event.get('narrative', ''),
                metrics_snapshot=None,
                world_state=event.get('lore')
            )
        elif event.get('type') == 'cycle':
            janus_db.insert_genesis_event(
                event_type="CYCLE",
                description=f"Cycle {event.get('cycle')}, score={event.get('score'):.4f}",
                metrics_snapshot=None,
                world_state=None
            )
        elif event.get('type') == 'record':
            janus_db.insert_genesis_event(
                event_type="RECORD",
                description=f"New record at cycle {event.get('cycle')}, score={event.get('score'):.4f}",
                metrics_snapshot=None,
                world_state=None
            )
        elif event.get('type') == 'lethal_mutation':
            janus_db.insert_genesis_event(
                event_type="LETHAL_MUTATION",
                description=f"Lethal mutation at cycle {event.get('cycle')}",
                metrics_snapshot=None,
                world_state=None
            )

        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка обработки события: {e}", exc_info=True)
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_device_data(request):
    """
    Принимает данные от устройств (Android, Cardputer и т.д.) с буферизацией.
    """
    try:
        data = await request.json()
        device_id = data.get('device_id')
        if not device_id:
            return web.json_response({"status": "error", "message": "Missing device_id"}, status=400)

        record_data = data.get('data', data)
        # Нормализуем строки от m5_adv_beacon
        record_data = normalize_data(record_data, device_id)

        record = {
            'timestamp': time.time(),
            'device_id': device_id,
            'data': record_data
        }
        async with pending_lock:
            pending_data.append(record)

        logger.info(f"[DEVICE DATA] Получены данные от {device_id}")
        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка приёма данных устройства: {e}", exc_info=True)
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_device_command_get(request):
    """Возвращает команду для устройства (если есть) и удаляет её из очереди."""
    device_id = request.match_info.get('device_id')
    if not device_id:
        return web.json_response({"status": "error", "message": "Missing device_id"}, status=400)

    async with state_lock:
        if not os.path.exists(DEVICE_COMMANDS_FILE):
            return web.json_response({"command": None})

        try:
            with open(DEVICE_COMMANDS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    commands = {}
                else:
                    commands = json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Ошибка чтения команд для {device_id}: {e}")
            commands = {}

        command = commands.pop(device_id, None)
        try:
            with open(DEVICE_COMMANDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(commands, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка записи команд: {e}")

    return web.json_response({"command": command})

async def handle_device_command_post(request):
    """Устанавливает команду для устройства."""
    try:
        data = await request.json()
        device_id = data.get('device_id')
        command = data.get('command')
        if not device_id or command is None:
            return web.json_response({"status": "error", "message": "Missing device_id or command"}, status=400)

        async with state_lock:
            commands = {}
            if os.path.exists(DEVICE_COMMANDS_FILE):
                try:
                    with open(DEVICE_COMMANDS_FILE, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            commands = json.loads(content)
                except (json.JSONDecodeError, OSError) as e:
                    logger.error(f"Ошибка чтения команд: {e}")

            commands[device_id] = command
            with open(DEVICE_COMMANDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(commands, f, indent=2)

        logger.info(f"[DEVICE COMMAND] Установлена команда для {device_id}")
        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка установки команды: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def websocket_handler(request):
    """WebSocket для потоковой передачи обновлений графа."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    active_websockets.add(ws)
    logger.info("[HRAIN] Установлен нейронный линк (WebSocket).")

    # При подключении отправляем полный текущий граф
    try:
        full_state = graph_engine.get_full_state()
        nodes = []
        for nid, node in full_state['nodes'].items():
            nodes.append({
                'id': nid,
                'label': node['data'].get('label', node['type']),
                'emoji': node['data'].get('emoji', '🔮'),
                'type': node['type'],
                'x': node['data'].get('x', 0),
                'y': node['data'].get('y', 0),
                'parentId': node['data'].get('parentId'),
                'description': node['data'].get('description', ''),
                'chatHistory': node['data'].get('chatHistory', [])
            })
        links = []
        for key, edge in full_state['edges'].items():
            src, dst = key.split('->')
            links.append({'source': src, 'target': dst})
        await ws.send_str(json.dumps({"type": "FULL", "data": {'nodes': nodes, 'links': links}}))
    except Exception as e:
        logger.error(f"Ошибка отправки полного графа: {e}")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT and msg.data == 'ping':
                await ws.send_str('pong')
    finally:
        active_websockets.remove(ws)
        logger.info("[HRAIN] Нейронный линк разорван.")
    return ws

# ==============================================================================
# ЗАПУСК СЕРВЕРА
# ==============================================================================
async def run_server():
    global graph_engine
    graph_engine = HrainGraphEngine()

    await load_graph_state()

    asyncio.create_task(save_graph_state())
    asyncio.create_task(flush_pending())   # запускаем буферную задачу

    app = web.Application(client_max_size=10 * 1024 * 1024)  # 10 MB
    app.add_routes([
        web.get('/', handle_index),
        web.get('/api/hrain/state', handle_get_state),
        web.post('/api/hrain/save', handle_save_state),
        web.post('/api/janus/action', handle_janus_action),
        web.post('/api/hrain/event', handle_hrain_event),
        web.post('/api/device/data', handle_device_data),
        web.get('/api/device/command/{device_id}', handle_device_command_get),
        web.post('/api/device/command', handle_device_command_post),
        web.get('/ws', websocket_handler)
    ])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 1138)
    await site.start()

    logger.info("[HRAIN] Визуальная оболочка активна. Доступ: http://localhost:1138")
    logger.info("[HRAIN] WebSocket endpoint: ws://localhost:1138/ws")

    while True:
        await asyncio.sleep(3600)

async def main():
    await run_server()

if __name__ == "__main__":
    janus_db.init_db()
    asyncio.run(main())