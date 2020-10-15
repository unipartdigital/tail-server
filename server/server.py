#!/usr/bin/python3

import os
import sys
import time
import sched
import random
import threading
import json
import socket
import select
import logger
import timer

from config import *
from anchor import *
from mqrpc import *
from event import *
from wpan import *
from tag import *

import paho.mqtt.client as mqtt


log = logger.getLogger(__name__)

log_msg = logger.getLogger('mesg')


class Server():

    def __init__(self):

        WPANFrame.verbose = config.dw1000.verbose

        self.rpcid = config.rtls.mqrpc_id
        self.domain = config.rtls.mqtt_domain
        
        self.tags     = {}
        self.anchors  = {}
        self.rangings = {}
        self.timers   = timer.TimerThread()

        self.mqtt     = mqtt.Client()
        
        self.mqtt.enable_logger(logger.getLogger('mqtt'))

        # Uncomment to see all MQTT callbacks
        #self.mqtt.on_connect      = self.mqtt_on_connect
        #self.mqtt.on_disconnect   = self.mqtt_on_disconnect
        #self.mqtt.on_message      = self.mqtt_on_message
        #self.mqtt.on_publish      = self.mqtt_on_publish
        #self.mqtt.on_subscribe    = self.mqtt_on_subscribe
        #self.mqtt.on_unsubscribe  = self.mqtt_on_unsubscribe

        self.mqtt.connect(config.rtls.mqtt_host, config.rtls.mqtt_port)

        self.mqtt.subscribe(f'TAIL/RF/{self.domain}/#', 0)
        self.mqtt.message_callback_add(f'TAIL/RF/{self.domain}/#', self.mqtt_on_rf_message)
        
        self.rpc = MQRPC(self.mqtt, self.rpcid, 5)

        for arg in config.anchors:
            self.add_anchor(arg)
        
        for arg in config.tags:
            self.add_tag(arg)


    def run(self):
        log.debug(f'starting server')
        self.mqtt.loop_forever()

    def stop(self):
        log.debug(f'stopping server')
        for anchor in self.anchors.values():
            anchor.stop()
        self.rpc.close()
        self.timers.stop()
        self.mqtt.disconnect()


    def add_anchor(self, args):
        log.debug(f'Server::add_anchor {args}')
        dev = Anchor(self, **args)
        self.anchors[dev.eui64] = dev

    def rem_anchor(self, dev):
        log.debug(f'Server::rem_anchor {dev.eui64}')
        self.anchors.pop(dev.eui64, None)

    def get_anchor(self, key):
        return self.anchors[key]

    def get_anchor_by_name(self, name):
        for anc in self.anchors.values():
            if anc.name == name:
                return anc
        return None


    def add_tag(self, args):
        log.debug(f'Server::add_tag {args}')
        dev = Tag(self,**args)
        self.tags[dev.eui64] = dev

    def rem_tag(self, dev):
        log.debug(f'Server::rem_tag {dev.eui64}')
        self.tags.pop(dev.eui64, None)


    def get_tag(self, key):
        return self.tags[key]

    def get_tag_by_name(self, name):
        for tag in self.tags.values():
            if tag.name == name:
                return tag
        return None


    def get_device(self, key):
        if key in self.anchors:
            return self.anchors[key]
        elif key in self.tags:
            return self.tags[key]
        return None


    def get_lat_algo(self, ref):
        algo = config.ranging.algorithm
        if algo == 'wls2d' or algo == 'wls':
            return LatWLS2D(self, ref)
        elif algo == 'wls3d':
            return LatWLS2D(self, ref)
        elif algo == 'swls':
            return LatSWLS(self, ref)
        else:
            raise NotImplementedError


    def get_ranging(self, evnt):
        ref = evnt.get_ranging_ref()
        if ref not in self.rangings:
            self.rangings[ref] = self.get_lat_algo(ref)
            self.rangings[ref].start()
        return self.rangings[ref]

    def finish_ranging(self, rng):
        if rng.rangid in self.rangings:
            del self.rangings[rng.rangid]
    

    def recv_tag_blink(self, evnt):
        rng = self.get_ranging(evnt)
        rng.add_blink(evnt)
    
    def recv_anchor_beacon(self, evnt):
        rng = self.get_ranging(evnt)
        rng.add_beacon(evnt)
        
    def recv_ranging_req(self, evnt):
        rng = self.get_ranging(evnt)
        rng.add_request(evnt)
    
    def recv_ranging_resp(self, evnt):
        rng = self.get_ranging(evnt)
        rng.add_response(evnt)
    
    def recv_rf_msg(self, ANCHOR, DIR, TIMES, FRAME, FINFO):
        dev = self.get_anchor(ANCHOR)
        evt = RFEvent(dev,DIR,TIMES,FRAME,FINFO)
        frm = evt.frame
        if frm.tail_protocol == frm.TAIL_PROTO_STD:
            log_msg.debug(f'{ANCHOR} <{DIR}> {frm}')
            if frm.tail_frmtype == frm.FRAME_TAG_BLINK:
                self.recv_tag_blink(evt)
            elif frm.tail_frmtype == frm.FRAME_ANCHOR_BEACON:
                self.recv_anchor_beacon(evt)
            elif frm.tail_frmtype == frm.FRAME_RANGING_REQUEST:
                self.recv_ranging_req(evt)
            elif frm.tail_frmtype == frm.FRAME_RANGING_RESPONSE:
                self.recv_ranging_resp(evt)
            elif frm.tail_frmtype == frm.FRAME_CONFIG_REQUEST:
                pass
            elif frm.tail_frmtype == frm.FRAME_CONFIG_RESPONSE:
                pass
            else:
                raise NotImplementedError(f'Tail WPAN frame type {frm.tail_frmtype} not implemented')

    
    def mqtt_on_rf_message(self, client, userdata, msg):
        try:
            args = json.loads(msg.payload.decode())
            self.recv_rf_msg(**args)
        except Exception:
            log.exception(f'Unable to handle RF message {msg.payload}')


    def mqtt_publish(self, topic, **args):
        try:
            msg = json.dumps(args).encode()
            self.mqtt.publish(topic,msg)
        except:
            log.exception(f'Unable to send MQTT message')


    def mqtt_on_connect(self, client, userdata, flags, rc):
        log.debug(f'mqtt_on_connect: client:{client} userdata:{userdata} flags:{flags} rc:{rc}')

    def mqtt_on_disconnect(self, client, userdata, rc):
        log.debug(f'mqtt_on_disconnect: client:{client} userdata:{userdata} rc:{rc}')

    def mqtt_on_message(self, client, userdata, msg):
        log.debug(f'mqtt_on_message: client:{client} userdata:{userdata} msg:{msg.topic} {msg.payload} {msg.qos}')

    def mqtt_on_publish(self, client, userdata, mid):
        log.debug(f'mqtt_on_publish: client:{client} userdata:{userdata} mid:{mid}')
        
    def mqtt_on_subscribe(self, client, userdata, mid, qos):
        log.debug(f'mqtt_on_subscribe: client:{client} userdata:{userdata} mid:{mid} qos:{qos}')
        
    def mqtt_on_unsubscribe(self, client, userdata, mid):
        log.debug(f'mqtt_on_unsubscribe: client:{client} userdata:{userdata} mid:{mid}')


