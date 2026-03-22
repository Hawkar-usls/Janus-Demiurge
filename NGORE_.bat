@echo off
set PYTHONWARNINGS=ignore::FutureWarning
chcp 65001 >nul
title JANUS DEMIURGE CORE [M2R EDITION] 🔥
cd /d "%~dp0"

:: Сохраняем полный путь к текущей папке
set "PROJECT_DIR=%CD%"
echo [🔧] Рабочая папка: %PROJECT_DIR%

echo [1/6] ⚡ Валидация протоколов...
python --version >nul 2>&1
if errorlevel 1 (
    echo [❌] ОШИБКА: Python не найден! Установи Python 3.8+
    pause
    exit /b
)

echo [2/6] 📦 Проверка и установка зависимостей...
pip install --quiet --upgrade pip

:: Основные
pip install --quiet torch torchvision torchaudio --index-url https://download.pytorch.org
pip install --quiet numpy aiohttp psutil requests

:: Сенсорный комплект
pip install --quiet pyserial
pip install --quiet nvidia-ml-py
pip install --quiet pyaudio
pip install --quiet pycaw comtypes
pip install --quiet pynput
pip install --quiet dxcam
pip install --quiet opencv-python
pip install --quiet mss

:: Для гетерогенного мониторинга
pip install --quiet wmi
pip install --quiet pywin32

:: Для диффузионных моделей
pip install --quiet diffusers transformers accelerate safetensors scikit-image

echo [✅] Зависимости установлены/проверены.

:: ========== ЗАПУСК КОМПОНЕНТОВ В ОДНОМ ОКНЕ ==========
echo [3/5] 💻 Поднятие Систем Титана...
:: Создаём окно Windows Terminal с первой вкладкой (HRAIN)
start "JANUS TERMINAL" wt -w 0 nt --title "HRAIN UI [PORT 1138]" -d "%PROJECT_DIR%" cmd /k "color 0D && python \"%PROJECT_DIR%\server.py\""

:: Даём полсекунды, чтобы окно создалось
timeout /t 1 /nobreak >nul

echo [4/5] 🔥 Запуск Эволюционного Ядра (Демиург)...
:: Добавляем вторую вкладку (CORE)
wt -w 0 new-tab --title "JANUS CORE" -d "%PROJECT_DIR%" cmd /k "color 0B && python \"%PROJECT_DIR%\core.py\""

echo.
echo [5/5] 👋 Все компоненты запущены в одном окне Windows Terminal (две вкладки). Этот батник можно закрыть.
pause