#!/usr/bin/env python
import logging

# Default configuration.
# Do not edit this.  Copy config_sample.py to config.py and edit that.

# Logging
LOGGING_LEVEL_CONSOLE = logging.INFO
LOGGING_LEVEL_FILE = logging.ERROR
LOGGING_FILE = None  # or set to file path LOGGING_FILE="/var/log/paradox_mqtt.log"

# Connection Type
CONNECTION_TYPE = "Serial"  # Only serial for now

# Serial Connection Details
SERIAL_PORT = "/dev/ttyUSB0"

# Paradox
PANEL_ID = '0000'
PASSWORD = None
KEEP_ALIVE_SECONDS = 9
ZONES = 32
USERS = 32
OUTPUTS = 16
READ_LABELS_SECONDS = 15 * 60
OUTPUT_PULSE_SECONDS = 1
UPDATE_ALARM_TIME_DIFF_MINUTES = (
    2  # minimum 2. Lower values will cause constant time updates.
)

# MQTT
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_CLIENT_ID = "paradox_mqtt"
MQTT_USERNAME = None
MQTT_PASSWORD = None

# Homie Standard Items
# https://homieiot.github.io/specification/spec-core-v4_0_0/

HOMIE_BASE_TOPIC = "homie"
HOMIE_DEVICE_ID = "alarm"
HOMIE_DEVICE_NAME = "Alarm"
HOMIE_DEVICE_VERSION = "4.0.0"
HOMIE_DEVICE_EXTENSIONS = ""
HOMIE_INIT_SECONDS = 3600 * 24  # Daily
HOMIE_MQTT_QOS = 1
HOMIE_MQTT_RETAIN = True
HOMIE_PUBLISH_ALL_SECONDS = 60
HOMIE_IMPLEMENTATION = "paradox_mqtt"

# Home Assistant
HASS_BASE_TOPIC = "homeassistant"
HASS_ALARM_CODE = "0000"
HASS_ALARM_CODE_ARM_REQUIRED = False
HASS_ALARM_CODE_DISARM_REQUIRED = False
HASS_ALARM_CODE_TRIGGER_REQUIRED = False
