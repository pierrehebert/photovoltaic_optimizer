#!/usr/bin/env python

# French only. This is a specific tool to compute the "instantaneous" power consumption from the EDF consumption indexes.

# Cet outil utilise les indexes de consommation lus depuis la sortie EDF (Enedis) TIC. Les données TIC ne fournissent
# pas la puissance instantanée. Il existe un champ "PAPP" (puissance apparente) mais sa valeur est bien distincte de
# la puissance active instantanée. En outre elle ne fournit pas le "sens" du courant (soutirage ou injection). Seuls
# les compteurs d'index (ici HC et HP pour un tarif bleu heures creuses/pleines) fournissent la valeur exacte correspondant
# à la facturation. Or les compteurs ne sont pas une valeur instantanée. L'objectif de ce programme est justement
# de déduire une valeur plus ou moins instantanée par chronométrage du temps qui s'écoule entre 2 changements d'index.
# Etant donné la résolution de l'index (1W/h) la précision est forcément très limitée pour les petites puissances. De plus
# la lecture des indexes est réalisée de manière cyclique, on perd donc en précision temporelle.
# Ceci étant, au dessus de 500W on obtient des résultats satisfaisant. Ils permettent essentiellement de vérifier la
# cohérence des autres mesures de puissance du système, en particulier la mesure de la puissance consommée par la maison
# réalisée par le module PZEM-004t.

import json
import time
import paho.mqtt.client as mqtt

prev_hc = None
prev_hp = None
prev_hc_date = None
prev_hp_date = None

THRESHOLD_LOW = 100
THRESHOLD_ZERO = 50


def debug(indent, msg):
    print((' '*indent)+str(msg))


def now_ts():
    return time.time()


def on_connect(client, userdata, flags, rc):
    debug(0, 'ready')

    client.subscribe("tic/data")


def send_instant_power(client, pe):
    pe = int(round(pe))
    print("power consumption: "+str(pe))
    client.publish('power/edf', str(pe))


def on_message(client, userdata, msg):
    global prev_hc, prev_hc_date, prev_hp, prev_hp_date, current_ps
    if msg.topic == 'tic/data':
        t = now_ts()
        j = json.loads(msg.payload.decode())
        hc = j['hchc']
        hp = j['hchp']
        if prev_hc is None:
            prev_hc = hc
            prev_hp = hp
            prev_hc_date = t
            prev_hp_date = t
        else:
            pe = 0
            min_delay = 8 # do not report a data faster than this delay to increase accuracy with high power
            if hc > prev_hc and (t - prev_hc_date) > min_delay:
                pe += (hc - prev_hc) * 3600.0 / (t - prev_hc_date)
                prev_hc = hc
                prev_hc_date = t
            if hp > prev_hp and (t - prev_hp_date) > min_delay:
                pe += (hp - prev_hp) * 3600.0 / (t - prev_hp_date)
                prev_hp = hp
                prev_hp_date = t

            if pe > 0:
                send_instant_power(client, pe)


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("192.168.1.7", 1883, 120)

    prev_msg_date = now_ts()
    threshold_time = 3600 / THRESHOLD_LOW
    while True:
        client.loop(1)
        if prev_hc_date is not None and prev_hp_date is not None:
            t = now_ts()
            if t - prev_msg_date > 5:
                delta_t = t - max(prev_hc_date, prev_hp_date)
                if delta_t > threshold_time:
                    pe = 3600/delta_t
                    if pe < THRESHOLD_ZERO:
                        pe = 0
                    send_instant_power(client, pe)
                    prev_msg_date = t


if __name__ == '__main__':
    main()
