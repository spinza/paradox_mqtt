# paradox_mqtt
Paradox Alarm - Serial - MQTT interface

This code allows you to connecet Paradox MG5050 via serial interface via MQTT.

# Credit
This is based on work in these two repositories:

* https://github.com/Tertiush/ParadoxIP150v2
* https://github.com/jpbarraca/ParadoxMulti-MQTT

# Improvements

Improvements over the above scripts:
* Better code handling of alarm situations.  Both the above failed to notify of zones under alarm.
* Handles more messages from the alarm.
* More zone states (including alarm, bpass, fire_alarm etc.)
* More logic for tracking zone/alarm/partition states.
* Publishes in [Homie standard](https://homieiot.github.io/)

# Install

1. Clone the repository
2. `cd` into the project folder
3. Copy the config_sample.py to config.py and uncomment the settings you wish to change. The commented values represent the default values.
4. Create a virtual enivornment with `python3 -m venv venv`
5. Activate it with `source venv/bin/activate`
6. Install requirement with `pip install -r requirements.txt`
7. Run with `python main.py`.
8. Use the supplied `paradox_mqtt.service` to setup a service to start this automatically.

# MQTT Topics

The script publishes alarm details under various topics (as per defaults):

This publishes on the Homie standard.

Some  high level topics are published:

* `homie/alarm/panel/` contains panel details such as battery states etc.
* `homie/alarm/panel/alarm/` is the alarm state
* `homie/alarm/partition1/` contains the partition 1 arm states and alarm states.
* `homie/alarm/partition2/` contains the partition 2 arm states and alarm states.
* `homie/alarm/troubleindicators/` contains trouble indicators.
* `homie/alarm/moduletroubleindicators/` contains module trouble indicators.
* `homie/alarm/output1/` contains output details for output 1. 
* `homie/alarm/zone1/` contains zone details for zone 1.
* `homie/alarm/zone1/open` contain is the open status of a zone (e.g. movement for PIRs).
* `homie/alarm/zone1/bypass` contains whether zone is bypassed.
* `homie/alarm/zone1/alarm` whehter the zone is causing an alarm.
* `homie/alarm/zone1/lowbattery` whether the zone battery is low (for wireless battery powered PIRs)

Settable topics contain the property `settable`.  For example `homie/alarm/zone1/bypass/$settable true` indicates that we can publish to this topic to set a value (and consequently bypass the zone).

Arming can be done in several ways but perhaps the easies is setting `homie/alarm/partition1/armstate` to an integer as follows:

* 0 - Disarmed
* 1 - Stay Armed
* 2 - Sleep Armed
* 3 - Armed
