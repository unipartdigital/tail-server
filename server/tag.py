#!/usr/bin/python3

import os
import sys

import math
import logger

from tail import *
from wpan import *
from tdoa import *
from dwarf import *
from coord import *
from lateration import *

from config import config


log = logger.getLogger(__name__)


class Tag(Tail):

    def __init__(self, server, name, eui64, **kwargs):
        Tail.__init__(self,name,eui64)
        self.server  = server
        self.kwargs  = kwargs
        self.beacon  = None

        self.coord   = Coord(None)

        # Different filter designs could be chosen here
        self.filter  = CoordQCFilter( CoordGeoFilter(config.coord.filter_len),
                                      CoordGeoFilter(config.coord.qc_filter_len),
                                      config.coord.qc_filter_dev )


    def report_coord(self):
        topic = 'TAIL/TAG/{}/{}/COORD'.format(self.server.domain, self.eui64)
        self.server.mqtt_publish(topic, TAG=self.eui64, NAME=self.name,
                                 COORD=self.coord.tolist(), FILTERED=self.filter.tolist())
    
    def update_coord(self, new_coord):
        log.debug(f'Tag: COORD: {new_coord.tolist()}')
        self.coord.update(new_coord)
        self.filter.update(new_coord)
        self.report_coord()

    def update_beacon(self, beacon):
        if self.beacon != beacon:
            if self.beacon:
                self.beacon.unregister_tag(self)
            self.beacon = beacon
            if self.beacon:
                self.beacon.register_tag(self)

