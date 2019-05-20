#!/usr/bin/env python

# Copyright (C) 2018-2019 Pierre Hébert
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# WARNING: this software is exactly the one in use in the photovoltaic optimization project. It's tailored for my
#          own use and requires minor adaptations and configuration to run in other contexts.

# This is the main power regulation loop. It's purpose is to match the power consumption with the photovoltaic power.
# Using power measurements and a list of electrical equipments, with varying behaviors and control modes, the regulation
# loop takes decisions such as allocating more power to a given equipment when there is photovoltaic power in excess, or
# shutting down loads when the overall power consumption is higher than the current PV power supply.

# Beside the regulation loop, this software also handles these features
# - manual control ("force"), in order to be able to manually turn on/off a given equipment with a specified power and
#   duration.
# - monitoring: sends a JSON status message on a MQTT topic for reporting on the current regulation state
# - fallback: a very specific feature which aim is to make sure that the water heater receives enough water (either
#   from the PV panels or the grid to keep the water warm enough.

# See the "equipment module" for the definitions of the loads.


import datetime
import json
import time

import paho.mqtt.client as mqtt

from debug import debug as debug
import equipment
from equipment import ConstantPowerEquipment, UnknownPowerEquipment, VariablePowerEquipment

# The comparison between power consumption and production is done every N seconds, it must be above the measurement
# rate, which is currently 4s with the PZEM-004t module.
EVALUATION_PERIOD = 5

# Consider powers are balanced when the difference is below this value (watts). This helps prevent fluctuations.
BALANCE_THRESHOLD = 20

# Keep this margin (in watts) between the power production and consumption. This helps in reducing grid consumption
# knowing that there may be measurement inaccuracy.
MARGIN = 20

# A debug switch to toggle simulation (uses distinct MQTT topics for instance)
SIMULATION = False

last_evaluation_date = None

power_production = None
power_consumption = None

mqtt_client = None

equipments = None
equipment_water_heater = None

# MQTT topics on which to subscribe and send messages
prefix = 's/' if SIMULATION else ''
TOPIC_SENSOR_CONSUMPTION = prefix + "pzem/0"
TOPIC_SENSOR_PRODUCTION = prefix + "pzem/1"
TOPIC_REGULATION_CONTROL = prefix + "regulation/control"
TOPIC_STATUS = prefix + "regulation/status"


def now_ts():
    # python2 support
    return time.time()


def get_equipment_by_name(name):
    for e in equipments:
        if e.name == name:
            return e
    return None


def on_connect(client, userdata, flags, rc):
    debug(0, 'ready')

    client.subscribe(TOPIC_SENSOR_CONSUMPTION)
    client.subscribe(TOPIC_SENSOR_PRODUCTION)
    client.subscribe(TOPIC_REGULATION_CONTROL)


def on_message(client, userdata, msg):
    # Receive power consumption and production values and triggers the evaluation. We also take into account manual
    # control messages in case we want to turn on/off a given equipment.
    global power_production, power_consumption
    if msg.topic == TOPIC_SENSOR_CONSUMPTION:
        j = json.loads(msg.payload.decode())
        power_consumption = int(j['p'])
        evaluate()
    elif msg.topic == TOPIC_SENSOR_PRODUCTION:
        j = json.loads(msg.payload.decode())
        power_production = int(j['p'])
        evaluate()
    elif msg.topic == TOPIC_REGULATION_CONTROL:
        j = json.loads(msg.payload.decode())
        command = j['command']
        name = j['name']
        if command == 'force':
            e = get_equipment_by_name(name)
            if e:
                power = j['power']
                msg = 'forcing equipment {} to {}W'.format(name, power)
                duration = j.get('duration')  # duration is optional with default value None
                if duration:
                    msg += ' for '+str(duration)+' seconds'
                else:
                    msg += ' without time limitation'
                debug(0, '')
                debug(0, msg)
                e.force(power, duration)
                evaluate()
        elif command == 'unforce':
            e = get_equipment_by_name(name)
            if e:
                debug(0, '')
                debug(0, 'not forcing equipment {} anymore'.format(name))
                e.force(None)
                evaluate()


# Specific fallback: the energy put in the water heater yesterday (see below)
energy_yesterday = 0

def low_energy_fallback():
    """ Fallback, when the amount of energy today went below a minimum"""

    # This is a custom and very specific fallback method which aim is to turn on the water heater should the daily
    # solar energy income be below a minimum threshold. We want the water to stay warm.
    # The check is done everyday at 16h

    global energy_yesterday

    LOW_ENERGY_TWO_DAYS = 4000  # minimal power on two days
    LOW_ENERGY_TODAY = 2000  # minimal power for today
    CHECK_AT = 16  # hour

    t = now_ts()
    if last_evaluation_date is not None:

        d1 = datetime.datetime.fromtimestamp(last_evaluation_date)
        d2 = datetime.datetime.fromtimestamp(t)

        energy_today = equipment_water_heater.get_energy()

        # save the energy so that it can be used in the fallback check tomorrow
        if d1.hour == 22 and d2.hour == 23:
            energy_yesterday = energy_today

        if d1.hour == CHECK_AT - 1 and d2.hour == CHECK_AT:
            max_power = equipment_water_heater.max_power
            if (energy_yesterday + energy_today) < LOW_ENERGY_TWO_DAYS and energy_today < LOW_ENERGY_TODAY:
                duration = 3600 * (LOW_ENERGY_TODAY - energy_today) / max_power
                debug(0, '')
                debug(0, 'daily energy fallback: forcing equipment {} to {}W for {} seconds'.format(
                    equipment_water_heater.name, max_power, duration))
                equipment_water_heater.force(max_power, duration)


def evaluate():
    # This is where all the magic happen. This function takes decision according to the current power measurements.
    # It examines the list of equipments by priority order, their current state and computes which one should be
    # turned on/off.

    global last_evaluation_date

    try:
        t = now_ts()
        if last_evaluation_date is not None:
            # reset energy counters every day
            d1 = datetime.datetime.fromtimestamp(last_evaluation_date)
            d2 = datetime.datetime.fromtimestamp(t)
            if d1.day != d2.day:
                for e in equipments:
                    e.reset_energy()

            # ensure there's a minimum duration between two evaluations
            if t - last_evaluation_date < EVALUATION_PERIOD:
                return

        # ensure that water stays warm enough
        low_energy_fallback()

        last_evaluation_date = t

        if power_production is None or power_consumption is None:
            return

        debug(0, '')
        debug(0, 'evaluating power consumption={}, power production={}'.format(power_consumption, power_production))

        # Here starts the real work, compare powers
        if power_consumption > (power_production - MARGIN):
            # Too much power consumption, we need to decrease the load
            excess_power = power_consumption - (power_production - MARGIN)
            debug(0, "decreasing global power consumption by {}W".format(excess_power))
            for e in reversed(equipments):
                debug(2, "examining " + e.name)
                if e.is_forced():
                    debug(4, "skipping this equipment because it's in forced state")
                    continue
                result = e.decrease_power_by(excess_power)
                if result is None:
                    debug(2, "stopping here and waiting for the next measurement to see the effect")
                    break
                excess_power -= result
                if excess_power <= 0:
                    debug(2, "no more excess power consumption, stopping here")
                    break
                else:
                    debug(2, "there is {}W left to cancel, continuing".format(excess_power))
            debug(2, "no more equipment to check")
        elif (power_production - MARGIN - power_consumption) < BALANCE_THRESHOLD:
            # Nice, this is the goal: consumption is equal to production
            debug(0, "power consumption and production are balanced")
        else:
            # There's power in excess, try to increase the load to consume this available power
            available_power = power_production - MARGIN - power_consumption
            debug(0, "increasing global power consumption by {}W".format(available_power))
            for i, e in enumerate(equipments):
                if available_power <= 0:
                    debug(2, "no more available power")
                    break
                debug(2, "examining " + e.name)
                if e.is_forced():
                    debug(4, "skipping this equipment because it's in forced state")
                    continue
                result = e.increase_power_by(available_power)
                if result is None:
                    debug(2, "stopping here and waiting for the next measurement to see the effect")
                    break
                elif result == 0:
                    debug(2, "no more available power to use, stopping here")
                    break
                elif result < 0:
                    debug(2, "not enough available power to turn on this equipment, trying to recover power on lower priority equipments")
                    freeable_power = 0
                    needed_power = -result
                    for j in range(i + 1, len(equipments)):
                        o = equipments[j]
                        if o.is_forced():
                            continue
                        p = o.get_current_power()
                        if p is not None:
                            freeable_power += p
                    debug(2, "power used by other equipments: {}W, needed: {}W".format(freeable_power, needed_power))
                    if freeable_power >= needed_power:
                        debug(2, "recovering power")
                        freed_power = 0
                        for j in reversed(range(i + 1, len(equipments))):
                            o = equipments[j]
                            if o.is_forced():
                                continue
                            result = o.decrease_power_by(needed_power)
                            freed_power += result
                            needed_power -= result
                            if needed_power <= 0:
                                debug(2, "enough power has been recovered, stopping here")
                                break
                        new_available_power = available_power + freed_power
                        debug(2, "now trying again to increase power of {} with {}W".format(e.name, new_available_power))
                        available_power = e.increase_power_by(new_available_power)
                    else:
                        debug(2, "this is not possible to recover enough power on lower priority equipments")
                else:
                    available_power = result
                    debug(2, "there is {}W left to use, continuing".format(available_power))
            debug(2, "no more equipment to check")

        # Build a status message
        status = {
            'date': t,
            'date_str': datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S'),
            'power_consumption': power_consumption,
            'power_production': power_production,
        }
        es = []
        for e in equipments:
            p = e.get_current_power()
            es.append({
                'name': e.name,
                'current_power': 'unknown' if p is None else p,
                'energy': e.get_energy(),
                'forced': e.is_forced()
            })
        status['equipments'] = es
        mqtt_client.publish(TOPIC_STATUS, json.dumps(status))

    except Exception as e:
        debug(0, e)


def main():
    global mqtt_client, equipments, equipment_water_heater

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect("192.168.1.7", 1883, 120)

    equipment.setup(mqtt_client, not SIMULATION)

    # This is a list of equipments by priority order (first one has the higher priority). As many equipments as needed
    # can be listed here.
    equipment_water_heater = VariablePowerEquipment('water_heater', 2400)
    equipments = (
        ConstantPowerEquipment('e_bike_charger', 120),
        equipment_water_heater,
        # ConstantPowerEquipment('heater', 1800, mqtt_client),
        # UnknownPowerEquipment('plug_1')
    )

    # At startup, reset everything
    for e in equipments:
        e.set_current_power(0)

    mqtt_client.loop_forever()


if __name__ == '__main__':
    main()
