#!/usr/bin/python3

import logger
import argparse

import paho.mqtt.client as mqtt

from mqrpc import *


log = logger.getLogger(__name__)


MYUID = 'RPC-TEST-CLIENT'


def main():

    parser = argparse.ArgumentParser(description="Tail RPC test")

    parser.add_argument('-D', '--debug', action='count', default=0)
    parser.add_argument('-L', '--logging', type=str, default=None)
    parser.add_argument('-A', '--anchor', type=str, default='70b3d5b1e0000052')

    args = parser.parse_args()

    logger.initLogger(args.logging)

    remote = args.anchor

    MQTT = mqtt.Client()

    MQTT.enable_logger(log)

    MQTT.connect('schottky.qs.unipart.io', 1883)
    MQTT.loop_start()

    MRPC = MQRPC(MQTT, MYUID)

    data = MRPC.call(remote, 'GETDWSTATS')

    for (key,val) in data.items():
        print(f'{key}: {val}')


    MQTT.disconnect()


if __name__ == "__main__": main()

