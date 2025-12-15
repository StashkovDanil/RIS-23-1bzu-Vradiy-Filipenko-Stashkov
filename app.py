#!/usr/bin/env python3
import json
import datetime
import threading
import time
import os
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

