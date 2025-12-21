#!/usr/bin/env python3
import json
import datetime
import threading
import time
import os
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import gpiozero
from gpiozero.pins.mock import MockFactory

# Файлы конфигов, настроек, логов и расписаний
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
LOG_FILE = os.path.join(BASE_DIR, "feed_log.json")
FOOD_FILE = os.path.join(BASE_DIR, "food_state.json")
# Эмуляция gpio
gpiozero.Device.pin_factory = MockFactory()

motor = gpiozero.LED(17)         # virtual motor
level_sensor = gpiozero.Button(4)  # virtual food-level sensor (pressed => has food)

try:
    if not hasattr(level_sensor.pin, "state"):
        level_sensor.pin.state = True
except Exception:
    pass

# Вспомогательные функции для работы с JSON
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
# Логика выдачи корма
lock = threading.Lock()

def log_feed(amount, mode):
    entry = {
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "amount": amount,
        "mode": mode
    }
    log = load_json(LOG_FILE, [])
    log.insert(0, entry)  # Сначало новые
    save_json(LOG_FILE, log)

def feed_portion(amount, mode="manual"):
    """Perform feeding: run motor (emulated), decrement food, log."""
    with lock:
        print(f"[FEED] {datetime.datetime.now().isoformat()} - {amount}g ({mode})")
        motor.on()
        # Симуляция времени работы механизма выдачи корма
        time.sleep(max(0.1, amount * 0.1))
        motor.off()

        food = load_json(FOOD_FILE, {"remaining": 0})
        food["remaining"] = max(0, food.get("remaining", 0) - amount)
        save_json(FOOD_FILE, food)

        log_feed(amount, mode)

