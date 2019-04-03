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


/***** Designed for the Nano *******/

// This version is interrupt driven. For a simple, synchronous version, see scr_control_local

#include <RF24.h>
#include <STimer.h>
#include <MessageIDs.h>

// the pin on which the zero signal is received
#define PIN_ZERO 2

// the pin on which the SCR signal is emitted
#define PIN_SCR 4

// NRF24L01+ module pin configuration
#define CE_PIN 9
#define CSN_PIN 10
RF24 radio(CE_PIN, CSN_PIN);
byte src_address[5] = RF24_ADDRESS_TA;
char rf24_buffer[32];

// the current power value, in percent of time
float power = 4;

// ISR called on zero crossing
void onZero() {
    if(power > 0) {
        // generate a pulse after this zero
        // power=100%: no wait, power=0%: wait 10ms
        int delay = power==100? 30 : (100-power)*100;
        call_later(delay, 8, onDelayExpired);
    }
}

// called at the end of the pulse
void onPulseEnd() {
    digitalWrite(PIN_SCR, LOW);
}

// called when the delay after the zero crossing has expired
void onDelayExpired() {
    // start the pulse and arm a timer to end it
    // generate a pulse (below 50% this is a short pulse, above the pulse has a 3ms duration)
    digitalWrite(PIN_SCR, HIGH);

    call_later(power < 50 ? 5 : 3000, 8, onPulseEnd);
}

void setup() {
    // setup the interrupt on the zero crossing signal
    pinMode(PIN_ZERO, INPUT);
    attachInterrupt(digitalPinToInterrupt(PIN_ZERO), onZero, CHANGE);

    // setup the SCR control pin
    pinMode(PIN_SCR, OUTPUT);
    digitalWrite(PIN_SCR, LOW);

    // setup the radio interface
    radio.begin(); // Start up the radio
    // radio.setAutoAck(1); // Ensure autoACK is enabled
    radio.setDataRate(RF24_250KBPS);
    radio.setPALevel(RF24_PA_MAX);
    radio.setRetries(5, 5); // Max delay between retries & number of retries
    radio.openReadingPipe(1, src_address);
    radio.powerUp();
    radio.startListening();

//    Serial.begin(115200);
//    Serial.println("ready");
}

void loop() {
    if(radio.available()) {
        radio.read(rf24_buffer, sizeof(rf24_buffer));
        if((unsigned char)rf24_buffer[0] == DEV_VPI3 && rf24_buffer[1] == DEV_SCR01 && rf24_buffer[2] == FCODE_WRITE_REQUEST) {
            power = *(float*)&rf24_buffer[3];
//            Serial.println(power);
        }
    }
}