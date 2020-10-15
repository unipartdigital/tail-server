#!/usr/bin/python3

import sys
import time
import math
import socket
import logger


log = logger.getLogger(__name__)


class TailPipe:

    def __init__(self,sock=None):
        self.sock = sock
        self.local = None
        self.remote = None

    def fileno(self):
        if self.sock is not None:
            return self.sock.fileno()
        return None

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def getsaddr(host,port,sock):
        addrs = socket.getaddrinfo(host, port)
        for addr in addrs:
            if addr[1] == sock:
                if addr[0] == socket.AF_INET6:
                    return addr[4]
        for addr in addrs:
            if addr[1] == sock:
                if addr[0] == socket.AF_INET:
                    return addr[4]
        return None


class TCPTailPipe(TailPipe):

    def __init__(self,sock=None):
        TailPipe.__init__(self,sock)
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buff = b''
        
    def getsaddr(host,port):
        return TailPipe.getsaddr(host,port,socket.SOCK_STREAM)
    
    def close(self):
        TailPipe.close(self)
        self.clear()

    def clear(self):
        self.buff = b''

    def recvraw(self):
        data = self.sock.recv(4096)
        if len(data) < 1:
            raise ConnectionResetError
        return data

    def fillbuf(self):
        self.buff += self.recvraw()

    def stripbuf(self):
        while len(self.buff) > 0 and self.buff[0] == 31:
            self.buff = self.buff[1:]
    
    def hasmsg(self):
        self.stripbuf()
        return (self.buff.find(31) > 0)

    def getmsg(self):
        self.stripbuf()
        eom = self.buff.find(31)
        if eom > 0:
            msg = self.buff[0:eom]
            self.buff = self.buff[eom+1:]
            return msg.decode()
        return None

    def getmsgfrom(self):
        return (self.getmsg(),self.remote)
    
    def recvmsg(self):
        while not self.hasmsg():
            self.fillbuf()
        return self.getmsg()

    def recvmsgfrom(self):
        return (self.recvmsg(),self.remote)

    def sendraw(self,data):
        self.sock.sendall(data)

    def sendmsg(self,data):
        self.sendraw(data.encode() + b'\x1f')

    def sendmsgto(self,data,addr):
        raise TypeError

    def connect(self, host, port):
        self.remote = TCPTailPipe.getsaddr(host,port)
        self.sock.connect(self.remote)

    def bind(self,addr,port):
        raise TypeError

    def listen(self,addr,port):
        self.local = (addr,port)
        self.sock.bind(self.local)
        self.sock.listen()
    
    def accept(self):
        (csock,caddr) = self.sock.accept()
        pipe = TCPTailPipe(csock)
        pipe.local = self.local
        pipe.remote = caddr
        return pipe

        
class UDPTailPipe(TailPipe):

    def __init__(self,sock=None):
        TailPipe.__init__(self,sock)
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.buff = []

    def getsaddr(host,port):
        return TailPipe.getsaddr(host,port,socket.SOCK_DGRAM)
    
    def clone(parent):
        pipe = UDPTailPipe(parent.sock)
        pipe.local = parent.local
        pipe.remote = parent.remote
        return pipe
    
    def close(self):
        TailPipe.close(self)
        self.clear()

    def clear(self):
        self.buff = []

    def recvraw(self):
        (data,addr) = self.sock.recvfrom(4096)
        if len(data) < 1:
            raise ConnectionResetError
        return (data,addr)

    def fillbuf(self):
        self.buff.append(self.recvraw())

    def hasmsg(self):
        return bool(self.buff)

    def getmsg(self):
        if self.hasmsg():
            (data,addr) = self.buff.pop(0)
            return data.decode()
        return None
    
    def getmsgfrom(self):
        if self.hasmsg():
            (data,addr) = self.buff.pop(0)
            return (data.decode(),addr)
        return None
    
    def recvmsg(self):
        while not self.hasmsg():
            self.fillbuf()
        return self.getmsg()

    def recvmsgfrom(self):
        while not self.hasmsg():
            self.fillbuf()
        return self.getmsgfrom()

    def sendmsg(self,data):
        self.sock.sendto(data.encode(),self.remote)

    def sendmsgto(self,data,addr):
        self.sock.sendto(data.encode(),addr)

    def connect(self,host,port):
        self.remote = UDPTailPipe.getsaddr(host,port)

    def bind(self,addr,port):
        self.local = (addr,port)
        self.sock.bind(self.local)

    def listen(self,addr,port):
        self.bind(addr,port)

    def accept(self):
        raise TypeError
    

