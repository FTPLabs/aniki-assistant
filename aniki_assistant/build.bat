@echo off
chcp 65001 >nul
echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║      🤜 АНИКИ — Сборка EXE-файла                  ║
echo  ║         Wrestle with the best!                    ║
echo  ╚═══════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Устанавливаем PyInstaller
echo [1/3] Установка PyInstaller...
pip install pyinstaller

:: Создаём директорию для иконки если нет
if not exist "resources" mkdir resources

:: Сборка EXE
echo.
echo [2/3] Сборка EXE (подожди, это займёт 1-3 минуты)...
echo.

pyinstaller ^
    --name "Aniki" ^
    --onedir ^
    --windowed ^
    --icon "resources\aniki.ico" ^
    --add-data "resources;resources" ^
    --add-data "data;data" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "pycaw.pycaw" ^
    --hidden-import "comtypes" ^
    --hidden-import "sounddevice" ^
    --hidden-import "faster_whisper" ^
    --hidden-import "sqlite3" ^
    --hidden-import "torch" ^
    --hidden-import "torchaudio" ^
    --collect-all "faster_whisper" ^
    --collect-all "ctranslate2" ^
    --collect-all "torch" ^
    --noconfirm ^
    main.py

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Сборка не удалась!
    echo Убедись что все зависимости установлены (setup.bat)
    pause
    exit /b 1
)

echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║   ✅ EXE собран успешно!                          ║
echo  ╚═══════════════════════════════════════════════════╝
echo.
echo Готовый файл: dist\Aniki\Aniki.exe
echo.
echo Для запуска: перейди в папку dist\Aniki\ и запусти Aniki.exe
echo Для установки на другой ПК: скопируй всю папку dist\Aniki\
echo.
pause
