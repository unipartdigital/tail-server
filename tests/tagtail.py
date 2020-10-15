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
        tag = json.loads(msg.payload.decode())
        print('Tag {} coord:({:.3f},{:.3f})'.format(tag['TAG'], tag['COORD'][0], tag['COORD'][1]))
    
    except Exception as err:
        eprint(f'Error {err}')


def main():

    MQTT = mqtt.Client()

    MQTT.on_message = on_message

    MQTT.connect('schottky.qs.unipart.io', 1883)
    MQTT.subscribe('TAIL/TAG/#', 0)
    MQTT.loop_forever()


if __name__ == "__main__": main()

