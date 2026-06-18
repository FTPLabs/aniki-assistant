@echo off
chcp 65001 >nul
echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║        🤜 АНИКИ — Установка зависимостей          ║
echo  ║         Are you ready? Let's go!                  ║
echo  ╚═══════════════════════════════════════════════════╝
echo.

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo Скачай и установи Python 3.10+ с https://python.org
    echo ВАЖНО: Поставь галочку "Add Python to PATH"
    pause
    exit /b 1
)

echo [OK] Python найден
python --version

:: Обновляем pip
echo.
echo [1/6] Обновление pip...
python -m pip install --upgrade pip

:: Устанавливаем PyQt6
echo.
echo [2/6] Установка PyQt6 (GUI)...
pip install PyQt6

:: Устанавливаем requests
echo.
echo [3/6] Установка requests...
pip install requests

:: Устанавливаем PyTorch (CPU версия — легче и бесплатна)
echo.
echo [4/6] Установка PyTorch (это займёт несколько минут)...
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

:: Устанавливаем faster-whisper и sounddevice
echo.
echo [5/6] Установка faster-whisper и аудио библиотек...
pip install faster-whisper sounddevice numpy pyaudio

:: Устанавливаем Windows-специфичные пакеты
echo.
echo [6/6] Установка Windows-библиотек...
pip install pycaw comtypes pywin32 pyttsx3 psutil

echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║   ✅ Все зависимости установлены!                 ║
echo  ╚═══════════════════════════════════════════════════╝
echo.
echo Теперь нужно установить Ollama для работы ИИ:
echo  1. Перейди на https://ollama.com
echo  2. Скачай и установи Ollama для Windows
echo  3. Открой cmd и запусти: ollama run mistral
echo     (Первый раз скачает модель ~4GB, это нормально)
echo  4. После этого запускай aniki.bat
echo.
echo Или просто запусти aniki.bat — Аники сам объяснит что делать!
echo.
pause
