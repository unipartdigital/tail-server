#!/usr/bin/python3

import os
import sys
import time
import json
import select
import logger
import hashlib
import argparse

from wpan import *
from dwarf import *
from mqrpc import *
from config import *

import paho.mqtt.client as mqtt



log = logger.getLogger('anchord')

DUID = '0000'
UUID = None
WPAN = None
MQTT = None
MRPC = None

TAGS = {}



def rpc_reset_tags():
    for key in list(TAGS.keys()):
        TAGS.pop(key)

def rpc_register_tag(EUI64):
    TAGS[EUI64] = { 'EUI64':EUI64, 'time':time.time(), }

def rpc_unregister_tag(EUI64):
    TAGS.pop(EUI64, None)

def rpc_get_dtattr(ATTR, FORMAT):
    return WPAN.get_dtattr(ATTR,FORMAT)

def rpc_get_dwstat(ATTR):
    return WPAN.get_dwstats(ATTR)

def rpc_get_dwstats():
    return { key:WPAN.get_dwstats(key) for key in WPAN.DW1000_STATS }

def rpc_get_dwattr(ATTR):
    return WPAN.get_dwattr(ATTR)

def rpc_set_dwattr(ATTR, VALUE):
    WPAN.set_dwattr(ATTR, VALUE)
    return WPAN.get_dwattr(ATTR)

def rpc_get_dwconfig():
    return { key:WPAN.get_dwattr(key) for key in ('channel','pcode','prf','rate','txpsr','tx_power') }

def wpan_xmit_frame(FRAME):
    WPAN.send(frame)

def make_ranging_ref(addr, seq):
    md5 = hashlib.md5()
    msg = struct.pack('8sB', addr, seq&0xff)
    md5.update(msg)
    ref =  md5.digest()
    return ref[:8]

def wpan_xmit_beacon(BREF, SUB=0, FLAGS=0):
    frame = WPAN.Frame()
    frame.set_src_addr(WPAN.if_laddr)
    frame.set_dst_addr(WPAN.BCAST_ADDR)
    frame.tail_protocol = frame.TAIL_PROTO_STD
    frame.tail_frmtype  = frame.FRAME_ANCHOR_BEACON
    frame.tail_subtype  = SUB
    frame.tail_flags    = FLAGS
    frame.tail_beacon   = BREF
    WPAN.send(frame)


def send_mqtt_rf_msg(**kwargs):
    data = json.dumps(kwargs).encode()
    MQTT.publish(f'TAIL/RF/{DUID}/{UUID}', data)


def frame_times(frame):
    if frame.timestamp:
        swts = int(frame.timestamp.sw)
        hwts = int(frame.timestamp.hw)
        hres = int(frame.timestamp.hires)
    else:
        swts = 0
        hwts = 0
        hres = 0
    if hwts == 0 or hres == 0:
        log.error(f'Invalid WPAN frame timestamp: {frame}')
    return { 'sw':swts, 'hw':hwts, 'hi':hres }


def recv_wpan_rx():
    frame = WPAN.recvrx()
    log.debug(f'recv_wpan_rx: {frame}')
    if frame.tail_protocol == frame.TAIL_PROTO_STD:
        send_mqtt_rf_msg(ANCHOR=UUID, DIR='RX', TIMES=frame_times(frame), FRAME=frame.hex(), FINFO=frame.timestamp.hex())
        if frame.tail_frmtype == frame.FRAME_TAG_BLINK:
            src = frame.get_src_eui()
            if src in TAGS:
                tag = frame.src_addr
                seq = frame.frame_seqnum
                ref = make_ranging_ref(tag,seq)
                wpan_xmit_beacon(ref)

def recv_wpan_tx():
    frame = WPAN.recvtx()
    log.debug(f'recv_wpan_tx: {frame}')
    if frame.tail_protocol == frame.TAIL_PROTO_STD:
        send_mqtt_rf_msg(ANCHOR=UUID, DIR='TX', TIMES=frame_times(frame), FRAME=frame.hex(), FINFO=frame.timestamp.hex())


def socket_loop():

    WPAN.open()

    wait = select.poll()
    wait.register(WPAN.if_sock, select.POLLIN)

    while True:
        for (fd,flags) in wait.poll(100):
            try:
                if flags & select.POLLIN:
                    recv_wpan_rx()
                if flags & select.POLLERR:
                    recv_wpan_tx()

            except OSError:
                log.exception('I/O error')
                break
                
            except Exception:
                log.exception('socket_loop error')
    
    WPAN.close()


    
def main():

    global UUID, DUID, MQTT, WPAN, MRPC
    
    parser = argparse.ArgumentParser(description="Tail Anchor Daemon")

    parser.add_argument('-L', '--logging', type=str, default=None)
    parser.add_argument('-c', '--config', type=str, default=None)

    args = parser.parse_args()

    if args.config:
        config.loadYAML(args.config)

    logger.initLogger(args.logging)

    WPAN = WPANInterface()
    UUID = WPAN.EUI64()
    DUID = config.anchor.mqtt_domain
    MQTT = mqtt.Client()
    
    MQTT.enable_logger(logger.getLogger('MQTT'))
    MQTT.connect(config.anchor.mqtt_host, config.anchor.mqtt_port)
    MQTT.loop_start()

    MRPC = MQRPC(MQTT,UUID)
    
    MRPC.register('GETDWSTAT', rpc_get_dwstat)
    MRPC.register('GETDWSTATS', rpc_get_dwstats)
    MRPC.register('GETDTATTR', rpc_get_dtattr)
    MRPC.register('GETDWATTR', rpc_get_dwattr)
    MRPC.register('SETDWATTR', rpc_set_dwattr)
    MRPC.register('GETDWCONFIG', rpc_get_dwconfig)
    
    MRPC.register('RESET', rpc_reset_tags)
    MRPC.register('REGISTER', rpc_register_tag)
    MRPC.register('UNREGISTER', rpc_unregister_tag)

    MRPC.register('WPAN-XMIT', wpan_xmit_frame)
    MRPC.register('WPAN-BEACON', wpan_xmit_beacon)

    
    log.info(f'Tail Anchor <{UUID}> daemon starting...') 
   
    WPANFrame.verbose = config.dw1000.verbose

    try:
        WPAN.set_dwattr('channel', config.dw1000.channel)
        WPAN.set_dwattr('pcode', config.dw1000.pcode)
        WPAN.set_dwattr('prf', config.dw1000.prf)
        WPAN.set_dwattr('rate', config.dw1000.rate)
        WPAN.set_dwattr('txpsr', config.dw1000.txpsr)
        WPAN.set_dwattr('smart_power', config.dw1000.smart)
        WPAN.set_dwattr('tx_power', config.dw1000.power)

        if config.dw1000.profile:
            WPAN.set_dwattr('profile', config.dw1000.profile)

        socket_loop()

    except KeyboardInterrupt:
        log.info('Exiting...')

    
    MRPC.close()
    MQTT.disconnect()
    


if __name__ == "__main__": main()

