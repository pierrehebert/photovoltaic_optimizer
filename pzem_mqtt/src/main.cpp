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
#include "pzem004t.h"

// Unique id of this module, which is used to build the MQTT topic on which data are published.
#define PZEM_ID 0

// Wait this duration between each measurement (milliseconds). This is added to the time needed to read data (~2s).
// It seems the PZEM-004t has an integration period of about 4s, hence no need to read faster than this.
#define PERIOD 3000

// A debug switch to publish raw data.
//#define PUBLISH_RAW_DATA

// Enter you WiFi and MQTT settings here.
const char* ssid = "<your ssid here>>";
const char* password = "<your password here>";
const char* mqtt_server = "<your broker ip address here>";

// WiFi + MQTT stuff.
WiFiClient espClient;
PubSubClient client(espClient);
String outTopic;

// Setup our pzem module with these pins : pins must be chosen carefully so that the ESP can boot.
PZEM004T pzem(1, 2);


// Utility debug function.
#ifdef PUBLISH_RAW_DATA
#define PUBLISH_RAW(...) publish_raw(__VA_ARGS__);
void publish_raw(const char *topic) {
    String s;
    const char *raw = pzem.getRawData();
    for(int i=0; i<PZEM_MSG_LENGTH; i++) {
        s+=" "+String(raw[i], HEX);
    }
    client.publish(topic, s.c_str());
}
#else
#define PUBLISH_RAW(...)
#endif

void setup_wifi() {
    delay(10);

    WiFi.softAPdisconnect (true);

    WiFi.begin(ssid, password);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }

    randomSeed(micros());
}

void reconnect() {
    while (!client.connected()) {
        String clientId = "pzem-";
        clientId += String(PZEM_ID);
        if (!client.connect(clientId.c_str())) {
            delay(5000);
        }
    }
}

void setup() {
   setup_wifi();

    client.setServer(mqtt_server, 1883);

    // data will be published on this topic
    outTopic = "pzem/";
    outTopic += String(PZEM_ID);

    // wait for a correct init handshake before to continue
    while(!pzem.init()) {
        delay(1000);
    }
}

void loop() {
    if (!client.connected()) {
        reconnect();
    }
    client.loop();

    float v = pzem.voltage();
    PUBLISH_RAW("pzem/raw/v");

    float c = pzem.current();
    PUBLISH_RAW("pzem/raw/c");

    uint16_t p = pzem.power();
    PUBLISH_RAW("pzem/raw/p");

    uint32_t e = pzem.energy();
    PUBLISH_RAW("pzem/raw/e");

    if(v != -1 && c != -1 && p != 0xffff && e != 0xffffffff) {
        String msg = "{\"v\":";
        msg += String(v);
        msg += ", \"c\": ";
        msg += String(c);
        msg += ", \"p\": ";
        msg += String(p);
        msg += ", \"e\": ";
        msg += String(e);
        msg += "}";

        client.publish(outTopic.c_str(), msg.c_str());
    }

    delay(PERIOD);
}
