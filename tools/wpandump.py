#!/usr/bin/python3

import os
import sys
import time
import json
import select
import socket
import argparse

from wpan import *
from dwarf import *


class config:

    dw1000_profile  = None
    dw1000_channel  = 5
    dw1000_pcode    = 12
    dw1000_prf      = 64
    dw1000_rate     = 850
    dw1000_txpsr    = 1024
    dw1000_smart    = 0
    dw1000_power    = '0x88888888'
    dw1000_txlevel  = -12.3


    
def main():

    global WPAN
    
    parser = argparse.ArgumentParser(description="Tail WPAN dump")

    parser.add_argument('-v', '--verbose', action='count', default=0)

    parser.add_argument('--profile', type=str, default=None)
    parser.add_argument('--channel', type=int, default=None)
    parser.add_argument('--pcode', type=int, default=None)
    parser.add_argument('--prf', type=int, default=None)
    parser.add_argument('--rate', type=int, default=None)
    parser.add_argument('--txpsr', type=int, default=None)
    parser.add_argument('--power', type=str, default=None)
    
    args = parser.parse_args()

    if args.profile:
        cfg.dw1000_profile = args.profile
    if args.channel:
        cfg.dw1000_channel = args.channel
    if args.pcode:
        cfg.dw1000_pcode = args.pcode
    if args.prf:
        cfg.dw1000_prf = args.prf
    if args.txpsr:
        cfg.dw1000_txpsr = args.txpsr
    if args.power:
        cfg.dw1000_power = args.power
    if args.rate:
        cfg.dw1000_rate = args.rate

    WPAN = WPANInterface()
    
    WPANFrame.verbose = args.verbose

    WPAN.open()
        
    try:
        WPAN.set_dwattr('channel', config.dw1000_channel)
        WPAN.set_dwattr('pcode', config.dw1000_pcode)
        WPAN.set_dwattr('prf', config.dw1000_prf)
        WPAN.set_dwattr('rate', config.dw1000_rate)
        WPAN.set_dwattr('txpsr', config.dw1000_txpsr)
        WPAN.set_dwattr('smart_power', config.dw1000_smart)
        WPAN.set_dwattr('tx_power', config.dw1000_power)

        if config.dw1000_profile:
            WPAN.set_dwattr('profile', config.dw1000_profile)

        while True:
            frame = WPAN.recvrx()
            print(frame)

    except KeyboardInterrupt:
        log.info('Exiting...')

    WPAN.close()
    

if __name__ == "__main__": main()

