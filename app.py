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

