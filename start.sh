#!/bin/bash
source /root/petfeeder/.venv/bin/activate
/root/petfeeder/.venv/bin/pip3 install -r /root/petfeeder/requiriment.txt
/root/petfeeder/.venv/bin/python3 /root/petfeeder/app.py
