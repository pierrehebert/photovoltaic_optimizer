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

// Simple implementation to validate the SCR control

#include <U8glib.h>

// the pin on which the zero signal is received
#define PIN_ZERO 2

// the pin on which the SCR signal is emitted
#define PIN_SCR 4

// buttons to control the power
#define PIN_BUTTON_MINUS 5
#define PIN_BUTTON_PLUS 6

bool button_minus_pushed = false;
bool button_plus_pushed = false;

// the current power value, in percent of time
int power = 100;

// armed in the ISR to indicate the zero crossing
volatile bool triggered = false;

// the screen to display the current power value
U8GLIB_SSD1306_128X64 u8g(U8G_I2C_OPT_NONE);

void draw() {
    String s = String(power);
    u8g.drawStr( 0, 30, s.c_str());
}

void refresh() {
    u8g.firstPage();
    do {
        draw();
    } while(u8g.nextPage());
}

// ISR called on zero crossing
void onZero() {
    triggered = true;
}

void setup() {
    attachInterrupt(digitalPinToInterrupt(PIN_ZERO), onZero, CHANGE);

    pinMode(PIN_SCR, OUTPUT);
    digitalWrite(PIN_SCR, LOW);

    pinMode(PIN_BUTTON_MINUS, INPUT_PULLUP);
    pinMode(PIN_BUTTON_PLUS, INPUT_PULLUP);

    u8g.setColorIndex(1);
    u8g.setFont(u8g_font_profont29);

    refresh();
}

void loop() {
    if(triggered) {
        triggered = false;
        if(power > 0) {
            // power=100%: no wait, power=0%: wait 10ms
            int delay = power==100? 30 : (100-power)*100;
            delayMicroseconds(delay);

            // generate a pulse (below 50% this is a short pulse, above the pulse has a 3ms duration)
            digitalWrite(PIN_SCR, HIGH);
            delayMicroseconds(power < 50 ? 5 : 3000);
            digitalWrite(PIN_SCR, LOW);
        }
    }

    // manage button
    bool pushed = digitalRead(PIN_BUTTON_MINUS) == LOW;
    if(!button_minus_pushed && pushed) {
        button_minus_pushed = true;
        if(power > 0) {
            power--;
            refresh();
        }
    }
    if(!pushed && button_minus_pushed) {
        button_minus_pushed = false;
    }

    // manage button
    pushed = digitalRead(PIN_BUTTON_PLUS) == LOW;
    if(!button_plus_pushed && pushed) {
        button_plus_pushed = true;
        if(power < 100) {
            power++;
            refresh();
        }
    }
    if(!pushed && button_plus_pushed) {
        button_plus_pushed = false;
    }
}