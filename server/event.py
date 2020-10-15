#!/usr/bin/python3

import logger
import hashlib

from config import *
from dwarf import *
from wpan import *


log = logger.getLogger(__name__)


class TEvent():

    TEV_TYPE = 0

    def __init__(self, evtype):
        self.evtype = evtype


class RFEvent(TEvent):

    TEV_TYPE = 1

    def __init__(self,anchor,dir,times,frame,finfo):
        TEvent.__init__(self,RFEvent.TEV_TYPE)
        self.key    = anchor.key
        self.anchor = anchor
        self.direct = dir
        self.times  = times
        self.frame  = TailWPANFrame(frame,finfo)
        self.finfo  = self.frame.timestamp.tsinfo
        self.rawts  = self.frame.timestamp.tsinfo.rawts

    def is_rx(self):
        return (self.direct == 'RX')

    def is_tx(self):
        return (self.direct == 'TX')

    def swts(self):
        return self.times.sw

    def hwts(self):
        return self.times.hw

    def hits(self):
        return self.times.hi

    def timestamp(self):
        return self.rawts

    def make_ranging_ref(self, addr, seq):
        md5 = hashlib.md5()
        msg = struct.pack('8sB', addr, seq&0xff)
        md5.update(msg)
        ref =  md5.digest()
        return ref[:8]

    def get_ranging_ref(self):
        if self.frame.tail_protocol == self.frame.TAIL_PROTO_STD:
            if self.frame.tail_frmtype == self.frame.FRAME_TAG_BLINK:
                tag = self.frame.src_addr
                seq = self.frame.frame_seqnum
                return self.make_ranging_ref(tag,seq)
            elif self.frame.tail_frmtype == self.frame.FRAME_ANCHOR_BEACON:
                return self.frame.tail_beacon
            elif self.frame.tail_frmtype == self.frame.FRAME_RANGING_REQUEST:
                raise NotImplementedError
            elif self.frame.tail_frmtype == self.frame.FRAME_RANGING_RESPONSE:
                tag = self.frame.src_addr
                seq = self.frame.frame_seqnum
                return self.make_ranging_ref(tag, seq-1)
        return None

    def get_rx_level(self):
        POW = self.finfo.cir_pwr
        RXP = self.finfo.rxpacc
        if POW>0 and RXP>0:
            power = (POW << 17) / (RXP*RXP)
            level = RxPower2dBm(power, config.dw1000.prf)
            return level
        else:
            return -120

    def get_fp_level(self):
        FP1 = self.finfo['fp_ampl1']
        FP2 = self.finfo['fp_ampl2']
        FP3 = self.finfo['fp_ampl3']
        RXP = self.finfo['rxpacc']
        if FP1>0 and FP2>0 and FP3>0 and RXP>0:
            power = (FP1*FP1 + FP2*FP2 + FP3*FP3) / (RXP*RXP)
            level = RxPower2dBm(power, config.dw1000.prf)
            return level
        else:
            return -120

    def get_noise(self):
        N = self.finfo['noise']
        return N

    def get_xtal_ratio(self):
        I = self.finfo['ttcki']
        O = self.finfo['ttcko']
        return O/I


