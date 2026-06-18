"""
Помощник для настройки Ollama.
Проверяет установку, загружает модель.
"""

import subprocess
import sys
import os
import requests
import time

OLLAMA_BASE_URL = "http://localhost:11434"
RECOMMENDED_MODEL = "mistral"
LIGHTWEIGHT_MODEL = "llama3.2:3b"


def check_ollama_installed() -> bool:
    """Проверить установлен ли Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_ollama_running() -> bool:
    """Проверить запущен ли Ollama."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


def start_ollama():
    """Запустить Ollama в фоне."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        print("Запускаю Ollama сервер...")
        for i in range(15):
            time.sleep(1)
            if check_ollama_running():
                print("Ollama запущен!")
                return True
        return False
    except Exception as e:
        print(f"Не удалось запустить Ollama: {e}")
        return False


def get_available_models() -> list:
    """Получить список загруженных моделей."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


def pull_model(model_name: str, progress_callback=None) -> bool:
    """Загрузить модель."""
    try:
        import json
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=600
        )

        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    status = data.get("status", "")

                    if progress_callback:
                        total = data.get("total", 0)
                        completed = data.get("completed", 0)
                        if total > 0:
                            percent = int(completed / total * 100)
                            progress_callback(status, percent)
                        else:
                            progress_callback(status, 0)

                    if status == "success":
                        return True
                except json.JSONDecodeError:
                    continue

        return True
    except Exception as e:
        print(f"Ошибка загрузки модели: {e}")
        return False


def ensure_model_available(model_name: str = RECOMMENDED_MODEL) -> bool:
    """Убедиться что модель доступна, загрузить если нет."""
    available = get_available_models()

    for m in available:
        if model_name.split(":")[0] in m.lower():
            print(f"Модель '{m}' уже загружена")
            return True

    print(f"Загружаю модель '{model_name}'...")
    print("Это может занять несколько минут при первом запуске...")

    def progress(status, percent):
        if percent > 0:
            print(f"  {status}: {percent}%")
        else:
            print(f"  {status}...")

    return pull_model(model_name, progress)


def full_setup():
    """Полная автоматическая настройка."""
    print("\n" + "="*50)
    print("🤜 АНИКИ — Настройка Ollama ИИ")
    print("="*50 + "\n")

    print("Проверяю Ollama...")
    if not check_ollama_installed():
        print("❌ Ollama не установлен!")
        print("\nДля установки:")
        print("  1. Перейди на https://ollama.com")
        print("  2. Нажми Download for Windows")
        print("  3. Установи и перезапусти этот скрипт")
        return False

    print("✅ Ollama установлен")

    if not check_ollama_running():
        print("Ollama не запущен. Пробую запустить...")
        if not start_ollama():
            print("❌ Не удалось запустить Ollama")
            print("Запусти вручную: ollama serve")
            return False

    print("✅ Ollama сервер работает")

    models = get_available_models()
    if models:
        print(f"✅ Загруженные модели: {', '.join(models)}")

        has_good_model = any(
            any(name in m.lower() for name in ["mistral", "llama", "gemma", "phi"])
            for m in models
        )
        if has_good_model:
            print("✅ Модель готова к работе!")
            return True

    print(f"\nЗагружаю рекомендуемую модель: {RECOMMENDED_MODEL}")
    print("(~4GB, загружается один раз)\n")

    if ensure_model_available(RECOMMENDED_MODEL):
        print(f"\n✅ Модель '{RECOMMENDED_MODEL}' загружена!")
        print("\nВсё готово! Запускай Аники через aniki.bat")
        return True
    else:
        print(f"\nПробую лёгкую модель: {LIGHTWEIGHT_MODEL}")
        if ensure_model_available(LIGHTWEIGHT_MODEL):
            print(f"\n✅ Модель '{LIGHTWEIGHT_MODEL}' загружена!")
            return True

    print("❌ Не удалось загрузить модель")
    return False


if __name__ == "__main__":
    success = full_setup()
    if success:
        print("\n🤜 Аники готов к работе! Are you ready?")
    else:
        print("\n❌ Настройка не завершена. Следуй инструкциям выше.")
    input("\nНажми Enter для выхода...")
