# PZEM-004t to MQTT

This PlatformIO projects lets you publish AC power data  to a MQTT topic, using a PZEM-004t module and an ESP8266 module (works on a tiny ESP-01 board).

**Important**: have a look at src/main.cpp and update settings at the top of the file (module ID, WiFi, MQTT broker, etc.).

There's also an OpenScad model for the box. It can be 3D printed to hold the PZEM and it's ESP-01 (in 3dprint/pzem_box.scad).

Please read https://www.pierrox.net/wordpress/2019/04/05/optimisation-photovoltaique-4-mesurer-lenergie-produite-et-lenergie-consommee/ (French).