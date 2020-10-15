#!/usr/bin/python3

import sys
import time
import logger

from coord import *
from config import *


class Tail():

    def __init__(self, name, eui64, coord=None):
        self.key      = eui64
        self.name     = name
        self.eui64    = eui64
        self.coord    = Coord(coord)

    def distance_to(self, obj):
        return self.coord.dist(obj.coord)

