/*
 * Copyright (C) 2018-2019 Pierre Hébert
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "pzem004t.h"

PZEM004T::PZEM004T() {
    HardwareSerial *hs = new HardwareSerial(UART0);
    hs->begin(9600);
    port = hs;
}

PZEM004T::PZEM004T(int receivePin, int transmitPin) {
    SoftwareSerial *ss = new SoftwareSerial(receivePin, transmitPin);
    ss->begin(9600);
    port = ss;
}

bool PZEM004T::init() {
    flush();
    port->write(RequestSetAddress, sizeof(RequestSetAddress));
    return read_reply();
}

float PZEM004T::voltage() {
    flush();
    port->write(RequestReadVoltage, sizeof(RequestReadVoltage));
    if(read_reply()) {
        return read_buffer[2] + read_buffer[3] / 10.0;
    } else {
        return -1;
    }
}

float PZEM004T::current() {
    flush();
    port->write(RequestReadCurrent, sizeof(RequestReadCurrent));
    if(read_reply()) {
        return read_buffer[2] + read_buffer[3] / 100.0;
    } else {
        return -1;
    }
}

uint16_t PZEM004T::power() {
    flush();
    port->write(RequestReadPower, sizeof(RequestReadPower));
    if(read_reply()) {
        return (((uint16_t)read_buffer[1]) << 8) + read_buffer[2];
    } else {
        return 0xffff;
    }
}

uint32_t PZEM004T::energy() {
    flush();
    port->write(RequestReadEnergy, sizeof(RequestReadEnergy));
    if(read_reply()) {
        return (((uint32_t)read_buffer[1]) << 16) + (((uint32_t)read_buffer[2]) << 8) + read_buffer[3];
    } else {
        return 0xffffffff;
    }
}

bool PZEM004T::read_reply() {
    int len = 0;
    unsigned long startTime = millis();
    while((len < sizeof(read_buffer)) && (millis() - startTime < 1000)) {
        if(port->available() > 0) {
            read_buffer[len++] = port->read();
        } else {
            yield();
        }
    }

    if(len != sizeof(read_buffer)) {
        // bad reply size
        return false;
    }

    char crc = (read_buffer[0] + read_buffer[1] + read_buffer[2] + read_buffer[3] + read_buffer[4] + read_buffer[5]) & 0xff;
    if(crc != read_buffer[6]) {
        // bad crc
        return false;
    }

    return true;
}

void PZEM004T::flush() {
    while(port->available()) {
        port->read();
    }
}

const char *PZEM004T::getRawData() {
    return read_buffer;
}

const char PZEM004T::RequestSetAddress[] = {0xB4, 0xC0, 0xA8, 0x01, 0x01, 0x00, 0x1E};
const char PZEM004T::RequestReadVoltage[] = {0xB0, 0xC0, 0xA8, 0x01, 0x01, 0x00, 0x1A};
const char PZEM004T::RequestReadCurrent[] = {0xB1, 0xC0, 0xA8, 0x01, 0x01, 0x00, 0x1B};
const char PZEM004T::RequestReadPower[] = {0xB2, 0xC0, 0xA8, 0x01, 0x01, 0x00, 0x1C};
const char PZEM004T::RequestReadEnergy[] = {0xB3, 0xC0, 0xA8, 0x01, 0x01, 0x00, 0x1D};
