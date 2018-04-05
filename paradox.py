#!/usr/bin/env python
import logging

logger = logging.getLogger('paradox_mqtt').getChild(__name__)
from time import sleep, time
from datetime import datetime, timedelta
from bits import test_bit
from math import floor
import paho.mqtt.client as mqtt

from config_defaults import *
from config import *


class Paradox():

    def __init__(self,
                 connection,
                 encrypted=0,
                 alarmeventmap="ParadoxMG5050",
                 alarmregmap="ParadoxMG5050"):
        """Intialise Paradox"""
        logger.debug("Initialising Paradox class...")
        #mqtt client
        self.mqtt = mqtt.Client('paradox_mqtt')
        self.mqtt.on_message = self.mqtt_message

        #Connection
        self.connection = connection

        #My event map and reg maps
        self.alarmeventmap = alarmeventmap
        self.alarmregmap = alarmregmap

        # Low Nibble Data
        self.neware_connected = False
        self.software_connected = False
        self.alarm = False
        self.event_reporting = False

        #Votage Info
        self.vdc = None
        self.dc = None
        self.battery = None

        #Bell on?
        self.bell = False

        #Partitions
        self.partition_data = []
        for i in range(0, 2 + 1):  #dummy partition 0
            partition = {}
            partition['number'] = i
            partition['label'] = 'Partition {:d}'.format(i)
            partition['machine_label'] = partition['label'].lower().replace(' ',
                                                                            '_')
            partition['alarm'] = False
            partition['arm'] = None
            partition['arm_full'] = None
            partition['arm_sleep'] = None
            partition['arm_stay'] = None
            self.partition_data.append(partition)

        #Bell on?
        self.bell = False

        #Zones & Zone Data
        self.zones = ZONES

        self.zone_data = []
        for i in range(0, self.zones + 1):  #implies a dummy zone 0
            zone = {}
            zone['number'] = i
            zone['label'] = 'Zone {:d}'.format(i + 1)
            zone['machine_label'] = zone['label'].lower().replace(' ', '_')
            zone['open'] = None
            zone['bypass'] = False
            zone['alarm'] = False
            zone['fire_alarm'] = False
            zone['shutdown'] = False
            zone['tamper'] = False
            zone['low_battery'] = False
            zone['supervision_trouble'] = False
            self.zone_data.append(zone)

        #Users
        self.users = USERS
        self.user_data = []
        for i in range(0, self.users + 1):  #implies dummy user 0
            user = {}
            user['number'] = i
            user['label'] = 'User {:d}'.format(i + 1)
            user['machine_label'] = user['label'].lower().replace(' ', '_')
            self.user_data.append(user)

        #Outputs
        self.outputs = OUTPUTS
        self.output_data = []
        for i in range(0, self.outputs + 1):  #implies dummy output 0
            output = {}
            output['number'] = i
            output['label'] = 'Output {:d}'.format(i + 1)
            output['machine_label'] = output['label'].lower().replace(' ', '_')
            output['on'] = False
            output['pulse'] = False
            output['supervision_trouble'] = False
            output['tamper'] = False
            self.output_data.append(output)

        #event map
        mod = __import__(
            "paradox_map", fromlist=[self.alarmeventmap + "EventMap"])
        self.eventmap = getattr(mod, self.alarmeventmap + "EventMap")

        #registers
        mod = __import__(
            "paradox_map", fromlist=[self.alarmregmap + "Registers"])
        self.registermap = getattr(mod, self.alarmregmap + "Registers")

        logger.debug("Initialised Paradox class.")

    def mqtt_connect(self,
                     host='localhost',
                     port=1883,
                     username='',
                     password='',
                     keepalive=60,
                     bind_address=""):
        logger.info("Connecting to mqtt.")

        if len(username) > 0 and len(password) > 0:
            self.mqtt.set_username_pw(username=username, password=password)
        self.mqtt.connect(host, port, keepalive, bind_address)
        self.mqtt.loop_start()
        self.mqtt.subscribe(
            "{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_CONTROL_TOPIC, "#"))
        logger.info("Connected to mqtt.")

    def mqtt_message_ON_OFF(self, message):
        if message in ['ON', 'OFF']:
            return message == 'ON'
        else:
            return None

    def mqtt_message(self, client, userdata, message):
        logger.info("message topic={}, message={}".format(
            message.topic, str(message.payload.decode("utf-8"))))
        topics = message.topic.split("/")
        if len(topics) < 2:
            logger.error("Invalid mqtt message.  No details topic {}.".format(
                message.topic))
            return
        if topics[2] == MQTT_ZONE_TOPIC:  #Zone command
            if len(topics) < 5:
                logger.error("Invalid mqtt message.  Not enough topics in {}.".
                             format(message.topic))
                return
            machine_label = topics[3]
            matching_zones = [
                z for z in self.zone_data if z['machine_label'] == machine_label
            ]
            if len(matching_zones) == 0:
                logger.error("Invalid zone label provided in topic {}.".format(
                    message.topic))
                return
            if topics[4] == "bypass":
                flag = self.mqtt_message_ON_OFF(
                    str(message.payload.decode("utf-8")))
                if flag == None:
                    logger.error("Invalid message body. Should be ON/OFF. {}".
                                 format(str(message.payload.decode("utf-8"))))
                    return
                for z in matching_zones:
                    self.bypass_zone(zone_number=z['number'])
            else:
                logger.error("Invalid zone property set in topic {}.".format(
                    message.topic))

        elif topics[2] == MQTT_PARTITION_TOPIC:  #Partition command
            if len(topics) < 5:
                logger.error("Invalid mqtt message.  Not enough topics in {}.".
                             format(message.topic))
                return
            machine_label = topics[3]
            matching_partitions = [
                z for z in self.partition_data
                if z['machine_label'] == machine_label
            ]
            if len(matching_partitions) == 0:
                logger.error("Invalid partition label provided in topic {}.".
                             format(message.topic))
                return
            if topics[4] in ["arm", "arm_full", "arm_stay", "arm_sleep"]:
                flag = self.mqtt_message_ON_OFF(
                    str(message.payload.decode("utf-8")))
                if flag == None:
                    logger.error("Invalid message body. Should be ON/OFF. {}".
                                 format(str(message.payload.decode("utf-8"))))
                    return
                for p in matching_partitions:
                    if flag:
                        if topics[4] in ['arm', 'arm_full']:
                            self.control_alarm(
                                partition_number=p['number'], state='ARM')
                        elif topics[4] == 'arm_stay':
                            self.control_alarm(
                                partition_number=p['number'], state='STAY')
                        elif topics[4] == 'arm_sleep':
                            self.control_alarm(
                                partition_number=p['number'], state='SLEEP')
                    else:
                        self.control_alarm(
                            partition_number=p['number'], state='DISARM')
            else:
                logger.error("Invalid partition property set in topic {}.".
                             format(message.topic))
        elif topics[2] == MQTT_OUTPUT_TOPIC:  #Output command
            if len(topics) < 5:
                logger.error("Invalid mqtt message.  Not enough topics in {}.".
                             format(message.topic))
                return
            machine_label = topics[3]
            matching_outputs = [
                z for z in self.output_data
                if z['machine_label'] == machine_label
            ]
            if len(matching_outputs) == 0:
                logger.error("Invalid output label provided in topic {}.".
                             format(message.topic))
                return
            if topics[4] in ["on", "pulse"]:
                flag = self.mqtt_message_ON_OFF(
                    str(message.payload.decode("utf-8")))
                if flag == None:
                    logger.error("Invalid message body. Should be ON/OFF. {}".
                                 format(str(message.payload.decode("utf-8"))))
                    return
                for o in matching_outputs:
                    if topics[4] == "pulse":
                        self.set_output_pulse(
                            output_number=o['number'], pulse=flag)
                    else:
                        self.set_output(output_number=o['number'], on=flag)
            else:
                logger.error("Invalid output property set in topic {}.".format(
                    message.topic))

    def main_loop(self):
        """Wait for and then process messages."""
        keep_alive_time = datetime(1900, 1, 1)
        label_time = datetime(1900, 1, 1)
        mqtt_publish_all_time = datetime(1900, 1, 1)
        output_pulse_time = datetime(1900, 1, 1)
        while True:
            if self.connection.in_waiting() >= 37:
                message = self.connection.read()
                logger.debug("Received message: {} ".format(message))
                self.process_message(message)
            sleep(0.1)
            if not self.software_connected:
                self.connect_software()
            if datetime.now() > mqtt_publish_all_time + timedelta(
                    seconds=READ_LABELS_SECONDS):
                self.read_labels()
                label_time = datetime.now()
            if datetime.now() > keep_alive_time + timedelta(
                    seconds=KEEP_ALIVE_SECONDS):
                self.keep_alive()
                keep_alive_time = datetime.now()
            if datetime.now() > mqtt_publish_all_time + timedelta(
                    seconds=MQTT_PUBLISH_ALL_SECONDS):
                self.publish_all()
                mqtt_publish_all_time = datetime.now()
            if datetime.now() > output_pulse_time + timedelta(
                    seconds=OUTPUT_PULSE_SECONDS):
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

    def boolean_ON_OFF(self, b):
        if b:
            return "ON"
        else:
            return "OFF"

    def timestamp_str(self):
        return "{}".format(datetime.now().isoformat())

    def publish_all(self):
        self.publish_neware_connected()
        self.publish_software_connected()
        self.publish_alarm()
        self.publish_voltages()
        self.publish_bell()
        self.publish_partitions()
        self.publish_outputs()
        self.publish_zones()

    def publish_bell(self):
        if self.bell != None:
            topic = "{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_STATES_TOPIC,
                                      'bell')
            self.mqtt.publish(topic, self.boolean_ON_OFF(self.bell))

    def publish_neware_connected(self):
        if self.neware_connected != None:
            topic = "{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_STATES_TOPIC,
                                      'neware_connected')
            self.mqtt.publish(topic, self.boolean_ON_OFF(self.neware_connected))

    def publish_software_connected(self):
        if self.software_connected != None:
            topic = "{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_STATES_TOPIC,
                                      'software_connected')
            self.mqtt.publish(topic,
                              self.boolean_ON_OFF(self.software_connected))

    def publish_alarm(self):
        if self.alarm != None:
            topic = "{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_STATES_TOPIC,
                                      'alarm')
            self.mqtt.publish(topic, self.boolean_ON_OFF(self.alarm))

    def publish_voltages(self):
        if self.vdc != None:
            topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_STATES_TOPIC,
                                         'voltages', 'vdc')
            self.mqtt.publish(topic, "{:f}".format(self.vdc))
        if self.dc != None:
            topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_STATES_TOPIC,
                                         'voltages', 'dc')
            self.mqtt.publish(topic, "{:f}".format(self.dc))
        if self.battery != None:
            topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_STATES_TOPIC,
                                         'voltages', 'battery')
            self.mqtt.publish(topic, "{:f}".format(self.battery))

    def publish_partitions(self):
        for i in range(1, 2 + 1):
            self.publish_partition_property(i, 'alarm')
            self.publish_partition_property(i, 'arm')
            self.publish_partition_property(i, 'arm_full')
            self.publish_partition_property(i, 'arm_sleep')
            self.publish_partition_property(i, 'arm_stay')

    def publish_outputs(self):
        for i in range(1, self.outputs + 1):
            self.publish_output_property(i, 'on')
            self.publish_output_property(i, 'pulse')
            self.publish_output_property(i, 'tamper')
            self.publish_output_property(i, 'supervision_trouble')

    def publish_zones(self):
        for i in range(1, self.zones + 1):
            self.publish_zone_property(i, 'open')
            self.publish_zone_property(i, 'bypass')
            self.publish_zone_property(i, 'alarm')
            self.publish_zone_property(i, 'fire_alarm')
            self.publish_zone_property(i, 'shutdown')
            self.publish_zone_property(i, 'tamper')
            self.publish_zone_property(i, 'low_battery')
            self.publish_zone_property(i, 'supervision_trouble')

    def update_bell(self, bell):
        if bell != self.bell:
            self.bell = bell
            if bell:
                logger.warning("Bell on!")
            else:
                logger.warning("Bell off.")
            self.publish_bell()

    def update_voltages(self, vdc, dc, battery):
        self.vdc = vdc
        self.dc = dc
        self.battery = battery
        logger.debug("vdc: {:.2f} | dc: {:.2f} | battery: {:.2f}".format(
            vdc, dc, battery))

    def publish_partition_event(self, partition_number, property):
        if self.partition_data[partition_number][property] != None:
            partition_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_PARTITION_TOPIC,
                'partition')
            label_topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC,
                                               MQTT_EVENTS_TOPIC,
                                               MQTT_PARTITION_TOPIC, 'label')
            property_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_PARTITION_TOPIC,
                'property')
            state_topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC,
                                               MQTT_EVENTS_TOPIC,
                                               MQTT_PARTITION_TOPIC, 'state')
            timestamp_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_PARTITION_TOPIC,
                'timestamp')
            self.mqtt.publish(
                partition_topic,
                self.partition_data[partition_number]['machine_label'])
            self.mqtt.publish(label_topic,
                              self.partition_data[partition_number]['label'])
            self.mqtt.publish(property_topic, property)
            self.mqtt.publish(
                state_topic,
                self.boolean_ON_OFF(
                    self.partition_data[partition_number][property]))
            self.mqtt.publish(timestamp_topic, self.timestamp_str())

    def publish_partition_property(self, partition_number, property="arm"):
        if self.partition_data[partition_number][property] != None:
            topic = "{}/{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_STATES_TOPIC, MQTT_PARTITION_TOPIC,
                self.partition_data[partition_number]['machine_label'],
                property)
            self.mqtt.publish(
                topic,
                self.boolean_ON_OFF(
                    self.partition_data[partition_number][property]))

    def update_partition_property(self,
                                  partition_number,
                                  property="arm",
                                  flag=None):
        if partition_number > 2 or partition_number < 0:
            logger.error(
                "Invalid partition_number {:d}".format(partition_number))
            return
        if flag != None:
            if self.partition_data[partition_number][
                    property] == None or self.partition_data[partition_number][
                        property] != flag:
                label = self.partition_data[partition_number]['label']
                self.partition_data[partition_number][property] = flag
                if flag:
                    logger.info('Partition {:d},"{}", {}.'.format(
                        partition_number, label, property))
                else:
                    logger.info('Partition {:d},"{}", Not {}.'.format(
                        partition_number, label, property))
                self.publish_partition_property(partition_number, property)
                self.publish_partition_event(partition_number, property)
                if property == 'arm' and flag == False:
                    self.clear_on_disarm()

    def publish_output_event(self, output_number, property):
        if self.output_data[output_number][property] != None:
            output_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_OUTPUT_TOPIC, 'output')
            label_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_OUTPUT_TOPIC, 'label')
            property_topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC,
                                                  MQTT_EVENTS_TOPIC,
                                                  MQTT_OUTPUT_TOPIC, 'property')
            state_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_OUTPUT_TOPIC, 'state')
            timestamp_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_OUTPUT_TOPIC,
                'timestamp')
            self.mqtt.publish(output_topic,
                              self.output_data[output_number]['machine_label'])
            self.mqtt.publish(label_topic,
                              self.output_data[output_number]['label'])
            self.mqtt.publish(property_topic, property)
            self.mqtt.publish(
                state_topic,
                self.boolean_ON_OFF(self.output_data[output_number][property]))
            self.mqtt.publish(timestamp_topic, self.timestamp_str())

    def publish_output_property(self, output_number, property=None):
        if self.output_data[output_number][property] != None:
            topic = "{}/{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_STATES_TOPIC, MQTT_OUTPUT_TOPIC,
                self.output_data[output_number]['machine_label'], property)
            self.mqtt.publish(
                topic,
                self.boolean_ON_OFF(self.output_data[output_number][property]))

    def update_output_property(self, output_number, property=None, flag=None):
        if output_number > self.outputs or output_number < 1:
            logger.error("Invalid output_number {:d}".format(output_number))
            return
        if flag != None:
            if self.output_data[output_number][
                    property] == None or self.output_data[output_number][
                        property] != flag:
                label = self.output_data[output_number]['label']
                self.output_data[output_number][property] = flag
                if flag:
                    logger.info('Output {:d},"{}", {}.'.format(output_number,
                                                               label, property))
                else:
                    logger.info('Output {:d},"{}", Not {}.'.format(
                        output_number, label, property))
                self.publish_output_property(output_number, property)
                self.publish_output_event(output_number, property)

    def update_output_label(self, output_number, label=None):
        if output_number > self.outputs or output_number < 1:
            logger.error("Invalid output_number {:d}".format(output_number))
            return
        if label != None:
            if self.output_data[output_number][
                    'label'] == None or self.output_data[output_number][
                        'label'] != label:
                self.output_data[output_number]['label'] = label
                self.output_data[output_number]['machine_label'] = label.lower(
                ).replace(' ', '_')
                logger.info('Output {:d} label set to "{}".'.format(
                    output_number, label))
            self.eventmap.setoutputLabel(
                output_number, self.output_data[output_number]['machine_label'])

    def publish_zone_event(self, zone_number, property):
        if self.zone_data[zone_number][property] != None:
            zone_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_ZONE_TOPIC, 'zone')
            label_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_ZONE_TOPIC, 'label')
            property_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_ZONE_TOPIC, 'property')
            state_topic = "{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_ZONE_TOPIC, 'state')
            timestamp_topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC,
                                                   MQTT_EVENTS_TOPIC,
                                                   MQTT_ZONE_TOPIC, 'timestamp')
            self.mqtt.publish(zone_topic,
                              self.zone_data[zone_number]['machine_label'])
            self.mqtt.publish(label_topic, self.zone_data[zone_number]['label'])
            self.mqtt.publish(property_topic, property)
            self.mqtt.publish(
                state_topic,
                self.boolean_ON_OFF(self.zone_data[zone_number][property]))
            self.mqtt.publish(timestamp_topic, self.timestamp_str())

    def publish_zone_property(self, zone_number, property="open"):
        if self.zone_data[zone_number][property] != None:
            topic = "{}/{}/{}/{}/{}".format(
                MQTT_BASE_TOPIC, MQTT_STATES_TOPIC, MQTT_ZONE_TOPIC,
                self.zone_data[zone_number]['machine_label'], property)
            self.mqtt.publish(
                topic,
                self.boolean_ON_OFF(self.zone_data[zone_number][property]))

    def update_zone_property(self, zone_number, property="open", flag=None):
        if zone_number > self.zones or zone_number < 1:
            logger.error("Invalid zone_number {:d}".format(zone_number))
            return
        if flag != None:
            if self.zone_data[zone_number][property] == None or self.zone_data[
                    zone_number][property] != flag:
                label = self.zone_data[zone_number]['label']
                self.zone_data[zone_number][property] = flag
                if flag:
                    logger.info('Zone {:d},"{}", {}.'.format(zone_number, label,
                                                             property))
                else:
                    logger.info('Zone {:d},"{}", Not {}.'.format(
                        zone_number, label, property))
                self.publish_zone_property(zone_number, property)
                self.publish_zone_event(zone_number, property)

    def toggle_zone_property(self, zone_number, property="open"):
        if zone_number > self.zones or zone_number < 1:
            logger.error("Invalid zone_number {:d}".format(zone_number))
            return
        self.update_zone_property(
            zone_number=zone_number,
            property=property,
            flag=not self.zone_data[zone_number][property])

    def update_zone_label(self, zone_number, label=None):
        if zone_number > self.zones or zone_number < 1:
            logger.error("Invalid zone_number {:d}".format(zone_number))
            return
        if label != None:
            if self.zone_data[zone_number]['label'] == None or self.zone_data[
                    zone_number]['label'] != label:
                self.zone_data[zone_number]['label'] = label
                self.zone_data[zone_number]['machine_label'] = label.lower(
                ).replace(' ', '_')
                logger.info(
                    'Zone {:d} label set to "{}".'.format(zone_number, label))
            self.eventmap.setzoneLabel(
                zone_number, self.zone_data[zone_number]['machine_label'])

    def update_label(self,
                     partition_number=0,
                     subevent_number=0,
                     label_type=0,
                     label=None):
        if label == None:
            return
        if label_type == 0:  #Zone labels
            self.update_zone_label(zone_number=subevent_number, label=label)
        elif label_type == 1:  #User labels
            self.update_user_label(user_number=subevent_number, label=label)
        elif label_type == 2:  #Partition labels
            self.update_partition_label(
                partition_number=partition_number, label=label)
        elif label_type == 3:  #Output labels
            if subevent_number > 0 and subevent_number <= self.outputs:
                self.update_output_label(
                    output_number=subevent_number, label=label)
        else:
            logger.error("Can't process label_type={:d} ".format(label_type))

    def update_user_label(self, user_number, label=None):
        if user_number > self.users or user_number < 1:
            logger.error("Invalid user_number {:d}".format(user_number))
            return
        if label != None:
            if self.user_data[user_number]['label'] == None or self.user_data[
                    user_number]['label'] != label:
                self.user_data[user_number]['label'] = label
                self.user_data[user_number]['machine_label'] = label.lower(
                ).replace(' ', '_')
                logger.info(
                    'User {:d} label set to "{}".'.format(user_number, label))
            self.eventmap.setuserLabel(
                user_number, self.user_data[user_number]['machine_label'])

    def update_partition_label(self, partition_number, label=None):
        if partition_number > 2 or partition_number < 1:
            logger.error(
                "Invalid partition_number {:d}".format(partition_number))
            return
        if label != None:
            if self.partition_data[partition_number][
                    'label'] == None or self.partition_data[partition_number][
                        'label'] != label:
                self.partition_data[partition_number]['label'] = label
                self.partition_data[partition_number][
                    'machine_label'] = label.lower().replace(' ', '_')
                logger.info('Partition {:d} label set to "{}".'.format(
                    partition_number, label))

    def process_low_nibble(self, low_nibble):
        neware_connected = (test_bit(low_nibble, 0) == True)
        software_connected = (test_bit(low_nibble, 1) == True)
        alarm = (test_bit(low_nibble, 2) == True)
        event_reporting = (test_bit(low_nibble, 3) == True)

        if self.neware_connected != neware_connected:
            self.neware_connected = neware_connected
            if self.neware_connected:
                logger.info("NEWare connected.")
            else:
                logger.info("NEWare disconnected.")

        if self.software_connected != software_connected:
            self.software_connected = software_connected
            if self.software_connected:
                logger.info("Software connected.")
            else:
                logger.info("Software disconnected.")

        if self.alarm != alarm:
            self.alarm = alarm
            if self.alarm:
                logger.warning("Alarm activated!")
            else:
                logger.info("Alarm deactivated.")
                self.update_partition_property(
                    partition_number=1, property='alarm', flag=False)
                self.update_partition_property(
                    partition_number=2, property='alarm', flag=False)

        if self.event_reporting != event_reporting:
            self.event_reporting = event_reporting
            if self.event_reporting:
                logger.info("Event reporting activated.")
            else:
                logger.info("Event reporting disabled.")

        logger.debug("NEWare connected: {0}".format(neware_connected))
        logger.debug("Software connected: {0}".format(software_connected))
        logger.debug("Alarm: {0}".format(alarm))
        logger.debug("Event reporting: {0}".format(event_reporting))

    def process_keep_alive_response(self, message):
        logger.debug("Processing Keep Alive Response...")
        if message[2] == 128:  #keep alive seq response
            seq = message[3]
            if seq == 0:
                #Alarm Time
                self.datetime = datetime(message[9] * 100 + message[10],
                                         message[11], message[12], message[13],
                                         message[14])
                logger.debug(
                    "Alarm time: {:%Y-%m-%d %H:%M}".format(self.datetime))
                #Voltage
                self.update_voltages(
                    vdc=round(message[15] * (20.3 - 1.4) / 255.0 + 1.4, 1),
                    dc=round(message[16] * 22.8 / 255.0, 1),
                    battery=round(message[17] * 22.8 / 255.0, 1))
                #Zone statuses
                for i in range(0, 4):
                    byte = message[19 + i]
                    for j in range(0, 8):
                        open = (byte >> j) & 0x01
                        zone_number = i * 8 + j + 1
                        self.update_zone_property(
                            zone_number, property='open', flag=open)
            elif seq == 1:
                #Parition Status
                for i in range(0, 2):
                    partition_number = i + 1
                    #logger.info('Partition {:d} status bytes'.format(partition_number))
                    #for j in range(17,21):
                    #    logger.info('Byte {:d}: {:d}'.format(j,message[j+4*i]))
                    #    logger.info('Byte {:d}: Bits: {:08b}'.format(j,message[j+4*i]))
                    arm = test_bit(message[17 + i * 4], 0)
                    arm_sleep = test_bit(message[17 + i * 4], 1)
                    arm_stay = test_bit(message[17 + i * 4], 2)
                    arm_full = arm and not (arm_stay or arm_sleep)
                    self.update_partition_property(
                        partition_number=partition_number,
                        property='arm',
                        flag=arm)
                    self.update_partition_property(
                        partition_number=partition_number,
                        property='arm_full',
                        flag=arm_full)
                    self.update_partition_property(
                        partition_number=partition_number,
                        property='arm_sleep',
                        flag=arm_sleep)
                    self.update_partition_property(
                        partition_number=partition_number,
                        property='arm_stay',
                        flag=arm_stay)
            elif seq == 2:
                #Zone Bypass Status
                for i in range(0, self.zones - 1):
                    bypass = test_bit(message[4 + i], 3)
                    self.update_zone_property(
                        zone_number=i + 1, property='bypass', flag=bypass)
            elif seq > 2 and seq < 7:
                pass  #What do these do?
            else:
                logger.error("Invalid sequence {:d} on keep alive.".format(seq))
        elif message[2] == 31 and message[3] == 224:
            logger.debug("Final keep alive response.")
        else:
            logger.error(
                "Can't process this keep alive response:{}".format(message))

    def publish_raw_event(self, partition_number, event_number,
                          subevent_number):
        event, subevent = self.eventmap.getEventDescription(event_number,
                                                            subevent_number)
        partition = self.partition_data[partition_number]['machine_label']
        partition_topic = "{}/{}/{}/{}".format(
            MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_RAW_TOPIC,
            'partition_number')
        event_topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC,
                                           MQTT_RAW_TOPIC, 'event_number')
        subevent_topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC,
                                              MQTT_EVENTS_TOPIC, MQTT_RAW_TOPIC,
                                              'subevent_number')
        self.mqtt.publish(partition_topic, partition_number)
        self.mqtt.publish(event_topic, event_number)
        self.mqtt.publish(subevent_topic, subevent_number)
        partition_topic = "{}/{}/{}/{}".format(
            MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_RAW_TOPIC, 'partition')
        event_topic = "{}/{}/{}/{}".format(MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC,
                                           MQTT_RAW_TOPIC, 'event')
        subevent_topic = "{}/{}/{}/{}".format(
            MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_RAW_TOPIC, 'subevent')
        self.mqtt.publish(partition_topic, partition)
        self.mqtt.publish(event_topic, event)
        self.mqtt.publish(subevent_topic, subevent)
        timestamp_topic = "{}/{}/{}/{}".format(
            MQTT_BASE_TOPIC, MQTT_EVENTS_TOPIC, MQTT_RAW_TOPIC, 'timestamp')
        self.mqtt.publish(timestamp_topic, self.timestamp_str())

    def process_live_event_command(self, message):
        logger.debug("Processing live event command...")
        event_number = message[7]
        subevent_number = message[8]
        partition_number = message[9] + 1
        event_timestamp = datetime(message[1] * 100 + message[2], message[3],
                                   message[4], message[5], message[6])
        module_serial = int(message[10]) * 10 ^ 8 + int(
            message[11]) * 10 ^ 4 + int(message[12]) * 10 ^ 2 + int(
                message[13]) * 10 ^ 0
        label_type = message[14]
        logger.debug(
            "Alarm timestamp: {:%Y-%m-%d %H:%M}".format(event_timestamp))
        logger.debug("Partition number: {:d}".format(partition_number))
        logger.debug("Module serial: {:d}".format(module_serial))
        logger.debug("Label type: {:d}".format(label_type))
        logger.debug("event_number: {:d}, subevent_number {:d}".format(
            event_number, subevent_number))
        label = message[15:31].decode("utf-8").strip()
        logger.debug(
            'event_number: {:d}, subevent_number: {:d}, partition_number: {:d}, label_type: {:d}, label: {}'.
            format(event_number, subevent_number, partition_number, label_type,
                   label))
        event, subevent = self.eventmap.getEventDescription(event_number,
                                                            subevent_number)
        logger.info("partition_number: {:d}, event: {}, subevent {}".format(
            partition_number, event, subevent))
        self.publish_raw_event(partition_number, event_number, subevent_number)

        if ord(label[0]) == 0 or len(label) == 0:
            label = None
        else:
            self.update_label(
                partition_number=partition_number,
                subevent_number=subevent_number,
                label_type=label_type,
                label=label)
        logger.debug(
            "event: {}, subevent: {}, label: {}".format(event, subevent, label))
        if event_number in (0, 1):  #Zone open
            self.update_zone_property(
                subevent_number, property='open', flag=event_number == 1)
        elif event_number == 2:  #Partition status
            if subevent_number in [2, 3, 4, 5, 6]:  #alarm subevents
                self.update_partition_property(
                    partition_number=partition_number,
                    property='alarm',
                    flag=True)
            elif subevent_number == 7:  #Alarm stopped
                self.update_partition_property(
                    partition_number=partition_number,
                    property='alarm',
                    flag=False)
            elif subevent_number == 11:  #Disarm partion
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm',
                    flag=False)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_full',
                    flag=False)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_sleep',
                    flag=False)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_stay',
                    flag=False)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='alarm',
                    flag=False)
                self.clear_on_disarm()
            elif subevent_number == 12:  #Arm partion
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm',
                    flag=True)
        elif event_number == 3:  #Bell status
            if subevent_number in (0, 1):
                self.update_bell(subevent_number == 1)
            else:
                pass  #we don't do anything with other bell events
        elif event_number == 6:  #Non-reportable events
            if subevent_number == 3:  #Arm in stay mode
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm',
                    flag=True)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_full',
                    flag=False)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_sleep',
                    flag=False)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_stay',
                    flag=True)
            elif subevent_number == 4:  #Arm in sleep mode
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm',
                    flag=True)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_full',
                    flag=False)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_sleep',
                    flag=True)
                self.update_partition_property(
                    partition_number=partition_number,
                    property='arm_stay',
                    flag=False)
        elif event_number == 35:  #Zone bypass
            self.toggle_zone_property(subevent_number, property='bypass')
        elif event_number in (36, 38):  #Zone alarm
            self.update_zone_property(
                subevent_number, property='alarm', flag=event_number == 36)
        elif event_number in (37, 39):  #Zone fire alarm
            self.update_zone_property(
                subevent_number, property='fire_alarm', flag=event_number == 37)
        elif event_number == 41:  #Zone shutdown?
            self.update_zone_property(
                subevent_number, property='shutdown', flag=True)
        elif event_number in (42, 43):  #Zone tamper
            self.update_zone_property(
                subevent_number, property='tamper', flag=event_number == 42)
        elif event_number in (49, 50):  #Zone battery
            self.update_zone_property(
                subevent_number,
                property='low_battery',
                flag=event_number == 49)
        elif event_number in (51, 52):  #Zone supervision_trouble
            self.update_zone_property(
                subevent_number,
                property='supervision_trouble',
                flag=event_number == 51)
        elif event_number in (53, 54):  #Wireless module supervision_trouble
            if subevent_number > 0 and subevent_number <= self.outputs:
                self.update_output_property(
                    subevent_number,
                    property='supervision_trouble',
                    flag=event_number == 53)
        elif event_number in (55, 56):  #Wireless module tamper trouble
            if subevent_number > 0 and subevent_number <= self.outputs:
                self.update_output_property(
                    subevent_number, property='tamper', flag=event_number == 55)
        else:
            logger.debug("Nothing special to do for this event.")

    def process_message(self, message):
        """Process message."""
        logger.debug("Processing message...")
        logger.debug("message[0]= {}".format(message[0]))
        high_nibble = message[0] >> 4
        low_nibble = message[0] & 0x0F
        logger.debug("High Nibble: {:d}".format(high_nibble))
        logger.debug("Low Nibble: {:d}".format(low_nibble))

        valid_checksum = self.verify_checksum(message)
        if not valid_checksum:
            logger.warning(
                "Message checksum fails.  Skipping message and flushing input buffer."
            )
            self.connection.reset_input_buffer()
            return
        if high_nibble != 15:
            self.process_low_nibble(low_nibble)
        if high_nibble == 4:  #Bypass command response
            zone_number = message[3] + 1
            logger.debug(
                "Bypass command received by panel for zone_number={:d}".format(
                    zone_number))
            self.toggle_zone_property(
                zone_number=zone_number, property='bypass')
        elif high_nibble == 5:  #Keep Alive Response
            self.process_keep_alive_response(message)
        elif high_nibble == 14:  #Live Event command, not sure about 15
            self.process_live_event_command(message)
        else:
            logger.error("Could not process message: {} (high_nibble={:d})".
                         format(message, high_nibble))
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
                "Message not 36 byes.  Cannot calculate checksum. Message: {}".
                format(message))
            return None

    def verify_checksum(self, message):
        if len(message) != 37:
            logger.debug("Message not 37 byes.  Message: {}".format(message))
            return False
        checksum = self.calc_checksum(message[:36])
        return checksum == message[36]

    def connect_software(self):
        """Software connection to alarm."""
        logger.info("Software connecting to alarm.")
        message = b'\x72\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        reply = self.send_and_process_reply(message)

        message = b'\x50\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        reply = self.send_and_process_reply(message)

        message = b'\x5f\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        reply = self.send_and_process_reply(message)

        message = reply
        #message = reply[0:10]+reply[8:10]+b'\x19\x00\x00'+reply[15:23] +b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00'
        reply = self.send_and_process_reply(message)

        message = b'\x50\x00\x1f\xe0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x4f'
        reply = self.send_and_process_reply(message)

        message = b'\x50\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        reply = self.send_and_process_reply(message)

        message = b'\x50\x00\x0e\x52\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        reply = self.send_and_process_reply(message)

        self.software_connected = True
        self.connection.reset_input_buffer()
        return True

    def set_time(self):
        message = b'\x30\x00\x00\x00'
        now = datetime.now()
        message += bytes([
            floor(now.year / 100), now.year - floor(now.year / 100) * 100,
            now.month, now.day, now.hour, now.minute, now.second
        ])
        message = message.ljust(36, b'\x00')
        self.send_message(message)

    def keep_alive(self):
        logger.debug("Sending keep alive messages...")
        base_message = b'\x50\x00\x80'
        for i in range(0, 7):
            message = (base_message + bytes([i])).ljust(36, b'\x00')
            self.wait_for_message(timeout=0.1, process_message=True)
            self.send_and_process_reply(message)
        sleep(0.1)
        message = b'\x50\x00\x1f\xe0'.ljust(36, b'\x00') + b'\x4f'
        self.send_and_process_reply(message)
        logger.debug("Keep alive done.")

    def read_zone_labels(self):
        logger.info('Reading zone labels...')
        register_dict = getattr(self.registermap,
                                "get" + "zoneLabel" + "Register")()
        for i in range(0, int(self.zones / 2)):
            self.wait_for_message(timeout=0.1, process_message=True)
            message = bytearray(
                register_dict[i * 2 + 1]['Send'], encoding='latin')
            message = message.ljust(36, b'\x00')
            reply = self.send_and_wait_for_reply(message)
            logger.debug("Label packet: {}".format(reply))
            if reply != None:
                try:
                    label = reply[4:20].decode("utf-8").strip()
                except:
                    logger.error("Could not extract label from message {}.".
                                 format(reply))
                    label == None
                if ord(label[0]) == 0 or len(label) == 0:
                    label = None
                self.update_zone_label(zone_number=i * 2 + 1, label=label)
                try:
                    label = reply[20:36].decode("utf-8").strip()
                except:
                    logger.error("Could not extract label from message {}.".
                                 format(reply))
                    label == None
                if ord(label[0]) == 0 or len(label) == 0:
                    label = None
                self.update_zone_label(zone_number=i * 2 + 2, label=label)
        logger.info('Read zone labels.')

    def read_user_labels(self):
        logger.info('Reading user labels...')
        register_dict = getattr(self.registermap,
                                "get" + "userLabel" + "Register")()
        for i in range(0, int(self.users / 2)):
            sleep(0.1)
            message = bytearray(
                register_dict[i * 2 + 1]['Send'], encoding='latin')
            message = message.ljust(36, b'\x00')
            reply = self.send_and_wait_for_reply(message)
            logger.debug("Label packet: {}".format(reply))
            if reply != None:
                try:
                    label = reply[4:20].decode("utf-8").strip()
                except:
                    logger.error("Could not extract label from message {}.".
                                 format(reply))
                    label == None
                if ord(label[0]) == 0 or len(label) == 0:
                    label = None
                self.update_user_label(user_number=i * 2 + 1, label=label)
                try:
                    label = reply[20:36].decode("utf-8").strip()
                except:
                    logger.error("Could not extract label from message {}.".
                                 format(reply))
                    label == None
                if ord(label[0]) == 0 or len(label) == 0:
                    label = None
                self.update_user_label(user_number=i * 2 + 2, label=label)
        logger.info('Read user labels.')

    def read_partition_labels(self):
        logger.info('Reading partition labels...')
        register_dict = getattr(self.registermap,
                                "get" + "partitionLabel" + "Register")()
        for i in range(0, 1):
            self.wait_for_message(timeout=0.1, process_message=True)
            message = bytearray(
                register_dict[i * 2 + 1]['Send'], encoding='latin')
            message = message.ljust(36, b'\x00')
            reply = self.send_and_wait_for_reply(message)
            logger.debug("Label packet: {}".format(reply))
            if reply != None:
                try:
                    label = reply[4:20].decode("utf-8").strip()
                except:
                    logger.error("Could not extract label from message {}.".
                                 format(reply))
                    label == None
                if ord(label[0]) == 0 or len(label) == 0:
                    label = None
                self.update_partition_label(
                    partition_number=i * 2 + 1, label=label)
                try:
                    label = reply[20:36].decode("utf-8").strip()
                except:
                    logger.error("Could not extract label from message {}.".
                                 format(reply))
                    label == None
                if ord(label[0]) == 0 or len(label) == 0:
                    label = None
                self.update_partition_label(
                    partition_number=i * 2 + 2, label=label)
        logger.info('Read partition labels.')

    def read_output_labels(self):
        logger.info('Reading output labels...')
        register_dict = getattr(self.registermap,
                                "get" + "outputLabel" + "Register")()
        for i in range(0, int(self.outputs / 2)):
            self.wait_for_message(timeout=0.1, process_message=True)
            message = bytearray(
                register_dict[i * 2 + 1]['Send'], encoding='latin')
            message = message.ljust(36, b'\x00')
            reply = self.send_and_wait_for_reply(message)
            logger.debug("Label packet: {}".format(reply))
            if reply != None:
                try:
                    label = reply[4:20].decode("utf-8").strip()
                except:
                    logger.error("Could not extract label from message {}.".
                                 format(reply))
                    label == None
                if ord(label[0]) == 0 or len(label) == 0:
                    label = None
                self.update_output_label(output_number=i * 2 + 1, label=label)
                try:
                    label = reply[20:36].decode("utf-8").strip()
                except:
                    logger.error("Could not extract label from message {}.".
                                 format(reply))
                    label == None
                if ord(label[0]) == 0 or len(label) == 0:
                    label = None
                self.update_output_label(output_number=i * 2 + 2, label=label)
        logger.info('Read output labels.')

    def read_labels(self):
        logger.info('Reading all labels...')
        self.read_zone_labels()
        self.read_user_labels()
        self.read_partition_labels()
        self.read_output_labels()
        logger.info('Read all labels.')

    def set_output(self, output_number, on=True, stop_pulse=True):
        if on:
            logger.info('Activating output {}...'.format(
                self.output_data[output_number]['label']))
        else:
            logger.info('Deactivating output {}...'.format(
                self.output_data[output_number]['label']))
        self.control_output(output_number, on)
        self.update_output_property(output_number, property='on', flag=on)
        if stop_pulse:
            self.update_output_property(
                output_number, property='pulse', flag=False)

    def set_output_pulse(self, output_number, pulse=True, stop_pulse=True):
        if pulse:
            logger.info('Activating pulse on output {}...'.format(
                self.output_data[output_number]['label']))
            self.update_output_property(
                output_number, property='pulse', flag=True)
        else:
            logger.info('Deactivating pulse on output {}...'.format(
                self.output_data[output_number]['label']))
            self.set_output(
                output_number=output_number, on=False, stop_pulse=True)

    def pulse_outputs(self):
        for i in range(1, self.outputs + 1):
            if self.output_data[i]['pulse']:
                on = self.output_data[i]['on']
                print(on)
                self.set_output(output_number=i, on=(not on), stop_pulse=False)

    def control_output(self, output_number, on):
        mapping_dict = self.registermap.getcontrolOutputRegister()
        if on:
            state = 'ON'
        else:
            state = 'OFF'
        message = bytearray(
            mapping_dict[output_number][state], encoding='latin')
        message = message.ljust(36, b'\x00')
        self.send_message(message)

    def control_alarm(self, partition_number, state):
        if not state in ['ARM', 'DISARM', 'SLEEP', 'STAY']:
            logger.error('Invalid control_alarm state {}.'.format(state))
        if not partition_number in [1, 2]:
            logger.error('Invalid partition number {:d} for control_alarm.'.
                         format(partition_number))
        logger.info('Setting partition {} to {}.'.format(
            self.partition_data[partition_number]['label'], state))
        mapping_dict = self.registermap.getcontrolAlarmRegister()
        message = bytearray(
            mapping_dict[partition_number][state], encoding='latin')
        message = message.ljust(36, b'\x00')
        self.send_message(message)

    def clear_on_disarm(self):
        #clear siren
        self.update_bell(False)
        #clear zone bypass
        for i in range(1, self.zones + 1):
            self.update_zone_property(i, property="bypass", flag=False)

    def bypass_zone(self, zone_number):
        """Sends bypass command for zone."""
        if zone_number < 1 or zone_number > self.zones:
            logger.error("Invalid zone number {:d}".format(zone_number))
            return
        logger.info('Sending bypass command for zone {}.'.format(
            self.zone_data[zone_number]['label']))
        message = bytearray(b'\x40\x00\x10')
        message.append(zone_number - 1)
        message += b'\x04'
        message = message.ljust(36, b'\x00')
        self.send_message(message)
