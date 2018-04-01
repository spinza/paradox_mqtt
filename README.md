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

# Install

Clone the repository and copy the config_sample.py to config.py and uncomment the settings you wish to change. The commented values represent the default values.

# MQTT Topics

The script publishes alarm details under various topics (as per defaults):

## State Channels

* `paradox_mqtt/states/zones/[machine label]` - Details of each zone.
* `paradox_mqtt/states/outputs/[machine label]` - Details of each output.
* `paradox_mqtt/states/partitions/[machine label]` - Details of each partition.
* `paradox_mqtt/states` - other alarm status items.

`[machine label]` is the label of the zone/ouput/etc. but with spaces replaced by underscores.

## Control Channels

Control various zones/partitions/outputs via publishing messages to:
* `paradox_mqtt/control/zones/[machine label]`                                                                                                                                                              
* `paradox_mqtt/control/outputs/[machine label]`
* `paradox_mqtt/control/partitions/[machine label]`

## Partition controls                                    

Control a partition by publishing to `ON` or `OFF` to `paradox_mqtt/control/partitions/[machine label]/[property]`. 

`[property]` can be one of:
* `arm` - arms or disarms the alarm.  By default arms on fully armed.
* `arm_full`  - arms of disarms the alarm.  Arming does fully armed.
* `arm_sleep` - arms the alarm on sleep mode (or disarms).
* `arm_stay` - arms the alarm in sleep mode (or disarms).

## Zone controls

Control a zone by publishing to `ON` or `OFF` to `paradox_mqtt/control/zones/[machine label]/bypass`. This is not yet implemented.

## Output controls

Control an output by publishing to `ON` or `OFF` to `paradox_mqtt/control/outputs/[machine label]/[property]`.

`[property]` can be one of: 
* `on` - activate or disable the output.
* `pules` - activates the output in pulses.


