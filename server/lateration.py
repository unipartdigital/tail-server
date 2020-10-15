#!/usr/bin/python3

import math
import logger
import random
import threading

from wpan import *
from tdoa import *
from dwarf import *
from coord import *

from config import config

import numpy as np


log = logger.getLogger(__name__)


class Lateration():

    NO_WAY_RANGING  = 0
    ONE_WAY_RANGING = 1
    TWO_WAY_RANGING = 2

    def __init__(self, server, rangid, method=0):
        self.rangid = rangid
        self.server = server
        self.method = method
        self.device = None
        self.blinks = None
        self.active = False
        self.thread = None
        self.ranging_timer = self.server.timers.Timer(config.ranging.ranging_timer, self.ranging_expire)
        self.timeout_timer = self.server.timers.Timer(config.ranging.timeout_timer, self.timeout_expire)

    def start(self):
        self.start_time = time.time()
        self.timeout_timer.arm()
        self.blinks = ( {}, {}, {} )
        self.active = True
        log.debug('Lateration::start')

    def finish(self):
        self.ranging_timer.unarm()
        self.timeout_timer.unarm()
        self.blinks = None
        self.active = False
        self.thread = None
        self.server.finish_ranging(self)
        log.debug('Lateration::finish @ {}s'.format(time.time() - self.start_time))

    def update(self,coord):
        if self.device:
            self.device.update_coord(coord)

    def laterate(self):
        self.finish()

    def ranging_expire(self):
        log.debug('Lateration::ranging_expire @ {}'.format(time.time() - self.start_time))
        self.ranging_timer.unarm()
        self.timeout_timer.unarm()
        self.thread = threading.Thread(target=self.laterate);
        self.thread.start()

    def timeout_expire(self):
        log.debug('Lateration::timeout_expire @ {}'.format(time.time() - self.start_time))
        self.finish()

    def find_beacon(self):
        beacons = {}
        for evnt in self.blinks[1].values():
            src = evnt.frame.get_src_eui()
            if src in beacons:
                beacons[src] += 1
            else:
                beacons[src] = 1
        key = max(beacons, key=beacons.get)
        anchor = self.server.get_anchor(key)
        log.debug('find_beacon: {} <{}>'.format(anchor.name, anchor.eui64))
        return anchor

    def add_blink(self,evnt):
        if self.active and self.method:
            log.debug('Lateration::add_blink:    ANC:{} <{}> SRC:{} Rx:{:.1f}dBm'.format(evnt.anchor.name, evnt.anchor.eui64, evnt.frame.get_src_eui(), evnt.get_rx_level()))
            self.blinks[0][evnt.anchor.key] = evnt
            if self.device is None:
                self.device = self.server.get_device(evnt.frame.get_src_eui())

    def add_beacon(self,evnt):
        if self.active and self.method == self.ONE_WAY_RANGING:
            log.debug('Lateration::add_beacon:   ANC:{} <{}> SRC:{} Rx:{:.1f}dBm'.format(evnt.anchor.name, evnt.anchor.eui64, evnt.frame.get_src_eui(), evnt.get_rx_level()))
            self.blinks[1][evnt.anchor.key] = evnt
            src = evnt.frame.get_src_eui()

    def add_request(self,evnt):
        if self.active and self.method == self.TWO_WAY_RANGING:
            log.debug('Lateration::add_request:  ANC:{} <{}> SRC:{} Rx:{:.1f}dBm'.format(evnt.anchor.name, evnt.anchor.eui64, evnt.frame.get_src_eui(), evnt.get_rx_level()))
            self.blinks[1][evnt.anchor.key] = evnt

    def add_response(self,evnt):
        if self.active and self.method:
            log.debug('Lateration::add_response: ANC:{} <{}> SRC:{} Rx:{:.1f}dBm'.format(evnt.anchor.name, evnt.anchor.eui64, evnt.frame.get_src_eui(), evnt.get_rx_level()))
            self.blinks[2][evnt.anchor.key] = evnt
            self.ranging_timer.arm()



class TWR(Lateration):
    
    def __init__(self, server, rangid):
        Lateration.__init__(self, server, randig, Lateration.TWO_WAY_RANGING)

    def laterate(self):
        raise NotImplementedError



class OWR(Lateration):

    def __init__(self, server, rangid):
        Lateration.__init__(self, server, rangid, Lateration.ONE_WAY_RANGING)
        self.beacon = None

    def register_beacon(self, beacon):
        if beacon and self.device:
            self.device.update_beacon(beacon)
    
    def select_beacon(self):
        if config.ranging.force_beacon == 'RANDOM':
            N = len(self.server.anchors)
            I = random.randrange(0,N)
            self.beacon = list(self.server.anchors.values())[I]
            log.debug('OWR::select_beacon: RANDOM Tag:{} => Anchor:{}'.format(self.device.name, self.beacon.name))
            return
        elif config.ranging.force_beacon is not None:
            self.beacon = self.server.get_anchor_by_name(config.ranging.force_beacon)
            log.debug('OWR::select_beacon: FORCED Tag:{} => Anchor:{}'.format(self.device.name, self.beacon.name))
            return
        else:
            levels = {}
            for key in self.server.anchors:
                if key in self.blinks[0]:
                    evnt = self.blinks[0][key]
                    levels[key] = evnt.get_rx_level()
            if levels:
                key = max(levels, key=levels.get)
                self.beacon = self.server.anchors[key]
                log.debug('OWR::select_beacon: BEST Tag:{} => Anchor:{}'.format(self.device.name, self.beacon.name))
                return
        raise ValueError('Beacon anchor selection not possible')



class OWRExt(OWR):

    def select_common(self):
        if config.ranging.force_common == 'RANDOM':
            N = len(self.server.anchors)
            I = random.randrange(0,N)
            com = list(self.server.anchors.values())[I]
            log.debug('OWRExt::select_common: RANDOM Tag:{} => Anchor:{}'.format(self.device.name, self.beacon.name))
            return com
        elif config.ranging.force_common is not None:
            com = self.server.get_anchor_by_name(config.ranging.force_common)
            log.debug('OWRExt::select_common: FORCED Tag:{} => Anchor:{}'.format(self.device.name, com.name))
            return com
        if self.beacon:
            levels = {}
            for key in self.server.anchors:
                if key != self.beacon.key:
                    if key in self.blinks[0] and key in self.blinks[1] and key in self.blinks[2]:
                        rx0 = self.blinks[0][key]
                        rx1 = self.blinks[1][key]
                        rx2 = self.blinks[2][key]
                        levels[key] = rx0.get_rx_level() + rx1.get_rx_level() + rx2.get_rx_level()
            if levels:
                key = max(levels, key=levels.get)
                com = self.server.anchors[key]
                log.debug('OWRExt::select_common: BEST Tag:{} => Anchor:{}'.format(self.device.name, com.name))
                return com
        raise ValueError('Common anchor selection not possible')



class LatWLS2D(OWR):

    def laterate(self):
        if self.device:
            try:
                self.beacon = self.find_beacon()
            
                log.debug(' * Beacon: {} {} {}'.format(self.beacon.name, self.beacon.eui64, self.beacon.coord))
        
                bkey = self.beacon.key
            
                COORDS = []
                RANGES = []
                SIGMAS = []
            
                T = [ 0, 0, 0, 0, 0, 0 ]

                for (akey,anchor) in self.server.anchors.items():
                    if akey != bkey:
                        try:
                            T[0] = self.blinks[0][akey].timestamp()
                            T[1] = self.blinks[0][bkey].timestamp()
                            T[2] = self.blinks[1][bkey].timestamp()
                            T[3] = self.blinks[1][akey].timestamp()
                            T[4] = self.blinks[2][akey].timestamp()
                            T[5] = self.blinks[2][bkey].timestamp()
                            C = self.beacon.distance_to(anchor)
                            L = woodoo(T)
                            D = C - 2*L
                            if -config.ranging.max_dist < D < config.ranging.max_dist:
                                COORDS.append((anchor.coord[0],anchor.coord[1]))
                                RANGES.append(D)
                                SIGMAS.append(0.1)
                                log.debug( ' * Anchor: {} <{}> LAT:{:.3f} C:{:.3f} D:{:.3f}'.format(anchor.name,anchor.eui64,L,C,D))
                            else:
                                log.debug( ' * Anchor: {} <{}> LAT:{:.3f} C:{:.3f} D:{:.3f} *** FAILURE'.format(anchor.name,anchor.eui64,L,C,D))
                        except KeyError:
                            log.debug( ' * Anchor: {} <{}> NOT FOUND'.format(anchor.name,anchor.eui64))
                        except ZeroDivisionError:
                            log.debug( ' * Anchor: {} <{}> BAD TIMES'.format(anchor.name,anchor.eui64))

                if len(RANGES) > 1:
                    (coord,cond) = hyperlater2D((self.beacon.coord[0], self.beacon.coord[1]), COORDS, RANGES, SIGMAS, delta=0.01)
                    self.update(coord)
        
            except:
                log.exception('LatWLS2D failed')
        
        self.select_beacon()
        self.register_beacon(self.beacon)

        self.finish()


class LatWLS3D(OWR):
    
    def laterate(self):
        if self.device:
            try:
                self.beacon = self.find_beacon()
            
                log.debug( ' * Beacon: {} <{}>'.format(self.beacon.name,self.beacon.eui64))
                
                bkey = self.beacon.key
                
                COORDS = []
                RANGES = []
                SIGMAS = []
                
                T = [ 0, 0, 0, 0, 0, 0 ]
                
                for (akey,anchor) in self.server.anchor_keys.items():
                    if akey != bkey:
                        try:
                            T[0] = self.blinks[0][akey].timestamp()
                            T[1] = self.blinks[0][bkey].timestamp()
                            T[2] = self.blinks[1][bkey].timestamp()
                            T[3] = self.blinks[1][akey].timestamp()
                            T[4] = self.blinks[2][akey].timestamp()
                            T[5] = self.blinks[2][bkey].timestamp()
                            C = self.beacon.distance_to(anchor)
                            L = woodoo(T)
                            D = C - 2*L
                            if -config.ranging.max_dist < D < config.ranging.max_dist:
                                COORDS.append(anchor.coord)
                                RANGES.append(D)
                                SIGMAS.append(0.1)
                                log.debug( ' * Anchor: {} <{}> LAT:{:.3f} C:{:.3f} D:{:.3f}'.format(anchor.name,anchor.eui64,L,C,D))
                            else:
                                log.debug( ' * Anchor: {} <{}> D:{:.3f} BAD TDOA'.format(anchor.name,anchor.eui64,D))
                        except KeyError:
                            log.debug( ' * Anchor: {} <{}> NOT FOUND'.format(anchor.name,anchor.eui64))
                        except ZeroDivisionError:
                            log.debug( ' * Anchor: {} <{}> BAD TIMES'.format(anchor.name,anchor.eui64))
                            
                if len(RANGES) > 4:
                    (coord,cond) = hyperlater3D(self.beacon.coord, COORDS, RANGES, SIGMAS, delta=0.01)
                    self.update(coord)
                    
            except:
                log.exception('LatWLS3D failed')
        
        self.select_beacon()
        self.register_beacon(self.beacon)

        self.finish()


class LatSWLS(OWRExt):
    
    def laterate(self):
        if self.device:
            try:
                self.beacon = self.find_beacon()
                self.common = self.select_common()
                
                log.debug( ' * Beacon: {} <{}>'.format(self.beacon.name,self.beacon.eui64))
                log.debug( ' * Common: {} <{}>'.format(self.common.name,self.common.eui64))
                
                ckey = self.common.key
                bkey = self.beacon.key
                
                COORDS = []
                RANGES = []
                SIGMAS = []
                
                T = [ 0, 0, 0, 0, 0, 0 ]
                
                for (akey,anchor) in self.server.anchor_keys.items():
                    if akey not in (bkey,ckey):
                        try:
                            T[0] = self.blinks[0][akey].timestamp()
                            T[1] = self.blinks[0][ckey].timestamp()
                            T[2] = self.blinks[1][ckey].timestamp()
                            T[3] = self.blinks[1][akey].timestamp()
                            T[4] = self.blinks[2][akey].timestamp()
                            T[5] = self.blinks[2][ckey].timestamp()
                            B = self.beacon.distance_to(self.common)
                            C = self.beacon.distance_to(anchor)
                            L = woodoo(T)
                            D = (C - B) - 2*L
                            if -config.ranging.max_dist < D < config.ranging.max_dist:
                                COORDS.append(anchor.coord)
                                RANGES.append(D)
                                SIGMAS.append(0.1)
                                log.debug( ' * Anchor: {} <{}> LAT:{:.3f} B:{:.3f} C:{:.3f} D:{:.3f}'.format(anchor.name,anchor.eui64,L,B,C,D))
                            else:
                                log.debug( ' * Anchor: {} <{}> D:{:.3f} BAD TDOA'.format(anchor.name,anchor.eui64,D))
                        except KeyError:
                            log.debug( ' * Anchor: {} <{}> NOT FOUND'.format(anchor.name,anchor.eui64))
                        except ZeroDivisionError:
                            log.debug( ' * Anchor: {} <{}> BAD TIMES'.format(anchor.name,anchor.eui64))
                
                if len(RANGES) > 4:
                    (coord,cond) = hyperlater3D(self.beacon.coord, COORDS, RANGES, SIGMAS, delta=0.01)
                    self.update(coord)
                    
            except:
                log.exception('LatSWLS failed')
            
        self.select_beacon()
        self.register_beacon(self.beacon)

        self.finish()


