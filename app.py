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

# Конфиги
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
LOG_FILE = os.path.join(BASE_DIR, "feed_log.json")
FOOD_FILE = os.path.join(BASE_DIR, "food_state.json")

# Эмуляция GPIO
gpiozero.Device.pin_factory = MockFactory()

motor = gpiozero.LED(17)         # Виртуальные мотор
level_sensor = gpiozero.Button(4)  # Виртуальный сенсор наличия корма

# Инициализация состояний сенсоров
try:
    # Пины имеют атрибут состояния
    if not hasattr(level_sensor.pin, "state"):
        level_sensor.pin.state = True
except Exception:
    pass

# JSON хранилище
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
    log.insert(0, entry)  # newest first
    save_json(LOG_FILE, log)

def feed_portion(amount, mode="manual"):
    """Perform feeding: run motor (emulated), decrement food, log."""
    with lock:
        print(f"[FEED] {datetime.datetime.now().isoformat()} - {amount}g ({mode})")
        motor.on()
        # simulate time needed to dispense: e.g., 0.1s per gram
        time.sleep(max(0.1, amount * 0.1))
        motor.off()

        food = load_json(FOOD_FILE, {"remaining": 0})
        food["remaining"] = max(0, food.get("remaining", 0) - amount)
        save_json(FOOD_FILE, food)

        log_feed(amount, mode)

# Расписание
scheduler = BackgroundScheduler()
scheduled_job_ids = set()

def schedule_reload():
    """Clear scheduled jobs and re-create daily jobs for each time in settings."""
    # Удаляет текущее расписание
    for job in scheduler.get_jobs():
        if job.id.startswith("feed_time_"):
            try:
                scheduler.remove_job(job.id)
            except Exception:
                pass

    settings = load_json(SETTINGS_FILE, {"portion":20, "schedule":[]})
    times = settings.get("schedule", [])
    portion = settings.get("portion", 20)
    for t in times:
        try:
            hh, mm = t.split(":")
            job_id = f"feed_time_{hh}_{mm}"
            # Каждый день в hh:mm
            scheduler.add_job(
                func=lambda amount=portion: feed_portion(amount, mode="авто"),
                trigger="cron",
                hour=int(hh),
                minute=int(mm),
                id=job_id,
                replace_existing=True
            )
        except Exception as e:
            print("Bad schedule entry:", t, e)

# Перезагрузка на старте
schedule_reload()
scheduler.start()

def check_low_food():
    food = load_json(FOOD_FILE, {"remaining":0})
    if food.get("remaining", 0) <= 50:
        # just print: notifications can be extended (telegram/email)
        print("[WARN] Low food remaining:", food.get("remaining", 0))

scheduler.add_job(check_low_food, "interval", minutes=30, id="check_low_food")

# Flask app + API
app = Flask(__name__, static_folder="static", template_folder="templates")

def compute_next_feed():
    """Return human-readable next scheduled feeding datetime and seconds until then, or None."""
    settings = load_json(SETTINGS_FILE, {"portion":20, "schedule":[]})
    times = settings.get("schedule", [])
    now = datetime.datetime.now()
    candidates = []
    for t in times:
        try:
            hh, mm = t.split(":")
            candidate = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if candidate <= now:
                candidate += datetime.timedelta(days=1)
            candidates.append(candidate)
        except Exception:
            continue
    if not candidates:
        return None
    nxt = min(candidates)
    delta = nxt - now
    # format like "in 2h 15m (2025-11-18 18:00)"
    hours, rem = divmod(int(delta.total_seconds()), 3600)
    mins = rem // 60
    human = f"Через {hours} часов {mins} минут ({nxt.strftime('%Y-%m-%d %H:%M')})"
    return {"datetime": nxt.strftime("%Y-%m-%d %H:%M:%S"), "human": human}

@app.route("/")
def index():
    settings = load_json(SETTINGS_FILE, {"portion":20, "schedule":[]})
    food = load_json(FOOD_FILE, {"remaining":0})
    log = load_json(LOG_FILE, [])
    nxt = compute_next_feed()
    return render_template("index.html",
                           portion_size=settings.get("portion",20),
                           food_left=food.get("remaining",0),
                           schedule=settings.get("schedule", []),
                           next_feed=nxt["human"] if nxt else "—",
                           log=log)

@app.route("/api/status")
def api_status():
    settings = load_json(SETTINGS_FILE, {"portion":20, "schedule":[]})
    food = load_json(FOOD_FILE, {"remaining":0})
    nxt = compute_next_feed()
    return jsonify({
        "portion_size": settings.get("portion",20),
        "food_remaining": food.get("remaining",0),
        "motor_state": bool(motor.value),
        "sensor_pressed": bool(level_sensor.is_pressed),
        "schedule": settings.get("schedule", []),
        "next_feed": nxt["human"] if nxt else None,
        "log": load_json(LOG_FILE, [])
    })

@app.route("/feed_now", methods=["POST"])
def feed_now():
    data = request.get_json(silent=True) or {}
    amount = int(data.get("amount", load_json(SETTINGS_FILE, {"portion":20}).get("portion",20)))
    threading.Thread(target=feed_portion, args=(amount, "ручной"), daemon=True).start()
    return jsonify({"status":"ok", "message": f"Выдача {amount}г корма"})

@app.route("/save_schedule", methods=["POST"])
def save_schedule():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"status":"error", "message":"Expected JSON list of times"}), 400
    # validate times (HH:MM)
    new_times = []
    for t in data:
        try:
            hh, mm = t.split(":")
            h = int(hh); m = int(mm)
            if 0 <= h <= 23 and 0 <= m <= 59:
                new_times.append(f"{h:02d}:{m:02d}")
        except Exception:
            continue
    settings = load_json(SETTINGS_FILE, {"portion":20, "schedule":[]})
    settings["schedule"] = new_times
    save_json(SETTINGS_FILE, settings)
    # reload scheduler
    schedule_reload()
    return jsonify({"status":"ok", "schedule": new_times})

@app.route("/set_portion", methods=["POST"])
def set_portion():
    data = request.get_json(silent=True) or {}
    try:
        portion = int(data.get("portion", 20))
    except Exception:
        portion = 20
    settings = load_json(SETTINGS_FILE, {"portion":20, "schedule":[]})
    settings["portion"] = portion
    save_json(SETTINGS_FILE, settings)
    # when schedule jobs were created we used previous portion; to be safe, reload
    schedule_reload()
    return jsonify({"status":"ok", "portion": portion})

@app.route("/toggle_sensor", methods=["POST"])
def toggle_sensor():
    # flip the mock pin state
    try:
        mock_pin = level_sensor.pin
        mock_pin.state = not getattr(mock_pin, "state", True)
        return jsonify({"status":"ok", "sensor_pressed": level_sensor.is_pressed})
    except Exception as e:
        return jsonify({"status":"error", "error": str(e)}), 500

# Main
if __name__ == "__main__":
    # Убедиться что файл существует
    for p, default in [(SETTINGS_FILE, {"portion":20, "schedule":["08:00","18:00"]}),
                       (LOG_FILE, []),
                       (FOOD_FILE, {"remaining":300})]:
        if not os.path.exists(p):
            save_json(p, default)
    # Запуск Flask
    app.run(host="0.0.0.0", port=8080)

