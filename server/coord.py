#!/usr/bin/python3

import logger

import numpy as np
import numpy.linalg as lin 


log = logger.getLogger(__name__)



def dist(coord1, coord2):
    if isinstance(coord1, Coord):
        vec1 = coord1.value()
    else:
        vec1 = coord1
    
    if isinstance(coord2, Coord):
        vec2 = coord2.value()
    else:
        vec2 = coord2
    
    return lin.norm(vec1 - vec2)



class Coord():

    def __init__(self, coord=None):
        self.update(coord)
    
    def new(self):
        return Coord(self)

    def reset(self):
        self._vector = np.zeros(3)

    def update(self,coord):
        if coord is not None:
            if isinstance(coord,Coord):
                self._vector = np.array(coord.value())
            else:
                self._vector = np.array(coord)
        else:
            self._vector = np.zeros(3)

    def __getitem__(self, key):
        return self.value()[key]

    def __str__(self):
        return str(self.tolist())
    
    def value(self):
        return np.array(self._vector)

    def tolist(self):
        return self.value().tolist()

    def norm(self):
        return lin.norm(self.value())
    
    def dist(self, coord):
        return self.distance_to(coord)
    
    def distance_to(self, coord):
        return lin.norm(self.value() - coord.value())


class CoordAvgFilter(Coord):

    def __init__(self, length):
        self.length = length
        self.reset()

    def new(self):
        return CoordAvgFilter(self.length)

    def reset(self):
        Coord.reset(self)
        self.data = []
        
    def update(self,coord):
        if isinstance(coord,Coord):
            self.data.append(coord.value())
        elif isinstance(coord, np.array):
            self.data.append(coord)
        if len(self.data) > self.length:
            data.popleft()

    def value(self):
        return np.mean(self.data)

    def avg(self):
        return np.mean(self.data)

    def var(self):
        return np.var(self.data)

    def std(self):
        return np.std(self.data)


class CoordGeoFilter(Coord):

    def __init__(self, length):
        self.length = length
        self.reset()

    def new(self):
        return CoordGeoFilter(self.length)

    def reset(self):
        Coord.reset(self)
        self.val_filt = np.zeros(3)
        self.var_filt = np.zeros(3)
        self.count = 0
        
    def update(self,coord):
        if isinstance(coord,Coord):
            vect = coord.value()
        else:
            vect = coord
        self.count += 1
        flen = min(self.count, self.length)
        diff = vect - self.val_filt
        self.val_filt += diff / flen
        self.var_filt += (np.sum(diff*diff) - self.var_filt) / flen

    def value(self):
        return self.avg()

    def avg(self):
        return np.array(self.val_filt)

    def var(self):
        return np.array(self.var_filt)

    def std(self):
        return np.sqrt(self.var_filt)



class CoordQCFilter(Coord):

    def __init__(self, cfilt, qfilt, maxdev):
        self.maxdev = maxdev
        self.coord_filt = cfilt.new()
        self.cqual_filt = qfilt.new()
        self.reset()

    def new(self):
        return CoordQCFilter(self.coord_filt, self.cqual_filt, self.maxdev)

    def reset(self):
        self.coord_filt.reset()
        self.cqual_filt.reset()
        
    def update(self,coord):
        self.cqual_filt.update(coord)
        if dist(self.cqual_filt.value(), coord) < self.maxdev:
            self.coord_filt.update(coord)
    
    def value(self):
        return self.coord_filt.value()
    
    def avg(self):
        return self.coord_filt.avg()

    def var(self):
        return self.coord_filt.var()

    def std(self):
        return self.coord_filt.std()




