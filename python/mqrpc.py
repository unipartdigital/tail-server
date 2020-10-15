#!/usr/bin/python3

import sys
import time
import json
import uuid
import logger
import threading


log = logger.getLogger(__name__)


class MQRPC:

    def __init__(self, mqtt=None, rpcid=None, timeout=1.0):
        self.mqtt     = mqtt
        self.rpcid    = rpcid
        self.timeout  = timeout
        self.version  = 'MQRPC/1.0'
        self.prefix   = 'TAIL/RPC'
        self.pending  = {}
        self.handler  = {}
        
        self.register('PING', MQRPC.rpc_ping)
        
        self.mqtt.subscribe(f'{self.prefix}/{rpcid}', 0)
        self.mqtt.message_callback_add(f'{self.prefix}/{rpcid}', self.mqtt_on_rpc_message)
        
        self.mqtt.subscribe(f'{self.prefix}/BROADCAST', 0)
        self.mqtt.message_callback_add(f'{self.prefix}/BROADCAST', self.mqtt_on_rpc_message)


    def close(self):
        self.mqtt.unsubscribe(f'{self.prefix}/{self.rpcid}')
        self.mqtt.unsubscribe(f'{self.prefix}/BROADCAST')
        self.mqtt.message_callback_remove(f'{self.prefix}/{self.rpcid}')
        self.mqtt.message_callback_remove(f'{self.prefix}/BROADCAST')


    def mqtt_on_rpc_message(self, client, userdata, msg):
        try:
            rpcmsg = json.loads(msg.payload.decode())
            self.recvrpc(**rpcmsg)
        except Exception:
            log.exception(f'RPC: Invalid MQTT RPC message received: {msg.payload}')
    
    def sendrpc(self, **kwargs):
        kwargs['VER'] = self.version
        topic = '{}/{}'.format(self.prefix, kwargs['DST'])
        data = json.dumps(kwargs).encode()
        self.mqtt.publish(topic, data)
        log.debug(f'sendrpc: {kwargs}')

    def recvrpc(self,SRC,DST,VER,UID,FUNC,ARGS):
        log.debug(f'recvrpc: {SRC} {DST} {VER} {UID} {FUNC} {ARGS}')
        if VER == self.version:
            if FUNC == '__RETURN__':
                if UID in self.pending:
                    self.pending[UID]['args'] = ARGS
                    self.pending[UID]['wait'].set()
            elif FUNC in self.handler:
                RETN = self.handler[FUNC](**ARGS)
                if UID:
                    self.sendrpc(SRC=self.rpcid, DST=SRC, UID=UID, FUNC='__RETURN__', ARGS=RETN)
        else:
            raise SyntaxWarning(f'version mismatch {VER} <> {self.version}')


    def register(self,name,func):
        log.debug(f'register {name} = {func}')
        self.handler[name] = func

    def unregister(self,name):
        log.debug(f'unregister {name}')
        self.handler.pop(name,None)


    def init_call(self):
        uid = str(uuid.uuid4())
        self.pending[uid] = { 'args':None, 'wait':threading.Event() }
        return uid

    def wait_call(self,uid):
        wait = self.pending[uid]['wait'].wait(self.timeout)
        args = self.pending[uid]['args']
        self.pending.pop(uid)
        if not wait:
            raise TimeoutError
        return args

    def call(self,remote,func,**kwargs):
        log.debug(f'call {remote} {func} {kwargs}')
        uid = self.init_call()
        self.sendrpc(SRC=self.rpcid, DST=remote, UID=uid, FUNC=func, ARGS=kwargs)
        args = self.wait_call(uid)
        log.debug(f'call {remote} {func} : {args}')
        return args

    def post(self,remote,func,**kwargs):
        self.sendrpc(SRC=self.rpcid, DST=remote, UID=None, FUNC=func, ARGS=kwargs)

    def bcast(self,remote,func,**kwargs):
        self.sendrpc(SRC=self.rpcid, DST='BROADCAST', UID=None, FUNC=func, ARGS=kwargs)


    def rpc_ping(**kwargs):
        log.debug(f'RPC PING: {kwargs}')
        return kwargs

