import time

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

# This module defines various equipments type depending on their control mechanism and power consumption profile.
# A brief summary of classes defined here:
# - Equipment: base class, with common behaviour and processing (including forcing and energy counter)
# - VariablePowerEquipment: an equipment which load can be controlled from 0 to 100%. It specifically uses the
#       digitally controlled SCR as described here: https://www.pierrox.net/wordpress/2019/03/04/optimisation-photovoltaique-3-controle-numerique-du-variateur-de-puissance/
# - UnknownPowerEquipment: an equipment which load can vary over time. It's controlled like a switch (either on or off).
#       This equipment is however not fully implemented as it has been specialized in the ConstantPowerEquipment below.
# - ConstantPowerEquipment: an equipment which load is fixed and known. It can be controlled like a switch.
#       ConstantPowerEquipment is essentially an optimization of UnknownPowerEquipment as it will allow the regulation
#       loop to match power consumption and production faster.

from debug import debug as debug

_mqtt_client = None
_send_commands = True


def setup(mqtt_client, send_commands):
    global _mqtt_client, _send_commands
    _mqtt_client = mqtt_client
    _send_commands = send_commands


def now_ts():
    return time.time()


class Equipment:
    def __init__(self, name):
        self.name = name
        self.is_forced_ = False
        self.force_end_date = None
        self.energy = 0
        self.current_power = None
        self.last_power_change_date = None

    def decrease_power_by(self, watt):
        """ Return the amount of power that has been canceled, None if unknown """
        # implement in subclasses
        pass

    def increase_power_by(self, watt):
        """ Return the amount of power that is left to use, None if unknown """
        # implement in subclasses
        pass

    def set_current_power(self, power):
        if self.last_power_change_date is not None:
            now = now_ts()
            delta = now - self.last_power_change_date
            self.energy += self.current_power * delta / 3600.0

        self.current_power = power
        self.last_power_change_date = now_ts()

    def get_current_power(self):
        return self.current_power

    def force(self, watt, duration=None):
        """ Force this equipment to the specified power in watt, for a given duration in seconds (None=forever)"""
        # implement in subclasses, watt may be ignored
        self.is_forced_ = watt is not None
        if duration is None:
            self.force_end_date = None
        else:
            self.force_end_date = now_ts() + duration

    def is_forced(self):
        if self.force_end_date is not None:
            if now_ts() > self.force_end_date:
                self.is_forced_ = False
                self.force_end_date = None
        return self.is_forced_

    def get_energy(self):
        return self.energy

    def reset_energy(self):
        if self.last_power_change_date is not None:
            now = now_ts()
            delta = now - self.last_power_change_date
            self.energy += self.current_power * delta / 3600.0

        previous_energy = self.energy
        self.energy = 0
        self.last_power_change_date = now_ts()

        return previous_energy


class VariablePowerEquipment(object, Equipment):
    MINIMUM_POWER = 150
    MINIMUM_PERCENT = 4

    def __init__(self, name, max_power):
        Equipment.__init__(self, name)
        self.max_power = max_power

    def set_current_power(self, power):
        super(VariablePowerEquipment, self).set_current_power(power)

        # regression factors computed from the response measurement of the SCR regulator
        a=1156.7360635374
        b=-2733.09296216279
        c=2365.91298447422
        d=-924.443712230202
        e=218.242717162968
        f=-0.010002294517421
        g=11.3205979917473

        if self.current_power == 0:
            percent = 0
        else:
            z = self.current_power / float(self.max_power)
            percent = g + f/z + e*z + d*z*z + c*z*z*z + b*z*z*z*z + a*z*z*z*z*z

        # issue with the regulator, don't go below 4
        if percent < VariablePowerEquipment.MINIMUM_PERCENT:
            percent = VariablePowerEquipment.MINIMUM_PERCENT 
        if percent > 100:
            percent = 100

        if _send_commands:
            _mqtt_client.publish('scr/0/in', str(percent))
        debug(4, "sending power command {}W ({}%) for {}".format(self.current_power, percent, self.name))

    def decrease_power_by(self, watt):
        if watt >= self.current_power:
            decrease = self.current_power
        else:
            decrease = watt

        if self.current_power - decrease < VariablePowerEquipment.MINIMUM_POWER:
            debug(4, "turning off power because it is below the minimum power: "+str(VariablePowerEquipment.MINIMUM_POWER))
            decrease = self.current_power

        if decrease > 0:
            old = self.current_power
            new = self.current_power - decrease
            self.set_current_power(new)
            debug(4, "decreasing power consumption of {} by {}W, from {} to {}".format(self.name, decrease, old, new))
        else:
            debug(4, "not decreasing power of {} because it is already at 0W".format(self.name))

        return decrease

    def increase_power_by(self, watt):
        if self.current_power + watt >= self.max_power:
            increase = self.max_power - self.current_power
            remaining = watt - increase
        else:
            increase = watt
            remaining = 0

        if self.current_power + increase < VariablePowerEquipment.MINIMUM_POWER:
            debug(4, "not increasing power because it doesn't reach the minimal power: "+str(VariablePowerEquipment.MINIMUM_POWER))
            increase = 0
            remaining = watt

        if increase == 0:
            debug(4, "status quo")
        elif increase > 0:
            old = self.current_power
            new = self.current_power + increase
            self.set_current_power(new)
            debug(4, "increasing power consumption of {} by {}W, from {} to {}".format(self.name, increase, old, new))
        else:
            debug(4, "not increasing power of {} because it is already at maximum power {}W".format(self.name, self.max_power))

        return remaining

    def force(self, watt, duration=None):
        super(VariablePowerEquipment, self).force(watt, duration)
        self.set_current_power(0 if watt is None else watt)


class ConstantPowerEquipment(object, Equipment):
    def __init__(self, name, nominal_power):
        Equipment.__init__(self, name)
        self.nominal_power = nominal_power
        self.is_on = False

    def set_current_power(self, power):
        super(ConstantPowerEquipment, self).set_current_power(power)
        self.is_on = power != 0
        msg = '1' if self.is_on else '0'
        if _send_commands:
            _mqtt_client.publish('wifi_plug/0/in', msg, retain=True)
        debug(4, "sending power command {} for {}".format(self.is_on, self.name))

    def decrease_power_by(self, watt):
        if self.is_on:
            debug(4, "shutting down {} with a consumption of {}W to recover {}W".format(self.name, self.nominal_power, watt))
            self.set_current_power(0)
            return self.nominal_power
        else:
            debug(4, "{} with a power of {}W is already off".format(self.name, self.nominal_power))
            return 0

    def increase_power_by(self, watt):
        if self.is_on:
            debug(4, "{} with a power of {}W is already on".format(self.name, self.nominal_power))
            return watt
        else:
            if watt >= self.nominal_power:
                debug(4, "turning on {} with a consumption of {}W to use {}W".format(self.name, self.nominal_power, watt))
                self.set_current_power(self.nominal_power)
                return watt - self.nominal_power
            else:
                debug(4, "not turning on {} with a consumption of {}W because it would use more than the available {}W".format(self.name, self.nominal_power, watt))
                return watt

    def force(self, watt, duration=None):
        super(ConstantPowerEquipment, self).force(watt, duration)
        if watt is not None and watt >= self.nominal_power:
            self.set_current_power(self.nominal_power)
        else:
            self.set_current_power(0)


class UnknownPowerEquipment(Equipment):
    def __init__(self, name):
        Equipment.__init__(self, name)
        self.is_on = False

    def send_power_command(self):
        debug(4, "sending power command {} for {}".format(self.is_on, self.name))
        pass

    def decrease_power_by(self, watt):
        if self.is_on:
            self.is_on = False
            debug(4, "shutting down {} with an unknown consumption to recover {}W".format(self.name, watt))
            return None
        else:
            debug(4, "{} with an unknown power is already off".format(self.name))
            return 0

    def increase_power_by(self, watt):
        if self.is_on:
            debug(4, "{} with an unknown power is already on".format(self.name))
            return watt
        else:
            self.is_on = True
            debug(4, "turning on {} with an unknown consumption use {}W".format(self.name, watt))
            return None

    def force(self, watt, duration=None):
        super(UnknownPowerEquipment, self).force(watt, duration)
        if watt is None:
            self.is_on = False
            self.set_current_power(0)
        else:
            self.is_on = True
            self.set_current_power(watt)
