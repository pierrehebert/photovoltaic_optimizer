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

import json

import paho.mqtt.client as mqtt
import time

import sys

from pzem import BTPOWER


def main():
    client = mqtt.Client()
    client.connect("vpi3", 1883, 120)

    client.loop_start()

    sensor = BTPOWER()

    print('percent;power')
    for percent in range(100, -1, -1):
        print('# command to {}%'.format(percent))
        client.publish('scr/0/in', str(percent))

        time.sleep(5)

        avg_power = 0
        avg_count = 12
        n = 0
        while n < avg_count:
            read_power = sensor.readPower()
            if read_power > 1:
                print('# read {}W'.format(read_power))
                sys.stdout.flush()
                avg_power += read_power
                n += 1
            time.sleep(1)
        avg_power /= float(avg_count)

        print('{};{}'.format(percent, avg_power))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
