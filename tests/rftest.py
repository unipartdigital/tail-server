#!/usr/bin/python3

import json
import logger
import argparse

import paho.mqtt.client as mqtt

from wpan import *
from logger import *
from pprint import pprint


def on_message(client, userdata, msg):
    try:
        rfmsg = json.loads(msg.payload.decode())
        frame = TailWPANFrame(rfmsg['FRAME'],rfmsg['FINFO'])
        anchor = rfmsg['ANCHOR']
        print(f'Anchor:{anchor}\n{frame}')

    except Exception as err:
        eprint(f'Error {err}')


def main():

    WPANFrame.verbose = 2

    MQTT = mqtt.Client()

    MQTT.on_message = on_message

    MQTT.connect('schottky.qs.unipart.io', 1883)
    MQTT.subscribe('TAIL/RF/#', 0)
    MQTT.loop_forever()



if __name__ == "__main__": main()

