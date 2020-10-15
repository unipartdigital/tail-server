#!/usr/bin/python3

import os
import sys
import time
import math
import ctypes
import struct
import socket
import logger
import netifaces

from ctypes import *


log = logger.getLogger(__name__)


##
## Pretty printing data dumps
##

def _dump_list(data,level,indent,keylen):
    ret = ''
    for item in data:
        ret += _dump_pair(item,level,indent,keylen)
    return ret

def _dump_pair(data,level,indent,keylen):
    (key,val) = data
    res = (indent*level)*' ' + str(key).ljust(keylen - indent*level) 
    if isinstance(val,list):
        res += ':\n'
        res += _dump_list(val,level+1,indent,keylen)
    else:
        res += f': {val}\n'
    return res

def prettydump(data,level=0,indent=2,keylen=0):
    return _dump_list(data,level,indent,keylen)


def _dump_list_simple(data):
    ret = ''
    for item in data:
        ret += _dump_pair_simple(item)
    return ret

def _dump_pair_simple(data):
    (key,val) = data
    res = f' {key}'
    if isinstance(val,list):
        res += ': [' + _dump_list_simple(val) + ' ]'
    else:
        res += f': {val}'
    return res

def simpledump(data):
    return _dump_list_simple(data)



##
## Kernel interface data structures
##

class Timespec(Structure):

    _fields_ = [("tv_sec", c_uint32),
                ("tv_nsec", c_uint32)]

    def __int__(self):
        return (self.tv_sec * 1000000000 + self.tv_nsec)

    def __float__(self):
        return float(int(self))

    def __str__(self):
        return '0x{:x}'.format(int(self))

    def __bool__(self):
        return bool(self.tv_sec or self.tv_nsec)

    def __iter__(self):
        return ((x[0], getattr(self,x[0])) for x in self._fields_)

    def __dump__(self):
        return str(self)

    def bytes(self):
        return bytes(self)
    
    def hex(self):
        return self.bytes().hex()

    def dict(self):
        return dict(self)
    

class Timehires(Structure):

    _fields_ = [
        ("tv_nsec", c_uint64),
        ("tv_frac", c_uint32),
        ("__res", c_uint32) ]

    def __int__(self):
        return ((self.tv_nsec << 32) | self.tv_frac)

    def __float__(self):
        return (float(self.tv_nsec) + self.tv_frac/4294967296)

    def __str__(self):
        return '0x{:x}.{:08x}'.format(self.tv_nsec,self.tv_frac)

    def __bool__(self):
        return bool(self.tv_nsec or self.tv_frac)

    def __iter__(self):
        return ((x[0], getattr(self,x[0])) for x in self._fields_)

    def __dump__(self):
        return str(self)

    def bytes(self):
        return bytes(self)
    
    def hex(self):
        return self.bytes().hex()
    
    def dict(self):
        return dict(self)
    

class TimestampInfo(Structure):

    _fields_ = [
        ("rawts", c_uint64),
        ("lqi", c_uint16),
        ("snr", c_uint16),
        ("fpr", c_uint16),
        ("noise", c_uint16),
        ("rxpacc", c_uint16),
        ("fp_index", c_uint16),
        ("fp_ampl1", c_uint16),
        ("fp_ampl2", c_uint16),
        ("fp_ampl3", c_uint16),
        ("cir_pwr", c_uint32),
        ("fp_pwr", c_uint32),
        ("ttcko", c_uint32),
        ("ttcki", c_uint32),
        ("temp", c_int16),
        ("volt", c_int16),
    ]

    def __iter__(self):
        return ((x[0], getattr(self,x[0])) for x in self._fields_)

    def __dump__(self):
        return list(self.__iter__())
        
    def bytes(self):
        return bytes(self)
    
    def hex(self):
        return self.bytes().hex()

    def dict(self):
        return dict(self)
    

class Timestamp(Structure):

    _fields_ = [
        ("sw", Timespec),
        ("legacy", Timespec),
        ("hw", Timespec),
        ("hires", Timehires),
        ("tsinfo", TimestampInfo),
    ]

    def __iter__(self):
        return ((x[0], getattr(self,x[0])) for x in self._fields_)

    def __dump__(self):
        return [
            ('sw', self.sw.__dump__()),
            ('hw', self.hw.__dump__()),
            ('hr', self.hires.__dump__()),
            ('ts', self.tsinfo.__dump__()),
        ]

    def bytes(self):
        return bytes(self)
    
    def hex(self):
        return self.bytes().hex()

    def dict(self):
        return dict(self)
    


##
## Support functions
##

def _byteswap(data):
    return bytes(reversed(tuple(data)))

def _bit(pos):
    return (1<<pos)

def _testbit(data,pos):
    return bool(data & _bit(pos))

def _getbits(data,pos,cnt):
    return (data>>pos) & ((1<<cnt)-1)

def _makebits(data,pos,cnt):
    return (data & ((1<<cnt)-1)) << pos


def isEUI64(addr):
    return (type(addr) is bytes) and (len(addr) == 8) and (addr != 8 * b'\xff')



##
## 802.15.4 WPAN Interface
##

class WPANInterface:

    BCAST_ADDR = 0xffff

    DW1000_SYSFS_DT     = '/sys/devices/platform/soc/3f204000.spi/spi_master/spi0/spi0.0/of_node/'
    DW1000_SYSFS_CONF   = '/sys/devices/platform/soc/3f204000.spi/spi_master/spi0/spi0.0/dw1000/'
    DW1000_SYSFS_STATS  = '/sys/devices/platform/soc/3f204000.spi/spi_master/spi0/spi0.0/statistics/'

    DW1000_STATS  = (
        'dw1000_rx_error',
        'dw1000_rx_fcg',
        'dw1000_rx_frame',
        'dw1000_rx_ovrr',
        'dw1000_rx_ldedone',
        'dw1000_rx_kpi_error',
        'dw1000_rx_stamp_error',
        'dw1000_rx_frame_rep',
        'dw1000_rx_reset',
        'dw1000_tx_error',
        'dw1000_rx_dfr',
        'dw1000_rx_hsrbp',
        'dw1000_rx_resync',
        'dw1000_tx_frame',
        'dw1000_tx_retry',
        'dw1000_spi_error',
        'dw1000_snr_reject',
        'dw1000_fpr_reject',
        'dw1000_noise_reject',
        'dw1000_irq_count',
        'dw1000_hard_reset',
    )

    
    def __init__(self):
        self.if_name   = 'wpan0'
        self.if_hwaddr = netifaces.ifaddresses(self.if_name)[netifaces.AF_LINK][0]['addr']
        self.if_eui64  = self.if_hwaddr.replace(':','')
        self.if_laddr  = bytes.fromhex(self.if_eui64)
        self.if_saddr  = None
        self.if_sock   = None
        self.if_dsn    = 0


    def EUI64(self):
        return self.if_eui64

    def Frame(self,data=None,ancl=None):
        return TailWPANFrame(data,ancl,self)

    def getDSN(self):
        self.if_dsn = (self.if_dsn + 1) & 0xff
        return self.if_dsn


    def get_dwstats(self,attr):
        if os.path.isfile(self.DW1000_SYSFS_STATS + attr):
            with open(self.DW1000_SYSFS_STATS + attr, 'r') as f:
                value = f.read()
                return value.rstrip()
        return None

    def set_dwattr(self,attr, data):
        if os.path.isfile(self.DW1000_SYSFS_CONF + attr):
            with open(self.DW1000_SYSFS_CONF + attr, 'w') as f:
                f.write(str(data))

    def get_dwattr(self,attr):
        if os.path.isfile(self.DW1000_SYSFS_CONF + attr):
            with open(self.DW1000_SYSFS_CONF + attr, 'r') as f:
                value = f.read()
                return value.rstrip()
        return None

    def get_dtattr_raw(self,attr):
        if os.path.isfile(self.DW1000_SYSFS_DT + attr):
            with open(self.DW1000_SYSFS_DT + attr, 'rb') as f:
                data = f.read()
                return data
        return None

    def get_dtattr_str(self,attr):
        if os.path.isfile(self.DW1000_SYSFS_DT + attr):
            with open(self.DW1000_SYSFS_DT + attr, 'r') as f:
                data = f.read()
                return data.rstrip('\n\r\0')
        return None

    def get_dtattr_format(self, attr, form):
        if os.path.isfile(self.DW1000_SYSDT + attr):
            with open(self.DW1000_SYSFS_DT + attr, 'rb') as f:
                data = f.read()
                return struct.unpack(form, data)
        return []

        
    def open(self):
        self.if_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.PROTO_IEEE802154)
        self.if_sock.setsockopt(socket.SOL_SOCKET, socket.SO_TIMESTAMPING,
                                socket.SOF_TIMESTAMPING_RAW_HARDWARE |
                                socket.SOF_TIMESTAMPING_RX_HARDWARE |
                                socket.SOF_TIMESTAMPING_TX_HARDWARE |
                                socket.SOF_TIMESTAMPING_SOFTWARE |
                                socket.SOF_TIMESTAMPING_RX_SOFTWARE)
        self.if_sock.bind((self.if_name,0))
    
    def close(self):
        self.if_sock.close()
        self.if_sock = None

    def send(self,frame):
        if type(frame) is bytes:
            self.sendmsg(frame)
        elif type(frame) is str:
            self.sendmsg(bytes.fromhex(frame))
        else:
            self.sendmsg(frame.encode())
        
    def recvrx(self):
        (data,ancl,_,_) = self.recvmsg()
        return self.Frame(data,ancl)
    
    def recvtx(self):
        (data,ancl,_,_) = self.recverrmsg()
        return self.Frame(data,ancl)
    
    def sendmsg(self,data):
        self.if_sock.send(data)

    def recvmsg(self):
        return self.if_sock.recvmsg(4096,1024,0)

    def recverrmsg(self):
        return self.if_sock.recvmsg(4096,1024,socket.MSG_ERRQUEUE)

    def match_addr(self,addr):
        return (addr == self.if_laddr) or (addr == self.if_saddr)

    def match_bcast(self,addr):
        return (addr == 2 * b'\xff') or (addr == 8 * b'\xff')
    
    def match_local(self,addr):
        return self.match_addr(addr) or self.match_bcast(addr)



##
## 802.15.4 Frame Format
##

class WPANFrame:

    BCAST_ADDR = 0xffff

    ADDR_NONE  = 0
    ADDR_SHORT = 2
    ADDR_EUI64 = 3

    dmp_indent = 2
    dmp_keylen = 20

    verbose    = 0
    

    def __init__(self, data=None, ancl=None, iface=None):
    
        self.iface          = iface

        self.frame          = None
        self.frame_len      = 0
        self.frame_control  = None
        self.frame_type     = 1
        self.frame_version  = 1
        self.frame_seqnum   = None
        
        self.header_len     = 0
        self.security       = False
        self.pending        = False
        self.ack_req        = False
        self.panid_comp     = True
        
        self.dst_mode       = 0
        self.dst_addr       = None
        self.dst_panid      = 0xffff
        
        self.src_mode       = 0
        self.src_addr       = None
        self.src_panid      = 0xffff

        self.timestamp      = Timestamp()

        if data is not None:
            self.decode(data)
        if ancl is not None:
            self.decode_ancl(ancl)


    def hex(self):
        if self.frame:
            return self.frame.hex()
        else:
            return None
    
    def get_src_eui(self):
        if self.src_mode == WPANFrame.ADDR_EUI64:
            return self.src_addr.hex()
        return None
            
    def get_dst_eui(self):
        if self.dst_mode == WPANFrame.ADDR_EUI64:
            return self.dst_addr.hex()
        return None

    def get_peer_eui(self):
        if self.iface:
            if self.iface.match_local(self.dst_addr) and isEUI64(self.src_addr):
                return self.src_addr.hex()
            if self.iface.match_local(self.src_addr) and isEUI64(self.dst_addr):
                return self.dst_addr.hex()
        return None

    def set_src_addr(self,addr):
        if addr is None:
            self.src_mode = WPANFrame.ADDR_NONE
            self.src_addr = None
        elif type(addr) is int:
            self.src_mode = WPANFrame.ADDR_SHORT
            self.src_addr = struct.pack('<H',addr)
        elif type(addr) is bytes:
            if len(addr) == 2:
                self.src_addr = addr
                self.src_mode = WPANFrame.ADDR_SHORT
            elif len(addr) == 8:
                self.src_addr = addr
                self.src_mode = WPANFrame.ADDR_EUI64
            else:
                raise ValueError
        elif type(addr) is str:
            if len(addr) == 4:
                self.src_addr = bytes.fromhex(addr)
                self.src_mode = WPANFrame.ADDR_SHORT
            elif len(addr) == 16:
                self.src_addr = bytes.fromhex(addr)
                self.src_mode = WPANFrame.ADDR_EUI64
            else:
                raise ValueError
        else:
            raise ValueError
            
    def set_src_panid(self,panid):
        if type(panid) is int:
            self.src_panid = panid
        elif type(panid) is bytes and len(addr) == 2:
            self.src_panid = struct.pack('<H',panid)
        else:
            raise ValueError
            
    def set_dst_addr(self,addr):
        if addr is None:
            self.dst_mode = WPANFrame.ADDR_NONE
            self.dst_addr = None
        elif type(addr) is int:
            self.dst_mode = WPANFrame.ADDR_SHORT
            self.dst_addr = struct.pack('<H',addr)
        elif type(addr) is bytes:
            if len(addr) == 2:
                self.dst_addr = addr
                self.dst_mode = WPANFrame.ADDR_SHORT
            elif len(addr) == 8:
                self.dst_addr = addr
                self.dst_mode = WPANFrame.ADDR_EUI64
            else:
                raise ValueError
        elif type(addr) is str:
            if len(addr) == 4:
                self.dst_addr = bytes.fromhex(addr)
                self.dst_mode = WPANFrame.ADDR_SHORT
            elif len(addr) == 16:
                self.dst_addr = bytes.fromhex(addr)
                self.dst_mode = WPANFrame.ADDR_EUI64
            else:
                raise ValueError
        else:
            raise ValueError
            
    def set_dst_panid(self,panid):
        if type(panid) is int:
            self.dst_panid = panid
        elif type(panid) is bytes and len(addr) == 2:
            self.dst_panid = struct.pack('<H',panid)
        else:
            raise ValueError

    def decode_ancl(self,data):
        if type(data) is bytes:
            self.decode_rawts(data)
        elif type(data) is str:
            self.decode_rawts(bytes.fromhex(data))
        elif type(data) is list:
            self.decode_ancl_list(data)
        else:
            raise TypeError(f'Invalid Timestamp type {type(data)}')
    
    def decode_rawts(self,data):
        raw = data.ljust(sizeof(Timestamp), b'\0')
        self.timestamp = Timestamp.from_buffer_copy(raw)

    def decode_ancl_list(self,ancl):
        for cmsg_level, cmsg_type, cmsg_data in ancl:
            if (cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SO_TIMESTAMPING):
                self.decode_rawts(cmsg_data)

    def decode(self,data):
        if type(data) is str:
            data = bytes.fromhex(data)
        elif type(data) is not bytes:
            raise ValueError('Invalid data format')
        ptr = 0
        self.frame = data
        self.frame_len = len(data)
        (fc,sq) = struct.unpack_from('<HB',data,ptr)
        ptr += 3
        self.frame_control = fc
        self.frame_seqnum = sq
        self.frame_type = _getbits(fc,0,3)
        self.frame_version = _getbits(fc,12,2)
        self.security = _testbit(fc,3)
        self.pending = _testbit(fc,4)
        self.ack_req = _testbit(fc,5)
        self.dst_mode = _getbits(fc,10,2)
        self.src_mode = _getbits(fc,14,2)
        self.panid_comp = _testbit(fc,6)
        if self.dst_mode != 0:
            (panid,) = struct.unpack_from('<H',data,ptr)
            self.dst_panid = panid
            ptr += 2
            if self.dst_mode == self.ADDR_SHORT:
                (addr,) = struct.unpack_from('2s',data,ptr)
                self.dst_addr = _byteswap(addr)
                ptr += 2
            elif self.dst_mode == self.ADDR_EUI64:
                (addr,) = struct.unpack_from('8s',data,ptr)
                self.dst_addr = _byteswap(addr)
                ptr += 8
        else:
            self.dst_panid = None
            self.dst_addr  = None
        if self.src_mode != 0:
            if self.panid_comp:
                self.src_panid = self.dst_panid
            else:
                (panid,) = struct.unpack_from('<H',data,ptr)
                self.src_panid = panid
                ptr += 2
            if self.src_mode == self.ADDR_SHORT:
                (addr,) = struct.unpack_from('2s',data,ptr)
                self.src_addr = _byteswap(addr)
                ptr += 2
            elif self.src_mode == self.ADDR_EUI64:
                (addr,) = struct.unpack_from('8s',data,ptr)
                self.src_addr = _byteswap(addr)
                ptr += 8
        else:
            self.src_panid = None
            self.src_addr  = None
        if self.security:
            raise NotImplementedError('decode WPAN security')
        self.header_len = ptr
        return ptr
            
    def encode(self):
        if self.frame_control is None:
            fc = self.frame_type & 0x07
            if self.security:
                fc |= _bit(3)
            if self.pending:
                fc |= _bit(4)
            if self.ack_req:
                fc |= _bit(5)
            if self.panid_comp and (self.src_panid == self.dst_panid):
                fc |= _bit(6)
            fc |= _makebits(self.dst_mode,10,2)
            fc |= _makebits(self.src_mode,14,2)
            fc |= _makebits(self.frame_version,12,2)
            self.frame_control = fc
        if self.frame_seqnum is None:
            if self.iface:
                self.frame_seqnum = self.iface.getDSN()
        data = struct.pack('<HB', self.frame_control, self.frame_seqnum)
        if self.dst_mode != 0:
            data += struct.pack('<H',self.dst_panid)
            if self.dst_mode == self.ADDR_SHORT:
                data += struct.pack('2s',_byteswap(self.dst_addr))
            elif self.dst_mode == self.ADDR_EUI64:
                data += struct.pack('8s',_byteswap(self.dst_addr))
        if self.src_mode != 0:
            if not (self.panid_comp and (self.src_panid == self.dst_panid)):
                data += struct.pack('<H', self.src_panid)
            if self.src_mode == self.ADDR_SHORT:
                data += struct.pack('2s', _byteswap(self.src_addr))
            elif self.src_mode == self.ADDR_EUI64:
                data += struct.pack('8s', _byteswap(self.src_addr))
        if self.security:
            raise NotImplementedError('encode WPAN security')
        self.header_len = len(data)
        self.frame = data
        return data

    def __dump__(self):
        res = []
        dmp = []
        if self.verbose == 0:
            dmp += [
                ('Len', self.frame_len),
                ('Seq', self.frame_seqnum),
                ('Src', self.src_addr.hex()),
                ('Dst', self.dst_addr.hex()) ]
            res.append(('WPAN Frame', dmp))
        else:
            if self.verbose > 1:
                dmp.append(('Payload', self.frame.hex()))
            dmp += [
                ('Length', self.frame_len),
                ('Control', f'0x{self.frame_control:04x}'),
                ('Type', self.frame_type),
                ('Version', self.frame_version),
                ('Security', self.security),
                ('Pending', self.pending),
                ('AckReq', self.ack_req),
                ('DstMode', self.dst_mode),
                ('SrcMode', self.src_mode),
                ('PanIDComp', self.panid_comp),
                ('SequenceNr', self.frame_seqnum),
                ('SrcAddr', self.src_addr.hex()),
                ('SrcPanID', f'{self.src_panid:04x}'),
                ('DstAddr', self.dst_addr.hex()),
                ('DstPanID', f'{self.dst_panid:04x}') ]
            if self.verbose > 1 and self.timestamp:
                res.append(('Timestamp', self.timestamp.__dump__()))
            res.append(('WPAN Frame', dmp))
        return res

    def __str__(self):
        if self.verbose == 0:
            return simpledump(self.__dump__())
        else:
            return prettydump(self.__dump__(),0,WPANFrame.dmp_indent,WPANFrame.dmp_keylen)




##
## Tail data format
##

def _int8(x):
    x = int(x) & 0xff
    if x > 127:
        x -= 256
    return x

def _int16(x):
    x = int(x) & 0xffff
    if x > 32767:
        x -= 65536
    return x


class TailWPANFrame(WPANFrame):

    TAIL_MAGIC_STD         = 0x37
    TAIL_MAGIC_ENC         = 0x38

    TAIL_PROTO_NONE        = 0
    TAIL_PROTO_STD         = 1
    TAIL_PROTO_ENC         = 2

    FRAME_TAG_BLINK        = 0
    FRAME_ANCHOR_BEACON    = 1
    FRAME_RANGING_REQUEST  = 2
    FRAME_RANGING_RESPONSE = 3
    FRAME_CONFIG_REQUEST   = 4
    FRAME_CONFIG_RESPONSE  = 5
    FRAME_ANCHOR_AUX       = 15

    CONFIG_RESET           = 0
    CONFIG_ENUMERATE       = 1
    CONFIG_READ            = 2
    CONFIG_WRITE           = 3
    CONFIG_DELETE          = 4
    CONFIG_SALT            = 5
    CONFIG_TEST            = 15

    IE_KEYS =  {
        0x00 : 'Batt',
        0x01 : 'Vreg',
        0x02 : 'Temp',
        0x40 : 'Vbatt',
        0x80 : 'Blinks',
        0xff : 'Debug',
    }

    IE_CONV =  {
        0x01 : lambda x: round(_int8(x)/173+3.300, 3),
        0x02 : lambda x: round(_int8(x)/1.14+23.0, 2),
        0x40 : lambda x: round(x*5/32768, 3),
    }

    def __init__(self, data=None, ancl=None, iface=None):
        WPANFrame.__init__(self,iface=iface)
        self.tail_protocol  = self.TAIL_PROTO_NONE
        self.tail_payload   = None
        self.tail_listen    = False
        self.tail_accel     = False
        self.tail_dcin      = False
        self.tail_salt      = False
        self.tail_timing    = False
        self.tail_frmtype   = None
        self.tail_subtype   = None
        self.tail_txtime    = None
        self.tail_rxtime    = None
        self.tail_rxtimes   = None
        self.tail_rxinfo    = None
        self.tail_rxinfos   = None
        self.tail_cookie    = None
        self.tail_beacon    = None
        self.tail_flags     = None
        self.tail_code      = None
        self.tail_test      = None
        self.tail_ies       = None
        self.tail_eies      = None
        self.tail_config    = None
        
        if data is not None:
            self.decode(data)
        if ancl is not None:
            self.decode_ancl(ancl)


    def get_beacon_ref(self):
        if self.tail_protocol == self.FRAME_ANCHOR_BEACON:
            return self.tail_beacon
        else:
            return None

    
    def tsdecode(data):
        times = struct.unpack_from('<Q', data.ljust(8, b'\0'))[0]
        return times

    def tsencode(times):
        data = struct.pack('<Q',times)[0:5]
        return data

    def decode(self,data):
        if type(data) is str:
            data = bytes.fromhex(data)
        elif type(data) is not bytes:
            raise ValueError('Invalid data format')
        ptr = WPANFrame.decode(self,data)
        (magic,) = struct.unpack_from('<B',data,ptr)
        ptr += 1
        if magic == TailWPANFrame.TAIL_MAGIC_STD:
            self.tail_protocol = self.TAIL_PROTO_STD
            self.tail_payload = data[ptr:]
            (frame,) = struct.unpack_from('<B',data,ptr)
            ptr += 1
            self.tail_frmtype = _getbits(frame,4,4)
            self.tail_subtype = _getbits(frame,0,4)
            if self.tail_frmtype == self.FRAME_TAG_BLINK:
                self.tail_eies_present   = _testbit(frame,1)
                self.tail_ies_present    = _testbit(frame,2)
                self.tail_cookie_present = _testbit(frame,3)
                (flags,) = struct.unpack_from('<B',data,ptr)
                ptr += 1
                self.tail_flags  = flags
                self.tail_listen = _testbit(flags,7)
                self.tail_accel  = _testbit(flags,6)
                self.tail_dcin   = _testbit(flags,5)
                self.tail_salt   = _testbit(flags,4)
                if self.tail_cookie_present:
                    (cookie,) = struct.unpack_from('16s',data,ptr)
                    ptr += 16
                    self.tail_cookie = cookie
                if self.tail_ies_present:
                    (iec,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    self.tail_ies = {}
                    for i in range(iec):
                        (id,) = struct.unpack_from('<B',data,ptr)
                        ptr += 1
                        idf = _getbits(id,6,2)
                        if idf == 0:
                            (val,) = struct.unpack_from('<B',data,ptr)
                            ptr += 1
                        elif idf == 1:
                            (val,) = struct.unpack_from('<H',data,ptr)
                            ptr += 2
                        elif idf == 2:
                            (val,) = struct.unpack_from('<I',data,ptr)
                            ptr += 4
                        else:
                            (val,) = struct.unpack_from('<p',data,ptr)
                            ptr += len(val) + 1
                        if id in TailWPANFrame.IE_CONV:
                            val = TailWPANFrame.IE_CONV[id](val)
                        if id in TailWPANFrame.IE_KEYS:
                            self.tail_ies[TailWPANFrame.IE_KEYS[id]] = val
                        else:
                            self.tail_ies['IE{:02X}'.format(id)] = val
                if self.tail_eies_present:
                    raise NotImplementedError('decode tail EIEs')
            elif self.tail_frmtype == self.FRAME_ANCHOR_BEACON:
                (flags,) = struct.unpack_from('<B',data,ptr)
                ptr += 1
                self.tail_flags = flags
                (ref,) = struct.unpack_from('8s',data,ptr)
                self.tail_beacon = _byteswap(ref)
                ptr += 8
            elif self.tail_frmtype == self.FRAME_RANGING_REQUEST:
                raise NotImplementedError('decode tail ranging request')
            elif self.tail_frmtype == self.FRAME_RANGING_RESPONSE:
                self.tail_owr = _testbit(self.tail_subtype,3)
                (txtime,) = struct.unpack_from('5s',data,ptr)
                ptr += 5
                self.tail_txtime = TailWPANFrame.tsdecode(txtime)
                if not self.tail_owr:
                    (cnt,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    bits = 0
                    self.tail_rxtimes = {}
                    for i in range(0,cnt,8):
                        (val,) = struct.unpack_from('<B',data,ptr)
                        ptr += 1
                        bits |= val << i
                    for i in range(cnt):
                        if _testbit(bits,i):
                            (addr,) = struct.unpack_from('8s',data,ptr)
                            ptr += 8
                        else:
                            (addr,) = struct.unpack_from('2s',data,ptr)
                            ptr += 2
                        (rxdata,) = struct.unpack_from('5s',data,ptr)
                        ptr += 5
                        rxtime = TailWPANFrame.tsdecode(rxdata)
                        self.tail_rxtimes[_byteswap(addr)] = rxtime
                        if WPANFrame.match_if(_byteswap(addr)):
                            self.tail_rxtime = rxtime
            elif self.tail_frmtype == self.FRAME_CONFIG_REQUEST:
                if self.tail_subtype == self.CONFIG_RESET:
                    (magic,) = struct.unpack_from('<H',data,ptr)
                    ptr += 2
                    self.tail_reset_magic = magic
                elif self.tail_subtype == self.CONFIG_ENUMERATE:
                    (iter,) = struct.unpack_from('<H',data,ptr)
                    ptr += 1
                    self.tail_iterator = iter
                elif self.tail_subtype == self.CONFIG_READ:
                    (cnt,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    self.tail_config = {}
                    for i in range(cnt):
                        (key,) = struct.unpack_from('<H',data,ptr)
                        ptr += 2
                        self.tail_config[key] = None
                elif self.tail_subtype == self.CONFIG_WRITE:
                    (cnt,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    self.tail_config = {}
                    for i in range(cnt):
                        (key,) = struct.unpack_from('<H',data,ptr)
                        ptr += 2
                        (val,) = struct.unpack_from('<p',data,ptr)
                        ptr += len(val) + 1
                        self.tail_config[key] = val
                elif self.tail_subtype == self.CONFIG_DELETE:
                    (cnt,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    self.tail_config = {}
                    for i in range(cnt):
                        (key,) = struct.unpack_from('<H',data,ptr)
                        ptr += 2
                        self.tail_config[key] = None
                elif self.tail_subtype == self.CONFIG_SALT:
                    (salt,) = struct.unpack_from('<16s',data,ptr)
                    ptr += 16
                    self.tail_salt = salt
                elif self.tail_subtype == self.CONFIG_TEST:
                    (test,) = struct.unpack_from('<p',data,ptr)
                    ptr += len(test) + 1
                    self.tail_test = test
                else:
                    raise NotImplementedError('decode config request: {}'.format(self.tail_subtype))
            elif self.tail_frmtype == self.FRAME_CONFIG_RESPONSE:
                if self.tail_subtype == self.CONFIG_RESET:
                    (magic,) = struct.unpack_from('<H',data,ptr)
                    ptr += 2
                elif self.tail_subtype == self.CONFIG_ENUMERATE:
                    (iter,cnt,) = struct.unpack_from('<HB',data,ptr)
                    ptr += 3
                    self.tail_iterator = iter
                    self.tail_config = {}
                    for i in range(cnt):
                        (key,) = struct.unpack_from('<H',data,ptr)
                        ptr += 2
                        self.tail_config[key] = None
                elif self.tail_subtype == self.CONFIG_READ:
                    (cnt,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    self.tail_config = {}
                    for i in range(cnt):
                        (key,val,) = struct.unpack_from('<Hs',data,ptr)
                        ptr += len(val) + 3
                        self.tail_config[key] = val
                elif self.tail_subtype == self.CONFIG_WRITE:
                    (code,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    self.tail_code = code
                elif self.tail_subtype == self.CONFIG_DELETE:
                    (code,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    self.tail_code = code
                elif self.tail_subtype == self.CONFIG_SALT:
                    (salt,) = struct.unpack_from('<16s',data,ptr)
                    ptr += 16
                    self.tail_salt = salt
                elif self.tail_subtype == self.CONFIG_TEST:
                    (test,) = struct.unpack_from('<p',data,ptr)
                    ptr += len(test) + 1
                    self.tail_test = test
                else:
                    raise NotImplementedError('decode config response: {}'.format(self.tail_subtype))
            elif self.tail_frmtype == self.FRAME_ANCHOR_AUX:
                self.tail_timing = _testbit(self.tail_subtype,3)
                txtime = _testbit(self.tail_subtype,2)
                rxtime = _testbit(self.tail_subtype,1)
                rxinfo = _testbit(self.tail_subtype,0)
                if txtime:
                    (tstamp,) = struct.unpack_from('5s',data,ptr)
                    ptr += 5
                    self.tail_txtime = TailWPANFrame.tsdecode(tstamp)
                if rxtime:
                    self.tail_rxtimes = {}
                if rxinfo:
                    self.tail_rxinfos = {}
                if rxtime or rxinfo:
                    (cnt,) = struct.unpack_from('<B',data,ptr)
                    ptr += 1
                    bits = 0
                    for i in range(0,cnt,8):
                        (val,) = struct.unpack_from('<B',data,ptr)
                        ptr += 1
                        bits |= val << i
                    for i in range(cnt):
                        if _testbit(bits,i):
                            (addr,) = struct.unpack_from('8s',data,ptr)
                            ptr += 8
                        else:
                            (addr,) = struct.unpack_from('2s',data,ptr)
                            ptr += 2
                        if rxtime:
                            (val,) = struct.unpack_from('5s',data,ptr)
                            ptr += 5
                            tstamp = TailWPANFrame.tsdecode(val)
                            self.tail_rxtimes[_byteswap(addr)] = tstamp
                            if WPANFrame.match_if(_byteswap(addr)):
                                self.tail_rxtime = tstamp
                        if rxinfo:
                            rxinfo = struct.unpack_from('<4H',data,ptr)
                            ptr += 8
                            self.tail_rxinfos[_byteswap(addr)] = rxinfo
                            if WPANFrame.match_if(_byteswap(addr)):
                                self.tail_rxinfo = rxinfo
            else:
                raise NotImplementedError('decode tail frametype: {}'.format(self.tail_frmtype))
    ## Tail encrypted protocol
        elif magic == TailWPANFrame.TAIL_MAGIC_ENC:
            self.tail_protocol = self.TAIL_PROTO_ENC
            self.tail_payload = data[ptr:]
    ## Tail protocols end
        else:
            self.tail_protocol = self.TAIL_PROTO_NONE
            self.tail_payload = data[ptr-1:]
            
    def encode(self):
        data = WPANFrame.encode(self)
        if self.tail_protocol == self.TAIL_PROTO_STD:
            data += struct.pack('<B',TailWPANFrame.TAIL_MAGIC_STD)
            if self.tail_frmtype == self.FRAME_TAG_BLINK:
                self.tail_subtype = 0
                if self.tail_cookie is not None:
                    self.tail_subtype |= _bit(3)
                if self.tail_ies is not None:
                    self.tail_subtype |= _bit(2)
                if self.tail_eies is not None:
                    self.tail_subtype |= _bit(1)
                frame = _makebits(self.tail_frmtype,4,4) | _makebits(self.tail_subtype,0,4)
                data += struct.pack('<B',frame)
                self.tail_flags = 0
                if self.tail_listen:
                    self.tail_flags |= _bit(7)
                if self.tail_accel:
                    self.tail_flags |= _bit(6)
                if self.tail_dcin:
                    self.tail_flags |= _bit(5)
                if self.tail_salt:
                    self.tail_flags |= _bit(4)
                data += struct.pack('<B',self.tail_flags)
                if self.tail_cookie is not None:
                    data += struct.pack('16s',self.tail_cookie)
                if self.tail_ies is not None:
                    data += struct.pack('<B',len(self.tail_ies))
                    for (id,val) in self.tail_ies.items():
                        data += struct.pack('<B', id)
                        idf = _getbits(id,6,2)
                        if idf == 0:
                            data += struct.pack('<B', val)
                        elif idf == 1:
                            data += struct.pack('<H', val)
                        elif idf == 2:
                            data += struct.pack('<I', val)
                        else:
                            data += struct.pack('<p', val)
                if self.tail_eies is not None:
                    raise NotImplementedError('encode EIEs')
            elif self.tail_frmtype == self.FRAME_ANCHOR_BEACON:
                frame = _makebits(self.tail_frmtype,4,4) | _makebits(self.tail_subtype,0,4)
                flags = self.tail_flags
                data += struct.pack('<BB', frame, flags)
                data += struct.pack('8s', _byteswap(self.tail_beacon))
            elif self.tail_frmtype == self.FRAME_RANGING_REQUEST:
                frame = _makebits(self.tail_frmtype,4,4) | _makebits(self.tail_subtype,0,4)
                flags = self.tail_flags
                data += struct.pack('<BB',frame, flags)
            elif self.tail_frmtype == self.FRAME_RANGING_RESPONSE:
                self.tail_subtype = 0
                if self.tail_owr:
                    self.tail_subtype |= _bit(3)
                frame = _makebits(self.tail_frmtype,4,4) | _makebits(self.tail_subtype,0,4)
                data += struct.pack('<B',frame)
                data += TailWPANFrame.tsencode(self.tail_txtime)
                if not self.tail_owr:
                    cnt = len(self.tail_rxtimes)
                    data += struct.pack('<B', cnt)
                    mask = 1
                    bits = 0
                    for addr in self.tail_rxtimes:
                        if len(addr) == 8:
                            bits |= mask
                        mask <<= 1
                    for i in range(0,cnt,8):
                        data += struct.pack('<B', ((bits>>i) & 0xff))
                    for (addr,time) in self.tail_rxtimes.items():
                        if len(addr) == 8:
                            data += struct.pack('8s', _byteswap(addr))
                        else:
                            data += struct.pack('2s', _byteswap(addr))
                        data += TailWPANFrame.tsencode(time)
            elif self.tail_frmtype == self.FRAME_CONFIG_REQUEST:
                if self.tail_subtype == self.CONFIG_RESET:
                    data += struct.pack('<H',self.tail_reset_magic)
                elif self.tail_subtype == self.CONFIG_ENUMERATE:
                    data += struct.pack('<H',self.tail_iterator)
                elif self.tail_subtype == self.CONFIG_READ:
                    data += struct.pack('<B',len(self.tail_config))
                    for key in tail_config:
                        data += struct.pack('<H',key)
                elif self.tail_subtype == self.CONFIG_WRITE:
                    data += struct.pack('<B',len(self.tail_config))
                    for (key,val) in tail_config.items():
                        data += struct.pack('<Hp',key,val)
                elif self.tail_subtype == self.CONFIG_DELETE:
                    data += struct.pack('<B',len(self.tail_config))
                    for key in tail_config:
                        data += struct.pack('<H',key)
                elif self.tail_subtype == self.CONFIG_SALT:
                    data += struct.pack('<16s',self.tail_salt)
                elif self.tail_subtype == self.CONFIG_TEST:
                    data += struct.pack('<16s',self.tail_test)
                else:
                    raise NotImplementedError('encode config request {}'.format(self.tail_subtype))
            elif self.tail_frmtype == self.FRAME_CONFIG_RESPONSE:
                if self.tail_subtype == self.CONFIG_RESET:
                    data += struct.pack('<H',self.tail_reset_magic)
                elif self.tail_subtype == self.CONFIG_ENUMERATE:
                    data += struct.pack('<H',self.tail_iterator)
                    data += struct.pack('<B',len(self.tail_config))
                    for key in tail_config:
                        data += struct.pack('<H',key)
                elif self.tail_subtype == self.CONFIG_READ:
                    data += struct.pack('<B',len(self.tail_config))
                    for (key,val) in tail_config.items():
                        data += struct.pack('<Hp',key,val)
                elif self.tail_subtype == self.CONFIG_WRITE:
                    data += struct.pack('<B',self.tail_code)
                elif self.tail_subtype == self.CONFIG_DELETE:
                    data += struct.pack('<B',self.tail_code)
                elif self.tail_subtype == self.CONFIG_SALT:
                    data += struct.pack('<16s',self.tail_salt)
                elif self.tail_subtype == self.CONFIG_TEST:
                    data += struct.pack('<16s',self.tail_test)
                else:
                    raise NotImplementedError('encode config response {}'.format(self.tail_subtype))
            elif self.tail_frmtype == self.FRAME_ANCHOR_AUX:
                self.tail_subtype = 0
                if self.tail_timing:
                    self.tail_subtype |= _bit(3)
                if self.tail_txtime:
                    self.tail_subtype |= _bit(2)
                if self.tail_rxtimes:
                    self.tail_subtype |= _bit(1)
                if self.tail_rxinfos:
                    self.tail_subtype |= _bit(0)
                frame = _makebits(self.tail_frmtype,4,4) | _makebits(self.tail_subtype,0,4)
                data += struct.pack('<B',frame)
                if self.tail_txtime:
                    data += TailWPANFrame.tsencode(self.tail_txtime)
                if self.tail_rxtimes:
                    addrs = self.tail_rxtimes.keys()
                elif self.tail_rxinfos:
                    addrs = self.tail_rxinfos.keys()
                if self.tail_rxtimes or self.tail_rxinfos:
                    cnt = len(addrs)
                    data += struct.pack('<B', cnt)
                    mask = 1
                    bits = 0
                    for addr in addrs:
                        if len(addr) == 8:
                            bits |= mask
                        mask <<= 1
                    for i in range(0,cnt,8):
                        data += struct.pack('<B', ((bits>>i) & 0xff))
                    for addr in addrs:
                        if len(addr) == 8:
                            data += struct.pack('8s', _byteswap(addr))
                        else:
                            data += struct.pack('2s', _byteswap(addr))
                        if self.tail_rxtimes:
                            data += TailWPANFrame.tsencode(self.tail_rxtimes[addr])
                        if self.tail_rxinfos:
                            data += struct.pack('<4H', *self.tail_rxinfos[addr])
            else:
                raise NotImplementedError('encode tail frametype {}'.format(self.tail_frmtype))
        elif self.tail_protocol == self.TAIL_PROTO_ENC:
            data += struct.pack('<B',TailWPANFrame.TAIL_MAGIC_ENC)
            data += self.tail_payload
        else:
            data += self.tail_payload
        self.frame_len = len(data)
        self.frame_data = data
        return data
        
    def __dump__(self):
        ret = WPANFrame.__dump__(self)
        dmp = []
        if self.verbose == 0:
            if self.tail_protocol == self.TAIL_PROTO_STD:
                dmp.append(('Protocol', 'Standard (v1)'))
                if self.tail_frmtype == self.FRAME_TAG_BLINK:
                    dmp.append(('FrameType', 'Tag Blink sub:{} flags:{}'.format(self.tail_subtype, self.tail_flags)))
                elif self.tail_frmtype == self.FRAME_ANCHOR_BEACON:
                    dmp.append(('FrameType', 'Anchor Beacon sub:{} flags:{} eui:{}'.format(self.tail_subtype, self.tail_flags, self.tail_beacon.hex())))
                elif self.tail_frmtype == self.FRAME_RANGING_REQUEST:
                    dmp.append(('FrameType', 'Ranging Request'))
                elif self.tail_frmtype == self.FRAME_RANGING_RESPONSE:
                    dmp.append(('FrameType', 'Ranging Response OWR:{}'.format(self.tail_owr)))
                    if self.tail_rxtimes:
                        dmp.append(('RxTimes', len(self.tail_rxtimes)))
                elif self.tail_frmtype == self.FRAME_CONFIG_REQUEST:
                    dmp.append(('FrameType', 'Config Request'))
                elif self.tail_frmtype == self.FRAME_CONFIG_RESPONSE:
                    dmp.append(('FrameType', 'Config Response'))
            elif self.tail_protocol == self.TAIL_PROTO_ENC:
                dmp.append(('Protocol', 'Encrypted'))
            elif self.tail_protocol == self.TAIL_PROTO_NONE:
                dmp.append(('Protocol', 'None (raw)'))
        else:
            if self.tail_protocol == self.TAIL_PROTO_STD:
                if self.verbose > 1:
                    dmp.append(('Payload', self.tail_payload.hex()))
                dmp.append(('Protocol', 'Standard (v1)'))
                if self.tail_frmtype == self.FRAME_TAG_BLINK:
                    dmp.append(('FrameType', 'Tag Blink {}:{}'.format(self.tail_frmtype,self.tail_subtype)))
                    dmp.append(('EIEs', _testbit(self.tail_subtype,1)))
                    dmp.append(('IEs', _testbit(self.tail_subtype,2)))
                    dmp.append(('Cookie', _testbit(self.tail_subtype,3)))
                    dmp.append(('Flags', '0x{:02x}'.format(self.tail_flags)))
                    dmp.append(('Listen', _testbit(self.tail_flags,7)))
                    dmp.append(('Accel', _testbit(self.tail_flags,6)))
                    dmp.append(('DCin', _testbit(self.tail_flags,5)))
                    dmp.append(('Salt', _testbit(self.tail_flags,4)))
                    if self.tail_cookie is not None:
                        dmp.append(('Cookie', self.tail_cookie.hex()))
                    if self.tail_ies is not None:
                        dmp.append(('IEs', list(self.tail_ies.items())))
                elif self.tail_frmtype == self.FRAME_ANCHOR_BEACON:
                    dmp.append(('FrameType', 'Anchor Beacon {}:{}'.format(self.tail_frmtype,self.tail_subtype)))
                    dmp.append(('Flags', '0x{:02x}'.format(self.tail_flags)))
                    dmp.append(('Ref', self.tail_beacon.hex()))
                elif self.tail_frmtype == self.FRAME_RANGING_REQUEST:
                    dmp.append(('FrameType', 'Ranging Request {}:{}'.format(self.tail_frmtype,self.tail_subtype)))
                elif self.tail_frmtype == self.FRAME_RANGING_RESPONSE:
                    dmp.append(('FrameType', 'Ranging Response {}'.format(self.tail_frmtype)))
                    dmp.append(('OWR', self.tail_owr))
                    dmp.append(('TxTime', self.tail_txtime))
                    if self.tail_rxtimes:
                        dmp.append(('RxTimes', self.tail_rxtimes.items()))
                elif self.tail_frmtype == self.FRAME_CONFIG_REQUEST:
                    dmp.append(('FrameType', 'ConfigReq {}:{}\n'.format(self.tail_frmtype,self.tail_subtype)))
                    if self.tail_subtype == self.CONFIG_RESET:
                        dmp.append(('Type', 'RESET'))
                        dmp.append(('Magic', self.tail_reset_magic))
                    elif self.tail_subtype == self.CONFIG_ENUMERATE:
                        dmp.append(('Type', 'ENUMERATE'))
                        dmp.append(('Iterator', self.tail_iterator))
                    elif self.tail_subtype == self.CONFIG_READ:
                        dmp.append(('Type', 'READ'))
                        dmp.append(('Keys', tail_config.items()))
                    elif self.tail_subtype == self.CONFIG_WRITE:
                        dmp.append(('Type', 'WRITE'))
                        dmp.append(('Keys', tail_config.items()))
                    elif self.tail_subtype == self.CONFIG_DELETE:
                        dmp.append(('Type', 'DELETE'))
                        dmp.append(('Keys', tail_config.items()))
                    elif self.tail_subtype == self.CONFIG_SALT:
                        dmp.append(('Type', 'SALT'))
                        dmp.append(('Salt', self.tail_salt))
                    elif self.tail_subtype == self.CONFIG_TEST:
                        dmp.append(('Type', 'TEST'))
                        dmp.append(('Value', self.tail_test))
                elif self.tail_frmtype == self.FRAME_CONFIG_RESPONSE:
                    dmp.append(('FrameType', 'ConfigResp {}:{}'.format(self.tail_frmtype,self.tail_subtype)))
                    if self.tail_subtype == self.CONFIG_RESET:
                        dmp.append(('Type', 'RESET'))
                        dmp.append(('Magic', self.tail_reset_magic))
                    elif self.tail_subtype == self.CONFIG_ENUMERATE:
                        dmp.append(('Type', 'ENUMERATE'))
                        dmp.append(('Iterator', self.tail_iterator))
                        dmp.append(('Keys', tail_config.items()))
                    elif self.tail_subtype == self.CONFIG_READ:
                        dmp.append(('Type', 'READ'))
                        dmp.append(('Keys', ''))
                        dmp.append(('Keys', tail_config.items()))
                    elif self.tail_subtype == self.CONFIG_WRITE:
                        dmp.append(('Type', 'WRITE'))
                        dmp.append(('Code', self.tail_code))
                    elif self.tail_subtype == self.CONFIG_DELETE:
                        dmp.append(('Type', 'DELETE'))
                        dmp.append(('Code', self.tail_code))
                    elif self.tail_subtype == self.CONFIG_SALT:
                        dmp.append(('Type', 'SALT'))
                        dmp.append(('Salt', self.tail_salt))
                    elif self.tail_subtype == self.CONFIG_TEST:
                        dmp.append(('Type', 'TEST'))
                        dmp.append(('Value', self.tail_test))
                elif self.tail_frmtype == self.FRAME_ANCHOR_AUX:
                    dmp.append(('FrameType', 'Ranging AUX {}'.format(self.tail_frmtype)))
                    dmp.append(('Timing', bool(self.tail_timing)))
                    dmp.append(('TxTime', bool(self.tail_txtime)))
                    dmp.append(('RxTimes', bool(self.tail_rxtimes)))
                    dmp.append(('RxInfos', bool(self.tail_rxinfos)))
                    if self.tail_txtime:
                        dmp.append(('TxTime', self.tail_txtime))
                    if self.tail_rxtimes:
                        dmp.append(('RxTimes', self.tail_rxtimes.items()))
                    if self.tail_rxinfos is not None:
                        dmp.append(('RxInfos', self.tail_rxinfos.items()))
            elif self.tail_protocol == self.TAIL_PROTO_ENC:
                dmp.append(('Protocol', 'Encrypted'))
            elif self.tail_protocol == self.TAIL_PROTO_NONE:
                dmp.append(('Protocol', 'None (raw)'))
        ret += [('Tail Frame',dmp)]
        return ret

    def __str__(self):
        if self.verbose == 0:
            return simpledump(self.__dump__())
        else:
            return prettydump(self.__dump__(),0,WPANFrame.dmp_indent,WPANFrame.dmp_keylen)



    
## Missing values in socket
    
for name,value in (
        ('PROTO_IEEE802154', 0xf600),
        ('SO_TIMESTAMPING', 37),
        ('SOF_TIMESTAMPING_TX_HARDWARE',  (1<<0)),
        ('SOF_TIMESTAMPING_TX_SOFTWARE',  (1<<1)),
        ('SOF_TIMESTAMPING_RX_HARDWARE',  (1<<2)),
        ('SOF_TIMESTAMPING_RX_SOFTWARE',  (1<<3)),
        ('SOF_TIMESTAMPING_SOFTWARE',     (1<<4)),
        ('SOF_TIMESTAMPING_SYS_HARDWARE', (1<<5)),
        ('SOF_TIMESTAMPING_RAW_HARDWARE', (1<<6))):
    if not hasattr(socket, name):
        setattr(socket, name, value)


