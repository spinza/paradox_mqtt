#!/usr/bin/env python
import logging

# Default configuration.
# Do not edit this.  Copy config_sample.py to config.py and edit that.

# Logging
# LOGGING_LEVEL_CONSOLE = logging.INFO
# LOGGING_LEVEL_FILE = logging.ERROR
# LOGGING_FILE=None #or set to file path LOGGING_FILE="/var/log/paradox_mqtt.log"

# Connection Type
# CONNECTION_TYPE = "Serial"  #Only serial for now

# Serial Connection Details
# SERIAL_PORT = "/dev/ttyUSB0"

# Paradox
# KEEP_ALIVE_SECONDS = 9
# ZONES = 32
# USERS = 32
# OUTPUTS = 16
# READ_LABELS_SECONDS = 15 * 60
# OUTPUT_PULSE_SECONDS = 1
# UPDATE_ALARM_TIME_DIFF_MINUTES = 2 #minimum 2. Lower values will cause constant time updates.

# MQTT
# MQTT_HOST='localhost'
# MQTT_PORT=1883
# MQTT_KEEPALIVE=60
# MQTT_BIND_ADDRESS=""

# MQTT Topics
# MQTT_PUBLISH_ALL_SECONDS = 60
# MQTT_BASE_TOPIC='paradox_mqtt'
# MQTT_ZONE_TOPIC='zones'
# MQTT_PARTITION_TOPIC='partitions'
# MQTT_EVENTS_TOPIC='events'
# MQTT_CONTROL_TOPIC='control'
# MQTT_OUTPUT_TOPIC='outputs'
# MQTT_STATES_TOPIC='states'
# MQTT_RAW_TOPIC='raw'
