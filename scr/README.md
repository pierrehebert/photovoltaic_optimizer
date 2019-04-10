# Stuff related to the SCR control.

Please read https://www.pierrox.net/wordpress/2019/03/04/optimisation-photovoltaique-3-controle-numerique-du-variateur-de-puissance/ (French).

There are three implementations
- Arduino/scr_control_local : Initial implementation, Arduino Nano based, with local control.
- Arduino/scr_control_remote : Arduino Nano based, with remote control using NRF24L01+.
- PlatformIO/scr_control : PIO project using an ESP-01 module, WiFi and MQTT. This is the one I use in my photovoltaic optimization project.
