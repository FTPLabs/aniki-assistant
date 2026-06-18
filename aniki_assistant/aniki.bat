@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo  🤜 Запуск Аники...

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Запусти setup.bat
    pause
    exit /b 1
)

:: Запускаем приложение
python main.py
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Аники не запустился.
    echo Попробуй запустить setup.bat для установки зависимостей.
    pause
)
