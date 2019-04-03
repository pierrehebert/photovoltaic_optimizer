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

#include <ESP8266WiFi.h>
#include <PubSubClient.h>

const char* ssid = "<your ssid here>";
const char* password = "<your password here>";
const char* mqtt_server = "<your mqtt broker ip address here>";

// SCR identifier, there might be more than one power regulation device on the network, select an id here
#define SCR_ID 0

// these pins are used to connect to the SCR
#define PIN_ZERO 1
#define PIN_SCR 3


WiFiClient espClient;
PubSubClient client(espClient);
String outTopic;
String inTopic;

// current power (as a percentage of time) : power off at startup.
float power = 0;

// this function pointer is used to store the next timer action (see call_later and onTimerISR below)
void (*timer_callback)(void);

// used to acknowledge the current power command
void sendCurrentPower() {
    client.publish(outTopic.c_str(), String(power).c_str(), true);
}

void setup_wifi() {
    delay(10);

    WiFi.softAPdisconnect (true);

    WiFi.begin(ssid, password);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }
}

void on_message(char* topic, byte* payload, unsigned int length) {
    char buffer[length+1];
    memcpy(buffer, payload, length);
    buffer[length] = '\0';
    float p = String(buffer).toFloat();
    if(p >= 0 && p<=100) {
        power = p;
        sendCurrentPower();
    }
}

void reconnect() {
    while (!client.connected()) {
        String clientId = "scr-";
        clientId += String(SCR_ID);
        if (client.connect(clientId.c_str())) {
            client.subscribe(inTopic.c_str());
            sendCurrentPower();
        } else {
            delay(5000);
        }
    }
}
 
void call_later(unsigned long duration_us, void(*callback)(void)) {
    timer_callback = callback;
    // 5 ticks/us
    timer1_write(duration_us * 5);
}

// timer interrupt routine : call the function which gas been registered earlier (see call_later)
void ICACHE_RAM_ATTR onTimerISR(){
    void (*f)(void) = timer_callback;
    timer_callback = NULL;
    if(f) {
        f();
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

    call_later(power < 50 ? 5 : 3000, onPulseEnd);
}

// pin ZERO interrupt routine
void onZero() {
    if(power > 0) {
        // generate a pulse after this zero
        // power=100%: no wait, power=0%: wait 10ms
        unsigned long delay = power==100 ? 30 : (100-power)*100;
        call_later(delay, onDelayExpired);
    }
}

void setup() {
    // usual pin configuration
    pinMode(PIN_SCR, OUTPUT);
    digitalWrite(PIN_SCR, LOW);
    pinMode(PIN_ZERO, INPUT);

    // as long as we are not connected to wifi, the SCR will remain "off" (no SCR pulse at all)
    setup_wifi();

    // setup the MQTT stuff (one topic for commands, another one to broadcast the current power)
    outTopic = "scr/" + String(SCR_ID) +"/out";
    inTopic = "scr/" + String(SCR_ID) +"/in";
    client.setServer(mqtt_server, 1883);
    client.setCallback(on_message);

    // setup the timer used to manage SCR tops
    timer1_isr_init();
    timer1_attachInterrupt(onTimerISR);
    timer1_enable(TIM_DIV16, TIM_EDGE, TIM_SINGLE); // 5 ticks/us
    
    // listen for change on the pin ZERO
    attachInterrupt(digitalPinToInterrupt(PIN_ZERO), onZero, CHANGE);
}

void loop() {
    if (!client.connected()) {
        reconnect();
    }
    client.loop();  
}