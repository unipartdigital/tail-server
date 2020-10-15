#!/usr/bin/python3


from logger import *


log = getLogger(__name__)


class Client():

    def __init__(self, pipe):
        self.pipe = pipe
        self.key  = self.pipe.remote
        self.fd   = self.pipe.sock.fileno()

    def sendmsg(self, **args):
        data = json.dumps(args)
        dprint(3, f'Client::sendmsg {data}')
        self.pipe.sendmsg(data)

    def recvmsg(self):
        while self.pipe.hasmsg():
            msg = self.pipe.getmsg()
            dprint(3, f'Client::recvmsg: {msg}')

        
