#!/usr/bin/python3

import sys
import time
import logger
import threading

from tail import *
from wpan import *
from config import *


log = logger.getLogger(__name__)

    
class Anchor(Tail):

    def __init__(self, server, name, eui64, coord, **kwargs):
        Tail.__init__(self,name=name,eui64=eui64,coord=coord)
        self.rpc = server.rpc
        self.server = server
        self.active = False
        self.exit = threading.Event()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()


    def run(self):
        log.debug(f'Anchor {self.name} <{self.eui64}> registered')
        while not self.exit.is_set():
            try:
                self.ping()
                if not self.active:
                    self.activate()
            except:
                if self.active:
                    self.deactivate()
            self.exit.wait(10)

    def stop(self):
        self.exit.set()

    def activate(self):
        log.debug(f'Activating anchor {self.name} <{self.eui64}>')
        self.active = True
        self.reset()

    def deactivate(self):
        log.debug(f'Deactivating anchor {self.name} <{self.eui64}>')
        self.active = False
        
    def ping(self):
        return self.rpc.call(self.eui64, 'PING')

    def rpc_call(self, func, **kwargs):
        if self.active:
            return self.rpc.call(self.eui64, func, **kwargs)
        else:
            raise ConnectionError

    def reset(self):
        return self.rpc_call('RESET')

    def register_tag(self, tag):
       return self.rpc_call('REGISTER', EUI64=tag.eui64)

    def unregister_tag(self, tag):
        return self.rpc_call('UNREGISTER', EUI64=tag.eui64)

    def xmit_frame(self, frame):
        return self.rpc_call('WPAN-XMIT', FRAME=frame.hex())

    def xmit_beacon(self, bref):
        return self.rpc_call('WPAN-BEACON', BREF=bref)

    def get_dtattr(self, attr, format):
        return self.rpc_call('GET_DTATTR', ATTR=attr, FORMAT=format)

    def get_dwattr(self, attr):
        return self.rpc_call('GET_DWATTR', ATTR=attr)

    def set_dwattr(self, attr, value):
        return self.rpc_call('GET_DWATTR', ATTR=attr, VALUE=value)

    def get_dwstat(self, attr):
        return self.rpc_call('GET_DWSTAT', ATTR=attr)

    def get_dwstats(self):
        return self.rpc_call('GET_DWSTATS')

