@echo off
chcp 65001 >nul
echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║    🤜 АНИКИ — Быстрый старт                       ║
echo  ║       Are you ready? Let's go!                    ║
echo  ╚═══════════════════════════════════════════════════╝
echo.
cd /d "%~dp0"

echo Проверяю Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python не найден!
    echo.
    echo Установи Python 3.11+ с https://python.org
    echo ВАЖНО: поставь галочку "Add Python to PATH"
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python найден

echo Проверяю зависимости...
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo [!] Зависимости не установлены. Устанавливаю...
    call setup.bat
)

echo Настраиваю Ollama ИИ...
python ollama_setup.py

echo.
echo Запускаю Аники!
echo.
python main.py
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Что-то пошло не так.
    echo Смотри лог: data\aniki.log
    pause
)
