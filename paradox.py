#!/usr/bin/env python
import logging

logger = logging.getLogger("paradox_mqtt").getChild(__name__)
from time import sleep, time
from datetime import datetime, timedelta
from bits import test_bit, split_high_low_nibble
from math import floor
import paho.mqtt.client as mqtt
import json

from config_defaults import *
from config import *


class Paradox:
    def __init__(
        self,
        connection,
        encrypted=0,
        alarmeventmap="ParadoxMG5050",
        alarmregmap="ParadoxMG5050",
    ):
        """Intialise Paradox"""
        logger.debug("Initialising Paradox class...")
        # mqtt client
        self.mqtt = mqtt.Client(client_id=MQTT_CLIENT_ID)
        self.mqtt.on_connect = self.on_mqtt_connect
        self.mqtt.on_disconnect = self.on_mqtt_disconnect
        self.mqtt.on_message = self.homie_message

        # MQTT Will
        topic = "{}/{}/{}".format(HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "$state")
        self.mqtt.will_set(
            topic, payload="lost", qos=HOMIE_MQTT_QOS, retain=HOMIE_MQTT_RETAIN
        )

        # Connection
        self.connection = connection

        # My event map and reg maps
        self.alarmeventmap = alarmeventmap
        self.alarmregmap = alarmregmap

        # PanelInfo
        self.panelid = None
        self.panelname = None
        self.firmwareversion = None
        self.firmwarerevision = None
        self.firmwarebuild = None
        self.programmedpanelida = None
        self.programmedpanelidb = None
        self.programmedpanelid1 = None
        self.programmedpanelid2 = None
        self.programmedpanelid3 = None
        self.programmedpanelid4 = None
        self.source_id = 1
        self.paneltime = None
        self.messagetime = None

        # Trouble indicators - not implemented yet
        # Order below is important
        self.trouble_indicators = {
            0: {"machine_label": "natrouble", "name": "N/A Trouble", "status": False},
            1: {
                "machine_label": "powerfailure",
                "name": "Power Failure",
                "status": False,
            },
            2: {
                "machine_label": "batteryfailure",
                "name": "Battery Failure",
                "status": False,
            },
            3: {
                "machine_label": "auxcurrentoverload",
                "name": "Aux Current Overload",
                "status": False,
            },
            4: {
                "machine_label": "bellcurrentoverload",
                "name": "Bell Current Overload",
                "status": False,
            },
            5: {
                "machine_label": "belldisconnected",
                "name": "Bell Disconnected",
                "status": False,
            },
            6: {"machine_label": "clockloss", "name": "Clock Loss", "status": False},
            7: {
                "machine_label": "firelooptrouble",
                "name": "Fire Loop Trouble",
                "status": False,
            },
            8: {
                "machine_label": "failuretocommunicatetelephone1",
                "name": "Failure to Communicate Telephone #1",
                "status": False,
            },
            9: {
                "machine_label": "failuretocommunicatetelephone2",
                "name": "Failure to Communicate Telephone #2",
                "status": False,
            },
            11: {
                "machine_label": "failuretocommunicatevoice",
                "name": "Failure to Communcate Voice Report",
                "status": False,
            },
            12: {"machine_label": "rfjamming", "name": "RF Jamming", "status": False},
            13: {
                "machine_label": "gsmrfjamming",
                "name": "GSM RF Jamming",
                "status": False,
            },
            14: {
                "machine_label": "gsmnoservice",
                "name": "GSM No Service",
                "status": False,
            },
            15: {
                "machine_label": "gsmsupervisionlost",
                "name": "GSM Supervision Lost",
                "status": False,
            },
            16: {
                "machine_label": "failuretocommunicateipreceiver1gprs",
                "name": "Failure to Communicate IP preceiver #1 (GPRS)",
                "status": False,
            },
            17: {
                "machine_label": "failuretocommunicateipreceiver2gprs",
                "name": "Failure to Communicate IP preceiver #2 (GPRS)",
                "status": False,
            },
            18: {
                "machine_label": "ipmodulenoservice",
                "name": "IP Module No Service",
                "status": False,
            },
            19: {
                "machine_label": "ipmodulesupervisionlost",
                "name": "IP Module Supervision Lost",
                "status": False,
            },
            20: {
                "machine_label": "failuretocommunicateipreceiver1ip",
                "name": "Failure to Communicate IP preceiver #1 (IP)",
                "status": False,
            },
            21: {
                "machine_label": "failuretocommunicateipreceiver2ip",
                "name": "Failure to Communicate IP preceiver #2 (IP)",
                "status": False,
            },
            99: {
                "machine_label": "anynewtroubleevent",
                "name": "Any New Trouble",
                "status": False,
            },
        }

        # Module Trouble Indicators
        self.module_trouble_indicators = {
            0: {
                "machine_label": "modulecommunicationfault",
                "name": "Bus / EBus / Wireless module communication fault",
                "status": False,
            },
            1: {
                "machine_label": "tampertrouble",
                "name": "Tamper Trouble",
                "status": False,
            },
            2: {
                "machine_label": "powerfailure",
                "name": "Power Failure",
                "status": False,
            },
            3: {
                "machine_label": "batteryfailure",
                "name": "Battery Failure",
                "status": False,
            },
            99: {"machine_label": "anytrouble", "name": "Any Trouble", "status": False},
        }

        # Low Nibble Data
        self.softwaredirectconnected = False
        self.softwareconnected = False
        self.alarm = False
        self.eventreporting = False

        # Votage Info
        self.input_dc_voltage = None
        self.power_supply_dc_voltage = None
        self.battery_dc_voltage = None

        # Bell on?
        self.bell = False

        # Partitions
        self.partition_data = []
        for i in range(0, 2 + 1):  # dummy partition 0
            partition = {}
            partition["number"] = i
            partition["label"] = "Partition {:d}".format(i)
            partition["machine_label"] = partition["label"].lower().replace(" ", "")
            partition["alarm"] = False
            partition["armed"] = None
            partition["armstate"] = None
            partition["armstatetext"] = None
            partition["armstatehass"] = None
            self.partition_data.append(partition)

        # Bell on?
        self.bell = False

        # Zones & Zone Data
        self.zones = ZONES

        self.zone_data = []
        for i in range(0, self.zones + 1):  # implies a dummy zone 0
            zone = {}
            zone["number"] = i
            zone["label"] = "Zone {:d}".format(i)
            zone["machine_label"] = zone["label"].lower().replace(" ", "")
            zone["open"] = None
            zone["bypass"] = False
            zone["alarm"] = False
            zone["firealarm"] = False
            zone["shutdown"] = False
            zone["tamper"] = False
            zone["lowbattery"] = False
            zone["supervisiontrouble"] = False
            self.zone_data.append(zone)

        # Users
        self.users = USERS
        self.user_data = []
        for i in range(0, self.users + 1):  # implies dummy user 0
            user = {}
            user["number"] = i
            user["label"] = "User {:d}".format(i + 1)
            user["machine_label"] = user["label"].lower().replace(" ", "")
            self.user_data.append(user)

        # Outputs
        self.outputs = OUTPUTS
        self.output_data = []
        for i in range(0, self.outputs + 1):  # implies dummy output 0
            output = {}
            output["number"] = i
            output["label"] = "Output {:d}".format(i + 1)
            output["machine_label"] = output["label"].lower().replace(" ", "")
            output["on"] = False
            output["pulse"] = False
            output["supervisiontrouble"] = False
            output["tamper"] = False
            self.output_data.append(output)

        # event map
        mod = __import__("paradox_map", fromlist=[self.alarmeventmap + "EventMap"])
        self.eventmap = getattr(mod, self.alarmeventmap + "EventMap")

        # registers
        mod = __import__("paradox_map", fromlist=[self.alarmregmap + "Registers"])
        self.registermap = getattr(mod, self.alarmregmap + "Registers")

        # connect to MQTT
        self.mqtt_connect(
            host=MQTT_HOST,
            port=MQTT_PORT,
            username=MQTT_USERNAME,
            password=MQTT_PASSWORD,
        )

        # flag Homie init
        self.do_homie_init = True

        logger.debug("Initialised Paradox class.")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT...")
            self.mqtt.subscribe(
                "{}/{}/{}/{}/{}/{}".format(
                    HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "+", "+", "set", "#"
                )
            )
            self.do_homie_init = True
        else:
            logger.info("Connectetion to MQTT failed return code of {}.".format(rc))

    def on_mqtt_disconnect(self, client, userdata, rc):
        logger.info("MQTT was disconnected with return code of {}".format(rc))

    def mqtt_connect(
        self,
        host="localhost",
        port=1883,
        username=None,
        password=None,
        keepalive=60,
        bind_address="",
    ):
        logger.info("Connecting to mqtt.")
        if username != None and password != None:
            self.mqtt.username_pw_set(username=username, password=password)

        error = True
        while error:
            try:
                self.mqtt.connect(host, port, keepalive, bind_address)
                error = False
            except Exception as e:
                logger.error("{} for MQTT.  Retrying...".format(e))
                error = True
                sleep(5)
        self.mqtt.loop_start()

    def homie_publish(self, topic, message):
        self.mqtt.publish(
            topic=topic, payload=message, qos=HOMIE_MQTT_QOS, retain=HOMIE_MQTT_RETAIN
        )

    def homie_message_ON_OFF(self, message):
        if message in ["ON", "OFF"]:
            return message == "ON"
        else:
            return None

    def homie_message_true_false(self, message):
        if message in ["true", "false"]:
            return message == "true"
        else:
            return None

    def homie_message_integer(self, message):
        if message.isdigit():
            return int(message)
        else:
            return None

    def homie_partition_property_set(self, partition_number, property, message):
        if property in ["armstate"]:
            value = self.homie_message_integer(str(message.payload.decode("utf-8")))
            if value == None:
                logger.error(
                    "Invalid message body. Should be integer. {}".format(
                        str(message.payload.decode("utf-8"))
                    )
                )
            else:
                if value == 3:
                    self.control_alarm(partition_number=partition_number, state="ARM")
                elif value == 1:
                    self.control_alarm(partition_number=partition_number, state="STAY")
                elif value == 2:
                    self.control_alarm(partition_number=partition_number, state="SLEEP")
                elif value == 0:
                    self.control_alarm(
                        partition_number=partition_number, state="DISARM"
                    )
                else:
                    logger.error("amrstate value {} is invalid.".format(value))
        elif property in ["armstatetext"]:
            value = str(message.payload.decode("utf-8"))
            if value == None:
                logger.error(
                    "Invalid message body. Should be ARM/STAY/SLEEP/DISARM. {}".format(
                        str(message.payload.decode("utf-8"))
                    )
                )
            else:
                if value in ["ARM", "STAY", "SLEEP", "DISARM"]:
                    self.control_alarm(partition_number=partition_number, state=value)
                else:
                    logger.error(
                        "amrstate value {} is invalid. Should be ARM/STAY/SLEEP.".format(
                            value
                        )
                    )
        elif property in ["armstatehass"]:
            value = str(message.payload.decode("utf-8"))
            if value == None:
                logger.error(
                    "Invalid message body. Should be disarmed/armed_home/armed_night/armed_away. {}".format(
                        str(message.payload.decode("utf-8"))
                    )
                )
            else:
                if value == "armed_away":
                    self.control_alarm(partition_number=partition_number, state="ARM")
                elif value == "armed_home":
                    self.control_alarm(partition_number=partition_number, state="STAY")
                elif value == "armed_night":
                    self.control_alarm(partition_number=partition_number, state="SLEEP")
                elif value == "disarmed":
                    self.control_alarm(
                        partition_number=partition_number, state="DISARM"
                    )
                else:
                    logger.error(
                        "amrstatehass value {} is invalid. Should be disarmed/armed_home/armed_night/armed_away.".format(
                            value
                        )
                    )
        elif property in ["armed"]:
            value = self.homie_message_true_false(str(message.payload.decode("utf-8")))
            if value == None:
                logger.error(
                    "Invalid message body. Should be true/false. {}".format(
                        str(message.payload.decode("utf-8"))
                    )
                )
            elif value == True:
                self.control_alarm(partition_number=partition_number, state="ARM")
            else:
                self.control_alarm(partition_number=partition_number, state="DISARM")

        else:
            logger.error("Partition property {} not settable.".format(property))

    def homie_output_property_set(self, output_number, property, message):
        flag = self.homie_message_true_false(str(message.payload.decode("utf-8")))
        if flag == None:
            logger.error(
                "Invalid message body. Should be true/false. {}".format(
                    str(message.payload.decode("utf-8"))
                )
            )
        else:
            if property in ["on", "pulse"]:
                if property == "on":
                    self.set_output(output_number=output_number, on=flag)
                elif property == "pulse":
                    self.set_output_pulse(output_number=output_number, pulse=flag)
            else:
                logger.error("Output property {} not settable.".format(property))

    def homie_zone_property_set(self, zone_number, property, message):
        flag = self.homie_message_true_false(str(message.payload.decode("utf-8")))
        if flag == None:
            logger.error(
                "Invalid message body. Should be true/false. {}".format(
                    str(message.payload.decode("utf-8"))
                )
            )
        else:
            if property in ["bypass"]:
                self.bypass_zone(zone_number)
            else:
                logger.error("Zone property {} not settable.".format(property))

    def homie_message(self, client, userdata, message):
        logger.info(
            "message topic={}, message={}".format(
                message.topic, str(message.payload.decode("utf-8"))
            )
        )
        node_found = False
        topics = message.topic.split("/")
        node_id = topics[2]
        property = topics[3]
        for i in range(1, 2 + 1):
            if node_id == self.partition_data[i]["machine_label"]:
                self.homie_partition_property_set(
                    partition_number=i, property=property, message=message
                )
                node_found = True
        if not node_found:
            for i in range(1, self.outputs + 1):
                if node_id == self.output_data[i]["machine_label"]:
                    self.homie_output_property_set(
                        output_number=i, property=property, message=message
                    )
                    node_found = True
        if not node_found:
            for i in range(1, self.zones + 1):
                if node_id == self.zone_data[i]["machine_label"]:
                    self.homie_zone_property_set(
                        zone_number=i, property=property, message=message
                    )
                    node_found = True

    def main_loop(self):
        """Wait for and then process messages."""
        keep_alive_time = datetime(1900, 1, 1)
        label_time = datetime(1900, 1, 1)
        homie_init_time = datetime(1900, 1, 1)
        homie_publish_all_time = datetime(1900, 1, 1)
        output_pulse_time = datetime(1900, 1, 1)
        while True:
            if self.connection.in_waiting() >= 37:
                message = self.connection.read()
                logger.debug("Received message: {} ".format(message))
                self.process_message(message)
            sleep(0.1)
            if not self.softwareconnected:
                self.connect_software()
            if datetime.now() > label_time + timedelta(seconds=READ_LABELS_SECONDS):
                self.read_labels()
                label_time = datetime.now()
            if datetime.now() > keep_alive_time + timedelta(seconds=KEEP_ALIVE_SECONDS):
                self.keep_alive()
                keep_alive_time = datetime.now()
            if self.do_homie_init or datetime.now() > homie_init_time + timedelta(
                seconds=HOMIE_INIT_SECONDS
            ):
                self.homie_init()
                homie_init_time = datetime.now()
            if datetime.now() > homie_publish_all_time + timedelta(
                seconds=HOMIE_PUBLISH_ALL_SECONDS
            ):
                self.homie_publish_all()
                homie_publish_all_time = datetime.now()
            if datetime.now() > output_pulse_time + timedelta(
                seconds=OUTPUT_PULSE_SECONDS
            ):
                self.pulse_outputs()
                output_pulse_time = datetime.now()

    def wait_for_message(self, timeout=1, process_message=False):
        """Wait (up to timeout) untill buffer is filled with 37 bytes and then return message."""
        tstart = time()
        while time() < tstart + timeout:
            if self.connection.in_waiting() >= 37:
                message = self.connection.read()
                logger.debug("Received message: {} ".format(message))
                if process_message:
                    self.process_message(message)
                return message
            sleep(0.1)
        return None

    def timestamp_str(self, date=datetime.now()):
        return "{}".format(datetime.now().isoformat())

    def homie_publish_device_state(self, state):
        topic = "{}/{}/{}".format(HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "$state")
        self.homie_publish(topic, state)

    def homie_init(self):
        # device to init
        self.homie_init_device()
        self.homie_init_panel()
        self.homie_init_trouble_indicators()
        self.homie_init_module_trouble_indicators()
        self.homie_init_partitions()
        self.homie_init_outputs()
        self.homie_init_zones()
        self.homie_init_last_zone_event()

        # device ready
        self.homie_publish_device_state("ready")
        self.do_homie_init = False

    def homie_init_device(self):
        topic = "{}/{}/{}".format(HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "$homie")
        self.homie_publish(topic, HOMIE_DEVICE_VERSION)
        topic = "{}/{}/{}".format(HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "$name")
        self.homie_publish(topic, HOMIE_DEVICE_NAME)
        self.homie_publish_device_state("init")
        topic = "{}/{}/{}".format(HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "$nodes")
        nodes = "panel,troubleindicators,moduletroubleindicators"
        for i in range(1, 2 + 1):
            nodes = nodes + "," + self.partition_data[i]["machine_label"]
        for i in range(1, self.outputs + 1):
            nodes = nodes + "," + self.output_data[i]["machine_label"]
        for i in range(1, self.zones + 1):
            nodes = nodes + "," + self.zone_data[i]["machine_label"]
        nodes = nodes + ",lastzoneevent"
        self.homie_publish(topic, nodes)
        topic = "{}/{}/{}".format(HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "$extensions")
        self.homie_publish(topic, "")
        topic = "{}/{}/{}".format(HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "$implementation")
        self.homie_publish(topic, HOMIE_IMPLEMENTATION)
        # self.homie_publish(topic, 'satus, voltages, partition[], output[], zone[]')

    def homie_publish_all(self, init=False):
        self.homie_publish_panel()
        self.homie_publish_trouble_indicators()
        self.homie_publish_module_trouble_indicators()
        self.homie_publish_partitions()
        self.homie_publish_outputs()
        self.homie_publish_zones()

    def homie_init_node(self, node_id, name, type=None, properties=None):
        topic = "{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, "$name"
        )
        self.homie_publish(topic, name)
        if type != None:
            topic = "{}/{}/{}/{}".format(
                HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, "$type"
            )
            self.homie_publish(topic, type)
        if properties != None:
            topic = "{}/{}/{}/{}".format(
                HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, "$properties"
            )
            self.homie_publish(topic, properties)

    def homie_message_boolean(self, value):
        if value:
            return "true"
        else:
            return "false"

    def homie_publish_boolean(self, topic, value):
        message = self.homie_message_boolean(value)
        self.homie_publish(topic, message)

    def homie_publish_property(self, node_id, property_id, datatype, value=None):
        if value != None:
            topic = "{}/{}/{}/{}".format(
                HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, property_id
            )
            if datatype == "boolean":
                message = self.homie_message_boolean(value)
            else:
                message = value
            self.homie_publish(topic, message)

    def get_hass_config_template(self):
        topic = "{}/{}/{}".format(HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, "$state")
        config_template = {
            "availability": {
                "topic": topic,
                "payload_available": "ready",
                "payload_not_available": "lost",
            },
            "code_arm_required": HASS_ALARM_CODE_ARM_REQUIRED,
            "code_disarm_required": HASS_ALARM_CODE_DISARM_REQUIRED,
            "code_trigger_required": HASS_ALARM_CODE_TRIGGER_REQUIRED,
            "availability_mode": "latest",
            "device": {
                "identifiers": HASS_DEVICE_ID,
                "model": "Paradox MG5050",
                "name": "Paradox MG5050",
                "sw_version": self.firmwareversion,
            },
        }
        if HASS_ALARM_CODE != None:
            config_template = config_template | {"code": HASS_ALARM_CODE}

        return config_template

    def hass_init_config(
        self,
        node_id,
        property_id,
        name,
        datatype,
        format=None,
        settable=False,
        retained=True,
        unit=None,
    ):
        config = self.get_hass_config_template()

        component = "Unknown"
        unique_id = HOMIE_DEVICE_ID + "_" + node_id + "_" + property_id
        config["name"] = name
        config["object_id"] = unique_id
        config["state_topic"] = "{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC,
            HOMIE_DEVICE_ID,
            node_id,
            property_id,
        )
        command_topic = "{}/{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC,
            HOMIE_DEVICE_ID,
            node_id,
            property_id,
            "set",
        )
        config["unique_id"] = unique_id
        if datatype == "boolean":
            config["payload_off"] = "false"
            config["payload_on"] = "true"
            if settable:
                component = "switch"
                config["optimistic"] = False
                config["command_topic"] = command_topic
            else:
                component = "binary_sensor"
        elif datatype in ("float", "integer"):
            if unit != None:
                config["unit_of_measurement"] = unit
            if settable:
                component = "number"
                config["optimistic"] = False
                config["command_topic"] = command_topic
                if format != None:
                    config["min"], config["max"] = format.split(":")
            else:
                component = "sensor"
        elif datatype == "string":
            if settable:
                component = "text"
                config["optimistic"] = False
                config["command_topic"] = command_topic
            else:
                component = "sensor"
        elif datatype == "enum":
            options = format.split(",")
            if len(options) == 2 and "On" in options and "Off" in options:
                config["payload_off"] = "Off"
                config["payload_on"] = "On"
                if settable:
                    component = "switch"
                    config["optimistic"] = False
                    config["command_topic"] = command_topic
                else:
                    component = "binary_sensor"
            else:
                if settable:
                    component = "select"
                    config["optimistic"] = False
                    config["command_topic"] = command_topic
                    config["options"] = format.split(",")
                else:
                    component = "sensor"
        else:
            logger.error(
                "Could not represent property {} of node {} for {}.".format(
                    property_id, node_id, self.label
                )
            )

        topic = "{}/{}/{}/{}".format(
            HASS_BASE_TOPIC,
            component,
            unique_id,
            "config",
        )
        config_serialised = json.dumps(config)
        if component != "Unknown":
            self.homie_publish(topic, config_serialised)
        else:
            logger.error("Unknown component")

    def hass_init_alarmcontrolpanel_config(self, partition=1):
        config = self.get_hass_config_template()
        config["state_topic"] = "{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC,
            HOMIE_DEVICE_ID,
            "partition" + str(partition),
            "armstatehass",
        )
        config["command_topic"] = "{}/{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC,
            HOMIE_DEVICE_ID,
            "partition" + str(partition),
            "armstatehass",
            "set",
        )
        config["name"] = "Alarm Partition " + str(partition)
        config["object_id"] = "alarm_partition" + str(partition)
        config["payload_arm_away"] = "armed_away"
        config["payload_arm_night"] = "armed_night"
        config["payload_arm_home"] = "armed_home"
        config["payload_disarm"] = "disarmed"
        config["unique_id"] = "alarmpartition" + str(partition)
        topic = "{}/{}/{}/{}".format(
            HASS_BASE_TOPIC,
            "alarm_control_panel",
            config["unique_id"],
            "config",
        )
        config_serialised = json.dumps(config)
        self.homie_publish(topic, config_serialised)

    def homie_init_property(
        self,
        node_id,
        property_id,
        name,
        datatype,
        format=None,
        settable=False,
        retained=True,
        unit=None,
    ):
        topic = "{}/{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, property_id, "$name"
        )
        self.homie_publish(topic, name)
        topic = "{}/{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, property_id, "$datatype"
        )
        self.homie_publish(topic, datatype)
        if format != None:
            topic = "{}/{}/{}/{}/{}".format(
                HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, property_id, "$format"
            )
            self.homie_publish(topic, format)
        topic = "{}/{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, property_id, "$settable"
        )
        self.homie_publish_boolean(topic, settable)
        topic = "{}/{}/{}/{}/{}".format(
            HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, property_id, "$retained"
        )
        self.homie_publish_boolean(topic, retained)
        if unit != None:
            topic = "{}/{}/{}/{}/{}".format(
                HOMIE_BASE_TOPIC, HOMIE_DEVICE_ID, node_id, property_id, "$unit"
            )
            self.homie_publish(topic, unit)

        self.hass_init_config(
            node_id, property_id, name, datatype, format, settable, retained, unit
        )

    def homie_init_panel(self):
        self.homie_init_node(
            node_id="panel",
            name="Panel",
            properties="panelid,panelname,firmwareversion,firmwarerevision,firmwarebuild,programmedpanelida,programmedpanelidb,programmedpanelid1,programmedpanelid2,programmedpanelid3,programmedpanelid4,paneltime,messagetime,softwaredirectconnected,softwareconnected,alarm,eventreporting,bell,inputdcvoltage,powersupplydcvoltage,batterydcvoltage",
        )
        self.homie_init_property(
            node_id="panel", property_id="panelid", name="Panel ID", datatype="integer"
        )
        self.homie_init_property(
            node_id="panel",
            property_id="panelname",
            name="Panel Name",
            datatype="string",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="firmwareversion",
            name="Firmware Version",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="firmwarerevision",
            name="Firmware Revision",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="firmwarebuild",
            name="Firmware Build",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="programmedpanelida",
            name="Programmed Panel ID A",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="programmedpanelidb",
            name="Programmed Panel ID B",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="programmedpanelid1",
            name="Programmed Panel ID 1",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="programmedpanelid2",
            name="Programmed Panel ID 2",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="programmedpanelid3",
            name="Programmed Panel ID 3",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="programmedpanelid4",
            name="Programmed Panel ID 4",
            datatype="integer",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="paneltime",
            name="Panel Time",
            datatype="string",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="messagetime",
            name="Message Time",
            datatype="string",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="softwaredirectconnected",
            name="Software Direct Connected",
            datatype="boolean",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="softwareconnected",
            name="Software Connected",
            datatype="boolean",
        )
        self.homie_init_property(
            node_id="panel", property_id="alarm", name="Alarm", datatype="boolean"
        )
        self.homie_init_property(
            node_id="panel",
            property_id="eventreporting",
            name="Event Reporting",
            datatype="boolean",
        )
        self.homie_init_property(
            node_id="panel", property_id="bell", name="Bell", datatype="boolean"
        )
        self.homie_init_property(
            node_id="panel",
            property_id="inputdcvoltage",
            name="Input DC Voltage",
            datatype="float",
            unit="v",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="powersupplydcvoltage",
            name="Power Supply DC Voltage",
            datatype="float",
            unit="v",
        )
        self.homie_init_property(
            node_id="panel",
            property_id="batterydcvoltage",
            name="Battery DC Voltage",
            datatype="float",
            unit="v",
        )

    def homie_init_trouble_indicators(self):
        trouble_properties = ",".join(
            self.trouble_indicators[t]["machine_label"] for t in self.trouble_indicators
        )
        self.homie_init_node(
            node_id="troubleindicators",
            name="Trouble Indicators",
            properties=trouble_properties,
        )
        for t in self.trouble_indicators:
            self.homie_init_property(
                node_id="troubleindicators",
                property_id=self.trouble_indicators[t]["machine_label"],
                name=self.trouble_indicators[t]["name"],
                datatype="boolean",
            )

    def homie_init_module_trouble_indicators(self):
        trouble_properties = ",".join(
            self.module_trouble_indicators[t]["machine_label"]
            for t in self.module_trouble_indicators
        )
        self.homie_init_node(
            node_id="moduletroubleindicators",
            name="Module Trouble Indicators",
            properties=trouble_properties,
        )
        for t in self.module_trouble_indicators:
            self.homie_init_property(
                node_id="moduletroubleindicators",
                property_id=self.module_trouble_indicators[t]["machine_label"],
                name=self.module_trouble_indicators[t]["name"],
                datatype="boolean",
            )

    def homie_publish_panel(self):
        self.homie_publish_property(
            node_id="panel",
            property_id="panelid",
            datatype="integer",
            value=self.panelid,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="panelname",
            datatype="string",
            value=self.panelname,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="firmwareversion",
            datatype="string",
            value=self.firmwareversion,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="firmwarerevision",
            datatype="string",
            value=self.firmwarerevision,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="firmwarebuild",
            datatype="string",
            value=self.firmwarebuild,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="programmedpanelida",
            datatype="string",
            value=self.programmedpanelida,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="programmedpanelidb",
            datatype="string",
            value=self.programmedpanelidb,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="programmedpanelid1",
            datatype="string",
            value=self.programmedpanelid1,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="programmedpanelid2",
            datatype="string",
            value=self.programmedpanelid2,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="programmedpanelid3",
            datatype="string",
            value=self.programmedpanelid3,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="programmedpanelid4",
            datatype="string",
            value=self.programmedpanelid4,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="paneltime",
            datatype="string",
            value=self.timestamp_str(self.paneltime),
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="messagetime",
            datatype="string",
            value=self.timestamp_str(self.messagetime),
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="softwaredirectconnected",
            datatype="boolean",
            value=self.softwaredirectconnected,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="softwareconnected",
            datatype="boolean",
            value=self.softwareconnected,
        )
        self.homie_publish_property(
            node_id="panel", property_id="alarm", datatype="boolean", value=self.alarm
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="eventreporting",
            datatype="boolean",
            value=self.eventreporting,
        )
        self.homie_publish_property(
            node_id="panel", property_id="bell", datatype="boolean", value=self.bell
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="inputdcvoltage",
            datatype="float",
            value=self.input_dc_voltage,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="powersupplydcvoltage",
            datatype="float",
            value=self.power_supply_dc_voltage,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="batterydcvoltage",
            datatype="float",
            value=self.battery_dc_voltage,
        )

    def homie_publish_trouble_indicators(self):
        for t in self.trouble_indicators:
            self.homie_publish_property(
                node_id="troubleindicators",
                property_id=self.trouble_indicators[t]["machine_label"],
                datatype="boolean",
                value=self.trouble_indicators[t]["status"],
            )

    def homie_publish_module_trouble_indicators(self):
        for t in self.module_trouble_indicators:
            self.homie_publish_property(
                node_id="moduletroubleindicators",
                property_id=self.module_trouble_indicators[t]["machine_label"],
                datatype="boolean",
                value=self.module_trouble_indicators[t]["status"],
            )

    def homie_init_partitions(self):
        for i in range(1, 2 + 1):
            node_id = self.partition_data[i]["machine_label"]
            self.homie_init_node(
                node_id=node_id,
                name=self.partition_data[i]["label"],
                type=None,
                properties="alarm,armed,armstate,armstatetext,armstatehass",
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="alarm",
                name="Alarm",
                datatype="boolean",
                settable=False,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="armed",
                name="Armed",
                datatype="boolean",
                settable=True,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="armstate",
                name="Arm State",
                datatype="integer",
                settable=True,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="armstatetext",
                name="Arm State Text",
                datatype="string",
                settable=True,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="armstatehass",
                name="Arm State Home Assistant",
                datatype="enum",
                format="disarmed,armed_home,armed_night,armed_away,triggered",
                settable=True,
            )
            self.hass_init_alarmcontrolpanel_config(partition=i)

    def homie_publish_partitions(self):
        for i in range(1, 2 + 1):
            node_id = self.partition_data[i]["machine_label"]
            self.homie_publish_property(
                node_id=node_id,
                property_id="alarm",
                datatype="boolean",
                value=self.partition_data[i]["alarm"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="armed",
                datatype="boolean",
                value=self.partition_data[i]["armed"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="armstate",
                datatype="integer",
                value=self.partition_data[i]["armstate"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="armstatetext",
                datatype="string",
                value=self.partition_data[i]["armstatetext"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="armstatehass",
                datatype="string",
                value=self.partition_data[i]["armstatehass"],
            )

    def homie_init_outputs(self):
        for i in range(1, self.outputs + 1):
            node_id = self.output_data[i]["machine_label"]
            self.homie_init_node(
                node_id=node_id,
                name=self.output_data[i]["label"],
                type=None,
                properties="on,pulse,tamper,supervisiontrouble",
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="on",
                name="On",
                datatype="boolean",
                settable=True,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="pulse",
                name="Pulse",
                datatype="boolean",
                settable=True,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="tamper",
                name="Tamper",
                datatype="boolean",
                settable=False,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="supervisiontrouble",
                name="Supervision Trouble",
                datatype="boolean",
                settable=False,
            )

    def homie_publish_outputs(self):
        for i in range(1, self.outputs + 1):
            node_id = self.output_data[i]["machine_label"]
            self.homie_publish_property(
                node_id=node_id,
                property_id="on",
                datatype="boolean",
                value=self.output_data[i]["on"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="pulse",
                datatype="boolean",
                value=self.output_data[i]["pulse"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="tamper",
                datatype="boolean",
                value=self.output_data[i]["tamper"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="supervisiontrouble",
                datatype="boolean",
                value=self.output_data[i]["supervisiontrouble"],
            )

    def homie_init_zones(self):
        for i in range(1, self.zones + 1):
            node_id = self.zone_data[i]["machine_label"]
            self.homie_init_node(
                node_id=node_id,
                name=self.zone_data[i]["label"],
                type=None,
                properties="open,bypass,alarm,firealarm,shutdown,tamper,lowbattery,supervisiontrouble",
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="open",
                name="Open",
                datatype="boolean",
                settable=False,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="bypass",
                name="Bypass",
                datatype="boolean",
                settable=True,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="alarm",
                name="Alarm",
                datatype="boolean",
                settable=False,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="firealarm",
                name="Fire Alarm",
                datatype="boolean",
                settable=False,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="shutdown",
                name="Shutdown",
                datatype="boolean",
                settable=False,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="tamper",
                name="Tamper",
                datatype="boolean",
                settable=False,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="lowbattery",
                name="Low Battery",
                datatype="boolean",
                settable=False,
            )
            self.homie_init_property(
                node_id=node_id,
                property_id="supervisiontrouble",
                name="Supervision Trouble",
                datatype="boolean",
                settable=False,
            )

    def homie_publish_zones(self):
        for i in range(1, self.zones + 1):
            node_id = self.zone_data[i]["machine_label"]
            self.homie_publish_property(
                node_id=node_id,
                property_id="open",
                datatype="boolean",
                value=self.zone_data[i]["open"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="bypass",
                datatype="boolean",
                value=self.zone_data[i]["bypass"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="alarm",
                datatype="boolean",
                value=self.zone_data[i]["alarm"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="firealarm",
                datatype="boolean",
                value=self.zone_data[i]["firealarm"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="shutdown",
                datatype="boolean",
                value=self.zone_data[i]["shutdown"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="tamper",
                datatype="boolean",
                value=self.zone_data[i]["tamper"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="lowbattery",
                datatype="boolean",
                value=self.zone_data[i]["lowbattery"],
            )
            self.homie_publish_property(
                node_id=node_id,
                property_id="supervisiontrouble",
                datatype="boolean",
                value=self.zone_data[i]["supervisiontrouble"],
            )

    def homie_init_last_zone_event(self):
        self.homie_init_node(
            node_id="lastzoneevent",
            name="Last Zone Event",
            properties="zone,label,property,state,time",
        )
        self.homie_init_property(
            node_id="lastzoneevent", property_id="zone", name="Zone", datatype="string"
        )
        self.homie_init_property(
            node_id="lastzoneevent",
            property_id="label",
            name="Zone Name",
            datatype="string",
        )
        self.homie_init_property(
            node_id="lastzoneevent",
            property_id="property",
            name="Zone Property",
            datatype="string",
        )
        self.homie_init_property(
            node_id="lastzoneevent",
            property_id="state",
            name="Zone Property State",
            datatype="boolean",
        )
        self.homie_init_property(
            node_id="lastzoneevent",
            property_id="time",
            name="Event Time",
            datatype="string",
        )

    def homie_publish_last_zone_event(self, zone_number, property):
        if self.zone_data[zone_number][property] != None:
            self.homie_publish_property(
                node_id="lastzoneevent",
                property_id="zone",
                datatype="string",
                value=self.zone_data[zone_number]["machine_label"],
            )
            self.homie_publish_property(
                node_id="lastzoneevent",
                property_id="label",
                datatype="string",
                value=self.zone_data[zone_number]["label"],
            )
            self.homie_publish_property(
                node_id="lastzoneevent",
                property_id="property",
                datatype="string",
                value=property,
            )
            self.homie_publish_property(
                node_id="lastzoneevent",
                property_id="state",
                datatype="boolean",
                value=self.zone_data[zone_number][property],
            )
            sleep(0.1)
            self.homie_publish_property(
                node_id="lastzoneevent",
                property_id="time",
                datatype="string",
                value=self.timestamp_str(),
            )

    def update_bell(self, bell):
        if bell != self.bell:
            self.bell = bell
            if bell:
                logger.warning("Bell on!")
            else:
                logger.warning("Bell off.")
            self.homie_publish_property(
                node_id="panel", property_id="bell", datatype="boolean", value=self.bell
            )

    def update_panel(
        self,
        panelid,
        firmwareversion,
        firmwarerevision,
        firmwarebuild,
        programmedpanelida,
        programmedpanelidb,
    ):
        if (
            panelid != self.panelid
            or self.firmwareversion != firmwareversion
            or self.firmwarerevision != firmwarerevision
            or self.firmwarebuild != firmwarebuild
            or self.programmedpanelida != programmedpanelida
            or self.programmedpanelidb != programmedpanelidb
        ):
            self.panelid = panelid
            if panelid == 21:
                self.panelname = "SP5500"
            elif panelid == 22:
                self.panelname = "SP6000"
            elif panelid == 23:
                self.panelname = "SP7000"
            elif panelid == 64:
                self.panelname = "MG5000"
            elif panelid == 65:
                self.panelname = "MG5050"
            else:
                logger.error("Invalid panelid {:d}".format(panelid))
            self.firmwareversion = firmwareversion
            self.firmwarerevision = firmwarerevision
            self.firmwarebuild = firmwarebuild
            self.programmedpanelid1, self.programmedpanelid2 = split_high_low_nibble(
                programmedpanelida
            )
            self.programmedpanelid3, self.programmedpanelid4 = split_high_low_nibble(
                programmedpanelidb
            )
            self.homie_publish_panel()

    def update_voltages(
        self, input_dc_voltage, power_supply_dc_voltage, battery_dc_voltage
    ):
        self.input_dc_voltage = input_dc_voltage
        self.power_supply_dc_voltage = power_supply_dc_voltage
        self.battery_dc_voltage = battery_dc_voltage
        self.homie_publish_property(
            node_id="panel",
            property_id="inputdcvoltage",
            datatype="float",
            value=self.input_dc_voltage,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="powersupplydcvoltage",
            datatype="float",
            value=self.power_supply_dc_voltage,
        )
        self.homie_publish_property(
            node_id="panel",
            property_id="batterydcvoltage",
            datatype="float",
            value=self.battery_dc_voltage,
        )
        logger.debug(
            "input_dc_voltage: {:.2f} | power_supply_dc_voltage: {:.2f} | battery_dc_voltage: {:.2f}".format(
                input_dc_voltage, power_supply_dc_voltage, battery_dc_voltage
            )
        )

    def update_partition_property(
        self, partition_number, property="armstate", value=None
    ):
        if partition_number > 2 or partition_number < 0:
            logger.error("Invalid partition_number {:d}".format(partition_number))
            return
        if value != None:
            if (
                self.partition_data[partition_number][property] == None
                or self.partition_data[partition_number][property] != value
            ):
                label = self.partition_data[partition_number]["label"]
                self.partition_data[partition_number][property] = value
                logger.info(
                    'Partition {:d},"{}", {} = {}.'.format(
                        partition_number, label, property, value
                    )
                )
                if property in ["alarm"]:
                    self.homie_publish_property(
                        node_id=self.partition_data[partition_number]["machine_label"],
                        property_id=property,
                        datatype="boolean",
                        value=value,
                    )
                elif property in ["armed"]:
                    self.homie_publish_property(
                        node_id=self.partition_data[partition_number]["machine_label"],
                        property_id=property,
                        datatype="boolean",
                        value=value,
                    )
                elif property in ["armstate"]:
                    self.homie_publish_property(
                        node_id=self.partition_data[partition_number]["machine_label"],
                        property_id=property,
                        datatype="integer",
                        value=value,
                    )
                elif property in ["armstatetext"]:
                    self.homie_publish_property(
                        node_id=self.partition_data[partition_number]["machine_label"],
                        property_id=property,
                        datatype="string",
                        value=value,
                    )
                elif property in ["armstatehass"]:
                    self.homie_publish_property(
                        node_id=self.partition_data[partition_number]["machine_label"],
                        property_id=property,
                        datatype="string",
                        value=value,
                    )
                if property == "armstate" and value == 0:
                    self.clear_on_disarm()

    def update_output_property(self, output_number, property=None, flag=None):
        if output_number > self.outputs or output_number < 1:
            logger.error("Invalid output_number {:d}".format(output_number))
            return
        if flag != None:
            if (
                self.output_data[output_number][property] == None
                or self.output_data[output_number][property] != flag
            ):
                label = self.output_data[output_number]["label"]
                self.output_data[output_number][property] = flag
                if flag:
                    logger.info(
                        'Output {:d},"{}", {}.'.format(output_number, label, property)
                    )
                else:
                    logger.info(
                        'Output {:d},"{}", Not {}.'.format(
                            output_number, label, property
                        )
                    )
                self.homie_publish_property(
                    node_id=self.output_data[output_number]["machine_label"],
                    property_id=property,
                    datatype="boolean",
                    value=flag,
                )

    def update_output_label(self, output_number, label=None):
        if output_number > self.outputs or output_number < 1:
            logger.error("Invalid output_number {:d}".format(output_number))
            return
        if label != None:
            if (
                self.output_data[output_number]["label"] == None
                or self.output_data[output_number]["label"] != label
            ):
                self.output_data[output_number]["label"] = label
                logger.info(
                    'Output {:d} label set to "{}".'.format(output_number, label)
                )
            self.eventmap.setoutputLabel(
                output_number, self.output_data[output_number]["machine_label"]
            )

    def update_zone_property(self, zone_number, property="open", flag=None):
        if zone_number > self.zones or zone_number < 1:
            logger.error("Invalid zone_number {:d}".format(zone_number))
            return
        if flag != None:
            if (
                self.zone_data[zone_number][property] == None
                or self.zone_data[zone_number][property] != flag
            ):
                label = self.zone_data[zone_number]["label"]
                self.zone_data[zone_number][property] = flag
                if flag:
                    logger.info(
                        'Zone {:d},"{}", {}.'.format(zone_number, label, property)
                    )
                else:
                    logger.info(
                        'Zone {:d},"{}", Not {}.'.format(zone_number, label, property)
                    )
                self.homie_publish_property(
                    node_id=self.zone_data[zone_number]["machine_label"],
                    property_id=property,
                    datatype="boolean",
                    value=flag,
                )
                self.homie_publish_last_zone_event(zone_number, property)

    def update_trouble_indicator(self, trouble_number, flag=None):
        if trouble_number not in self.trouble_indicators:
            logger.error("Invalid trouble_number {:d}".format(trouble_number))
        elif flag != None:
            if (
                self.trouble_indicators[trouble_number]["status"] == None
                or self.trouble_indicators[trouble_number]["status"] != flag
            ):
                machine_label = self.trouble_indicators[trouble_number]["machine_label"]
                self.trouble_indicators[trouble_number]["status"] = flag
                if flag:
                    logger.info(
                        'Trouble {:d},"{}", {}.'.format(
                            trouble_number, machine_label, "status"
                        )
                    )
                else:
                    logger.info(
                        'Trouble {:d},"{}", Not {}.'.format(
                            trouble_number, machine_label, "status"
                        )
                    )
                self.homie_publish_property(
                    node_id="troubleindicators",
                    property_id=machine_label,
                    datatype="boolean",
                    value=flag,
                )

    def update_module_trouble_indicator(self, trouble_number, flag=None):
        if trouble_number not in self.module.trouble_indicators:
            logger.error("Invalid trouble_number {:d}".format(trouble_number))
        elif flag != None:
            if (
                self.module_trouble_indicators[trouble_number]["status"] == None
                or self.module_trouble_indicators[trouble_number]["status"] != flag
            ):
                machine_label = self.module_trouble_indicators[trouble_number][
                    "machine_label"
                ]
                self.module_trouble_indicators[trouble_number]["status"] = flag
                if flag:
                    logger.info(
                        'Module Trouble {:d},"{}", {}.'.format(
                            trouble_number, machine_label, "status"
                        )
                    )
                else:
                    logger.info(
                        'Module Trouble {:d},"{}", Not {}.'.format(
                            trouble_number, machine_label, "status"
                        )
                    )
                self.homie_publish_property(
                    node_id="moduletroubleindicators",
                    property_id=machine_label,
                    datatype="boolean",
                    value=flag,
                )

    def toggle_zone_property(self, zone_number, property="open"):
        if zone_number > self.zones or zone_number < 1:
            logger.error("Invalid zone_number {:d}".format(zone_number))
            return
        self.update_zone_property(
            zone_number=zone_number,
            property=property,
            flag=not self.zone_data[zone_number][property],
        )

    def update_zone_label(self, zone_number, label=None):
        if zone_number > self.zones or zone_number < 1:
            logger.error("Invalid zone_number {:d}".format(zone_number))
            return
        if label != None:
            if (
                self.zone_data[zone_number]["label"] == None
                or self.zone_data[zone_number]["label"] != label
            ):
                self.zone_data[zone_number]["label"] = label
                logger.info('Zone {:d} label set to "{}".'.format(zone_number, label))
            self.eventmap.setzoneLabel(
                zone_number, self.zone_data[zone_number]["machine_label"]
            )

    def update_label(
        self, partition_number=0, subevent_number=0, label_type=0, label=None
    ):
        if label == None:
            return
        if label_type == 0:  # Zone labels
            self.update_zone_label(zone_number=subevent_number, label=label)
        elif label_type == 1:  # User labels
            self.update_user_label(user_number=subevent_number, label=label)
        elif label_type == 2:  # Partition labels
            self.update_partition_label(partition_number=partition_number, label=label)
        elif label_type == 3:  # Output labels
            if subevent_number > 0 and subevent_number <= self.outputs:
                self.update_output_label(output_number=subevent_number, label=label)
        else:
            logger.error("Can't process label_type={:d} ".format(label_type))

    def update_user_label(self, user_number, label=None):
        if user_number > self.users or user_number < 1:
            logger.error("Invalid user_number {:d}".format(user_number))
            return
        if label != None:
            if (
                self.user_data[user_number]["label"] == None
                or self.user_data[user_number]["label"] != label
            ):
                self.user_data[user_number]["label"] = label
                logger.info('User {:d} label set to "{}".'.format(user_number, label))
            self.eventmap.setuserLabel(
                user_number, self.user_data[user_number]["machine_label"]
            )

    def update_partition_label(self, partition_number, label=None):
        if partition_number > 2 or partition_number < 1:
            logger.error("Invalid partition_number {:d}".format(partition_number))
            return
        if label != None:
            if (
                self.partition_data[partition_number]["label"] == None
                or self.partition_data[partition_number]["label"] != label
            ):
                self.partition_data[partition_number]["label"] = label
                logger.info(
                    'Partition {:d} label set to "{}".'.format(partition_number, label)
                )

    def process_low_nibble(self, low_nibble):
        softwaredirectconnected = test_bit(low_nibble, 0) == True
        softwareconnected = test_bit(low_nibble, 1) == True
        alarm = test_bit(low_nibble, 2) == True
        eventreporting = test_bit(low_nibble, 3) == True

        if self.softwaredirectconnected != softwaredirectconnected:
            self.softwaredirectconnected = softwaredirectconnected
            self.homie_publish_property(
                node_id="panel",
                property_id="softwaredirectconnected",
                datatype="boolean",
                value=self.softwaredirectconnected,
            )
            if self.softwaredirectconnected:
                logger.info("Software directly connected.")
            else:
                logger.info("Software direct disconnected.")

        if self.softwareconnected != softwareconnected:
            self.softwareconnected = softwareconnected
            self.homie_publish_property(
                node_id="panel",
                property_id="softwareconnected",
                datatype="boolean",
                value=self.softwareconnected,
            )
            if self.softwareconnected:
                logger.info("Software connected.")
            else:
                logger.info("Software disconnected.")

        if self.alarm != alarm:
            self.alarm = alarm
            self.homie_publish_property(
                node_id="panel",
                property_id="alarm",
                datatype="boolean",
                value=self.alarm,
            )
            if self.alarm:
                logger.warning("Alarm activated!")
            else:
                logger.info("Alarm deactivated.")
                self.update_partition_property(
                    partition_number=1, property="alarm", value=False
                )
                self.update_partition_property(
                    partition_number=2, property="alarm", value=False
                )

        if self.eventreporting != eventreporting:
            self.eventreporting = eventreporting
            self.homie_publish_property(
                node_id="panel",
                property_id="eventreporting",
                datatype="boolean",
                value=self.eventreporting,
            )
            if self.eventreporting:
                logger.info("Event reporting activated.")
            else:
                logger.info("Event reporting disabled.")

        logger.debug("software_direct connected: {0}".format(softwaredirectconnected))
        logger.debug("Software connected: {0}".format(softwareconnected))
        logger.debug("Alarm: {0}".format(alarm))
        logger.debug("Event reporting: {0}".format(eventreporting))

    def check_time(self):
        now = datetime.now()
        if self.paneltime:
            diff = abs(self.paneltime - now).total_seconds() / 60
        else:
            diff = UPDATE_ALARM_TIME_DIFF_MINUTES
        logger.debug("PC time: {:%Y-%m-%d %H:%M}".format(now))
        if diff >= UPDATE_ALARM_TIME_DIFF_MINUTES:
            logger.info("Time out by {:.1f} minutes.  Updating.".format(diff))
            self.set_time()
        else:
            logger.debug("Time out by {:.1f} minutes.  Close enough.".format(diff))

    def process_panel_status_response(self, message):
        logger.debug("Processing Keep Alive Response...")
        if message[2] == 128:  # Not an eeprom read
            panel_status = message[3]
            if panel_status == 0:
                # Alarm Time
                try:
                    self.paneltime = datetime(
                        message[9] * 100 + message[10],
                        message[11],
                        message[12],
                        message[13],
                        message[14],
                    )
                    self.homie_publish_property(
                        node_id="panel",
                        property_id="paneltime",
                        datatype="string",
                        value=self.timestamp_str(self.paneltime),
                    )
                    logger.debug("Panel time: {:%Y-%m-%d %H:%M}".format(self.paneltime))
                except:
                    self.paneltime = None
                self.check_time()
                # Voltage
                self.update_voltages(
                    input_dc_voltage=round(message[15] * (20.3 - 1.4) / 255.0 + 1.4, 1),
                    power_supply_dc_voltage=round(message[16] * 22.8 / 255.0, 1),
                    battery_dc_voltage=round(message[17] * 22.8 / 255.0, 1),
                )
                # Zone statuses
                for i in range(0, 4):
                    byte = message[19 + i]
                    for j in range(0, 8):
                        open = (byte >> j) & 0x01
                        zone_number = i * 8 + j + 1
                        self.update_zone_property(
                            zone_number, property="open", flag=open
                        )
            elif panel_status == 1:
                # Parition Status
                for i in range(0, 2):
                    partition_number = i + 1
                    # logger.info('Partition {:d} status bytes'.format(partition_number))
                    # for j in range(17,21):
                    #    logger.info('Byte {:d}: {:d}'.format(j,message[j+4*i]))
                    #    logger.info('Byte {:d}: Bits: {:08b}'.format(j,message[j+4*i]))
                    arm = test_bit(message[17 + i * 4], 0)
                    arm_sleep = test_bit(message[17 + i * 4], 1)
                    arm_stay = test_bit(message[17 + i * 4], 2)
                    if arm_stay:
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armed",
                            value=True,
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstate",
                            value=1,
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstatetext",
                            value="STAY",
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstatehass",
                            value="armed_home",
                        )
                    elif arm_sleep:
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armed",
                            value=True,
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstate",
                            value=2,
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstatetext",
                            value="SLEEP",
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstatehass",
                            value="armed_night",
                        )
                    elif arm:
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armed",
                            value=True,
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstate",
                            value=3,
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstatetext",
                            value="ARM",
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstatehass",
                            value="armed_away",
                        )
                    else:
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armed",
                            value=False,
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstate",
                            value=0,
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstatetext",
                            value="DISARM",
                        )
                        self.update_partition_property(
                            partition_number=partition_number,
                            property="armstatehass",
                            value="disarmed",
                        )

            elif panel_status == 2:
                # Zone Bypass Status
                for i in range(0, self.zones - 1):
                    bypass = test_bit(message[4 + i], 3)
                    self.update_zone_property(
                        zone_number=i + 1, property="bypass", flag=bypass
                    )
            elif panel_status > 2 and panel_status < 7:
                pass  # What do these do?
            else:
                logger.error(
                    "Invalid panel_statusuence {:d} on keep alive.".format(panel_status)
                )
        elif message[2] == 31 and message[3] == 224:
            logger.debug("Final keep alive response.")
        else:
            logger.error("Can't process this keep alive response:{}".format(message))

    def process_live_event_command(self, message):
        logger.debug("Processing live event command...")
        event_number = message[7]
        subevent_number = message[8]
        partition_number = message[9] + 1
        try:
            event_timestamp = datetime(
                message[1] * 100 + message[2],
                message[3],
                message[4],
                message[5],
                message[6],
            )
        except:
            event_timestamp = None
        module_serial = (
            int(message[10]) * 10
            ^ 8 + int(message[11]) * 10
            ^ 4 + int(message[12]) * 10
            ^ 2 + int(message[13]) * 10
            ^ 0
        )
        label_type = message[14]
        if event_timestamp:
            logger.debug("Alarm timestamp: {:%Y-%m-%d %H:%M}".format(event_timestamp))
        logger.debug("Partition number: {:d}".format(partition_number))
        logger.debug("Module serial: {:d}".format(module_serial))
        logger.debug("Label type: {:d}".format(label_type))
        logger.debug(
            "event_number: {:d}, subevent_number {:d}".format(
                event_number, subevent_number
            )
        )
        label = message[15:31].decode("utf-8").strip()
        logger.debug(
            "event_number: {:d}, subevent_number: {:d}, partition_number: {:d}, label_type: {:d}, label: {}".format(
                event_number, subevent_number, partition_number, label_type, label
            )
        )
        event, subevent = self.eventmap.getEventDescription(
            event_number, subevent_number
        )
        logger.info(
            "partition_number: {:d}, event: {}, subevent {}".format(
                partition_number, event, subevent
            )
        )
        # self.publish_raw_event(partition_number, event_number, subevent_number)
        if label != None:
            if ord(label[0]) == 0 or len(label) == 0:
                label = None
        if label != None:
            self.update_label(
                partition_number=partition_number,
                subevent_number=subevent_number,
                label_type=label_type,
                label=label,
            )
        logger.debug(
            "event: {}, subevent: {}, label: {}".format(event, subevent, label)
        )
        if event_number in (0, 1):  # Zone open
            self.update_zone_property(
                subevent_number, property="open", flag=event_number == 1
            )
        elif event_number == 2:  # Partition status
            if subevent_number in [2, 3, 4, 5, 6]:  # alarm subevents
                self.update_partition_property(
                    partition_number=partition_number, property="alarm", value=True
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstatehass",
                    value="triggered",
                )
            elif subevent_number == 7:  # Alarm stopped
                self.update_partition_property(
                    partition_number=partition_number, property="alarm", value=False
                )
            elif subevent_number == 11:  # Disarm partion
                self.update_partition_property(
                    partition_number=partition_number, property="armed", value=False
                )
                self.update_partition_property(
                    partition_number=partition_number, property="armstate", value=0
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstatetext",
                    value="DISARM",
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstatehass",
                    value="disarmed",
                )

                self.update_partition_property(
                    partition_number=partition_number, property="alarm", value=False
                )
                self.clear_on_disarm()
            elif subevent_number == 12:  # Arm partion
                # This is indication of arming of partition but not which type.
                # Ignore this sub event as others will indicate the type
                pass
        elif event_number == 3:  # Bell status
            if subevent_number in (0, 1):
                self.update_bell(subevent_number == 1)
            else:
                pass  # we don't do anything with other bell events
        elif event_number == 6:  # Non-reportable events
            if subevent_number == 3:  # Arm in stay mode
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armed",
                    value=True,
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstate",
                    value=1,
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstatetext",
                    value="STAY",
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstatehass",
                    value="armed_home",
                )

            elif subevent_number == 4:  # Arm in sleep mode
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armed",
                    value=True,
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstate",
                    value=2,
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstatetext",
                    value="SLEEP",
                )
                self.update_partition_property(
                    partition_number=partition_number,
                    property="armstatehass",
                    value="armed_night",
                )

        elif event_number == 35:  # Zone bypass
            self.toggle_zone_property(subevent_number, property="bypass")
        elif event_number in (36, 38):  # Zone alarm
            self.update_zone_property(
                subevent_number, property="alarm", flag=event_number == 36
            )
        elif event_number in (37, 39):  # Zone fire alarm
            self.update_zone_property(
                subevent_number, property="firealarm", flag=event_number == 37
            )
        elif event_number == 41:  # Zone shutdown?
            self.update_zone_property(subevent_number, property="shutdown", flag=True)
        elif event_number in (42, 43):  # Zone tamper
            self.update_zone_property(
                subevent_number, property="tamper", flag=event_number == 42
            )
        elif event_number in (44, 45):  # Trouble
            self.update_trouble_indicator(subevent_number, flag=event_number == 44)
        elif event_number in (46, 47):  # Trouble
            self.update_module_trouble_indicator(
                subevent_number, flag=event_number == 46
            )
        elif event_number in (49, 50):  # Zone battery
            self.update_zone_property(
                subevent_number, property="lowbattery", flag=event_number == 49
            )
        elif event_number in (51, 52):  # Zone supervisiontrouble
            self.update_zone_property(
                subevent_number, property="supervisiontrouble", flag=event_number == 51
            )
        elif event_number in (53, 54):  # Wireless module supervisiontrouble
            if subevent_number > 0 and subevent_number <= self.outputs:
                self.update_output_property(
                    subevent_number,
                    property="supervisiontrouble",
                    flag=event_number == 53,
                )
        elif event_number in (55, 56):  # Wireless module tamper trouble
            if subevent_number > 0 and subevent_number <= self.outputs:
                self.update_output_property(
                    subevent_number, property="tamper", flag=event_number == 55
                )
        else:
            logger.debug("Nothing special to do for this event.")

    def process_start_communication_response(self, message):
        """Process start communication response to fetch panelid etc."""
        self.update_panel(
            panelid=message[4],
            firmwareversion=message[5],
            firmwarerevision=message[6],
            firmwarebuild=message[7],
            programmedpanelida=message[8],
            programmedpanelidb=message[9],
        )

    def process_initialize_communication_response(self, message):
        """Nothing to do as for WinLoad the message contains no useful info."""
        logger.debug("Panel received initialize communication message.")

    def process_set_time_date_response(self, message):
        """Nothing to do as for WinLoad the message contains no useful info."""
        logger.info("Panel date & time updated.")

    def process_action_response(self, message):
        """Process result of perform action command."""
        action = message[2]
        if action == 16:  # Bypass action
            zone_number = message[3] + 1
            logger.debug(
                "Bypass command received by panel for zone_number={:d}".format(
                    zone_number
                )
            )
            self.toggle_zone_property(zone_number=zone_number, property="bypass")
        else:  # Unknown action response
            logger.error(
                "Received unkown action on action_response from panel: {:d}".format(
                    action
                )
            )

    def process_message(self, message):
        """Process message."""
        logger.debug("Processing message...")
        logger.debug("message[0]= {}".format(message[0]))
        high_nibble, low_nibble = split_high_low_nibble(message[0])
        logger.debug("High Nibble: {:d}".format(high_nibble))
        logger.debug("Low Nibble: {:d}".format(low_nibble))

        valid_checksum = self.verify_checksum(message)
        if not valid_checksum:
            logger.warning(
                "Message checksum fails.  Skipping message and flushing input buffer."
            )
            self.connection.reset_input_buffer()
            return
        self.messagetime = datetime.now()
        self.homie_publish_property(
            node_id="panel",
            property_id="messagetime",
            datatype="string",
            value=self.timestamp_str(self.messagetime),
        )
        if high_nibble != 15:
            self.process_low_nibble(low_nibble)
        if high_nibble == 0:  # Start communication response
            self.process_start_communication_response(message)
        elif high_nibble == 1:  # Initialize Communication Response
            self.process_initialize_communication_response(message)
        elif high_nibble == 3:  # Set time & date response
            self.process_set_time_date_response(message)
        elif high_nibble == 4:  # Action response
            self.process_action_response(message)
        elif high_nibble == 5:  # Keep Alive Response
            self.process_panel_status_response(message)
        elif high_nibble == 7:  # Error & disconnect  message from panel
            logger.error("Panel sent an error message and/or disconnected.")
        elif high_nibble == 14:  # Live Event command, not sure about 15
            self.process_live_event_command(message)
        else:
            logger.error(
                "Could not process message: {} (high_nibble={:d})".format(
                    message, high_nibble
                )
            )
            self.connection.reset_input_buffer()

    def send_message(self, message):
        """Send a message."""
        checksum = self.calc_checksum(message)
        if checksum:
            message += bytearray([checksum])

        logger.debug("Sending message {}...".format(message))
        self.connection.write(message)
        logger.debug("Message sent.")

    def send_and_process_reply(self, message, tries=3):
        """Send a message and wait for a single reply, and process it."""
        attempts = 0
        reply = None
        while attempts < tries and reply == None:
            self.send_message(message)
            reply = self.wait_for_message()
            attempts += 1
        if reply != None:
            self.process_message(reply)
        return reply

    def send_and_wait_for_reply(self, message, tries=3):
        """Send a message and wait for a single reply."""
        attempts = 0
        reply = None
        while attempts < tries and reply == None:
            self.send_message(message)
            reply = self.wait_for_message()
            attempts += 1
        return reply

    def calc_checksum(self, message):
        """Calculate a checksum for a message."""
        checksum = 0
        if len(message) == 36:
            for val in message:
                checksum += val
            while checksum > 255:
                checksum = checksum - int(checksum / 256) * 256
            return checksum
        else:
            logger.debug(
                "Message not 36 byes.  Cannot calculate checksum. Message: {}".format(
                    message
                )
            )
            return None

    def verify_checksum(self, message):
        if len(message) != 37:
            logger.debug("Message not 37 byes.  Message: {}".format(message))
            return False
        checksum = self.calc_checksum(message[:36])
        return checksum == message[36]

    def connect_software(self):
        """Software connection to alarm."""
        if PASSWORD != None:
            logger.info("Logging into to alarm.")

        logger.info("Software connecting to alarm.")
        message = b"\x72\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        reply = self.send_and_process_reply(message)

        message = b"\x50\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        reply = self.send_and_process_reply(message)

        message = b"\x5f\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        reply = self.send_and_process_reply(message)

        # message = reply
        message = (
            reply[0:10]
            + reply[8:10]
            + b"\x19\x00\x00"
            + reply[15:23]
            + b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00"
        )
        reply = self.send_and_process_reply(message)

        message = b"\x50\x00\x1f\xe0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x4f"
        reply = self.send_and_process_reply(message)

        message = b"\x50\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        reply = self.send_and_process_reply(message)

        message = b"\x50\x00\x0e\x52\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        reply = self.send_and_process_reply(message)

        self.softwareconnected = True
        self.connection.reset_input_buffer()
        return True

    def set_time(self):
        message = b"\x30\x00\x00\x00"
        now = datetime.now()
        message += bytes(
            [
                floor(now.year / 100),
                now.year - floor(now.year / 100) * 100,
                now.month,
                now.day,
                now.hour,
                now.minute,
                now.second,
            ]
        )
        message = message.ljust(36, b"\x00")
        self.send_message(message)

    def keep_alive(self):
        logger.debug("Sending keep alive messages...")
        base_message = b"\x50\x00\x80"
        for i in range(0, 7):
            message = (base_message + bytes([i])).ljust(36, b"\x00")
            self.wait_for_message(timeout=0.1, process_message=True)
            self.send_and_process_reply(message)
        sleep(0.1)
        message = b"\x50\x00\x1f\xe0".ljust(36, b"\x00") + b"\x4f"
        self.send_and_process_reply(message)
        logger.debug("Keep alive done.")

    def read_zone_labels(self):
        logger.info("Reading zone labels...")
        register_dict = getattr(self.registermap, "get" + "zoneLabel" + "Register")()
        for i in range(0, int(self.zones / 2)):
            self.wait_for_message(timeout=0.1, process_message=True)
            message = bytearray(register_dict[i * 2 + 1]["Send"], encoding="latin")
            message = message.ljust(36, b"\x00")
            reply = self.send_and_wait_for_reply(message)
            logger.debug("Label packet: {}".format(reply))
            if reply != None:
                try:
                    label = reply[4:20].decode("utf-8").strip()
                except:
                    logger.error(
                        "Could not extract label from message {}.".format(reply)
                    )
                    label = None
                if label != None:
                    if ord(label[0]) == 0 or len(label) == 0:
                        label = None
                self.update_zone_label(zone_number=i * 2 + 1, label=label)
                try:
                    label = reply[20:36].decode("utf-8").strip()
                except:
                    logger.error(
                        "Could not extract label from message {}.".format(reply)
                    )
                    label = None
                if label != None:
                    if ord(label[0]) == 0 or len(label) == 0:
                        label = None
                self.update_zone_label(zone_number=i * 2 + 2, label=label)
        logger.info("Read zone labels.")

    def read_user_labels(self):
        logger.info("Reading user labels...")
        register_dict = getattr(self.registermap, "get" + "userLabel" + "Register")()
        for i in range(0, int(self.users / 2)):
            sleep(0.1)
            message = bytearray(register_dict[i * 2 + 1]["Send"], encoding="latin")
            message = message.ljust(36, b"\x00")
            reply = self.send_and_wait_for_reply(message)
            logger.debug("Label packet: {}".format(reply))
            if reply != None:
                try:
                    label = reply[4:20].decode("utf-8").strip()
                except:
                    logger.error(
                        "Could not extract label from message {}.".format(reply)
                    )
                    label = None
                if label != None:
                    if ord(label[0]) == 0 or len(label) == 0:
                        label = None
                self.update_user_label(user_number=i * 2 + 1, label=label)
                try:
                    label = reply[20:36].decode("utf-8").strip()
                except:
                    logger.error(
                        "Could not extract label from message {}.".format(reply)
                    )
                    label = None
                if label != None:
                    if ord(label[0]) == 0 or len(label) == 0:
                        label = None
                self.update_user_label(user_number=i * 2 + 2, label=label)
        logger.info("Read user labels.")

    def read_partition_labels(self):
        logger.info("Reading partition labels...")
        register_dict = getattr(
            self.registermap, "get" + "partitionLabel" + "Register"
        )()
        for i in range(0, 1):
            self.wait_for_message(timeout=0.1, process_message=True)
            message = bytearray(register_dict[i * 2 + 1]["Send"], encoding="latin")
            message = message.ljust(36, b"\x00")
            reply = self.send_and_wait_for_reply(message)
            logger.debug("Label packet: {}".format(reply))
            if reply != None:
                try:
                    label = reply[4:20].decode("utf-8").strip()
                except:
                    logger.error(
                        "Could not extract label from message {}.".format(reply)
                    )
                    label = None
                if label != None:
                    if ord(label[0]) == 0 or len(label) == 0:
                        label = None
                self.update_partition_label(partition_number=i * 2 + 1, label=label)
                try:
                    label = reply[20:36].decode("utf-8").strip()
                except:
                    logger.error(
                        "Could not extract label from message {}.".format(reply)
                    )
                    label = None
                if label != None:
                    if ord(label[0]) == 0 or len(label) == 0:
                        label = None
                self.update_partition_label(partition_number=i * 2 + 2, label=label)
        logger.info("Read partition labels.")

    def read_output_labels(self):
        logger.info("Reading output labels...")
        register_dict = getattr(self.registermap, "get" + "outputLabel" + "Register")()
        for i in range(0, int(self.outputs / 2)):
            self.wait_for_message(timeout=0.1, process_message=True)
            message = bytearray(register_dict[i * 2 + 1]["Send"], encoding="latin")
            message = message.ljust(36, b"\x00")
            reply = self.send_and_wait_for_reply(message)
            logger.debug("Label packet: {}".format(reply))
            if reply != None:
                try:
                    label = reply[4:20].decode("utf-8").strip()
                except:
                    logger.error(
                        "Could not extract label from message {}.".format(reply)
                    )
                    label = None
                if label != None:
                    if type(label) != "str":
                        label = None
                    elif len(label) == 0:
                        label = None
                self.update_output_label(output_number=i * 2 + 1, label=label)
                try:
                    label = reply[20:36].decode("utf-8").strip()
                except:
                    logger.error(
                        "Could not extract label from message {}.".format(reply)
                    )
                    label = None
                if label != None:
                    if type(label) != "str":
                        label = None
                    elif len(label) == 0:
                        label = None
                self.update_output_label(output_number=i * 2 + 2, label=label)
        logger.info("Read output labels.")

    def read_labels(self):
        logger.info("Reading all labels...")
        self.read_zone_labels()
        self.read_user_labels()
        self.read_partition_labels()
        self.read_output_labels()
        logger.info("Read all labels.")

    def set_output(self, output_number, on=True, stop_pulse=True):
        if on:
            logger.info(
                "Activating output {}...".format(
                    self.output_data[output_number]["label"]
                )
            )
        else:
            logger.info(
                "Deactivating output {}...".format(
                    self.output_data[output_number]["label"]
                )
            )
        self.control_output(output_number, on)
        self.update_output_property(output_number, property="on", flag=on)
        if stop_pulse:
            self.update_output_property(output_number, property="pulse", flag=False)

    def set_output_pulse(self, output_number, pulse=True, stop_pulse=True):
        if pulse:
            logger.info(
                "Activating pulse on output {}...".format(
                    self.output_data[output_number]["label"]
                )
            )
            self.update_output_property(output_number, property="pulse", flag=True)
        else:
            logger.info(
                "Deactivating pulse on output {}...".format(
                    self.output_data[output_number]["label"]
                )
            )
            self.set_output(output_number=output_number, on=False, stop_pulse=True)

    def pulse_outputs(self):
        for i in range(1, self.outputs + 1):
            if self.output_data[i]["pulse"]:
                on = self.output_data[i]["on"]
                print(on)
                self.set_output(output_number=i, on=(not on), stop_pulse=False)

    def control_output(self, output_number, on):
        mapping_dict = self.registermap.getcontrolOutputRegister()
        if on:
            state = "ON"
        else:
            state = "OFF"
        message = bytearray(mapping_dict[output_number][state], encoding="latin")
        message = message.ljust(36, b"\x00")
        self.send_message(message)

    def control_alarm(self, partition_number, state):
        if not state in ["ARM", "DISARM", "SLEEP", "STAY"]:
            logger.error("Invalid control_alarm state {}.".format(state))
        if not partition_number in [1, 2]:
            logger.error(
                "Invalid partition number {:d} for control_alarm.".format(
                    partition_number
                )
            )
        logger.info(
            "Setting partition {} to {}.".format(
                self.partition_data[partition_number]["label"], state
            )
        )
        mapping_dict = self.registermap.getcontrolAlarmRegister()
        message = bytearray(mapping_dict[partition_number][state], encoding="latin")
        message = message.ljust(36, b"\x00")
        self.send_message(message)

    def clear_on_disarm(self):
        # clear siren
        self.update_bell(False)
        # clear zone bypass
        for i in range(1, self.zones + 1):
            self.update_zone_property(i, property="bypass", flag=False)

    def bypass_zone(self, zone_number):
        """Sends bypass command for zone."""
        if zone_number < 1 or zone_number > self.zones:
            logger.error("Invalid zone number {:d}".format(zone_number))
            return
        logger.info(
            "Sending bypass command for zone {}.".format(
                self.zone_data[zone_number]["label"]
            )
        )
        message = bytearray(b"\x40\x00\x10")
        message.append(zone_number - 1)
        message += b"\x04"
        message = message.ljust(36, b"\x00")
        self.send_message(message)
