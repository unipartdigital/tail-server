#!/usr/bin/python3

import logger

import numpy as np


log = logger.getLogger(__name__)


class MAVGFilter():

    def __init__(self, lenght):
        self.lenght = lenght
        self.reset()

    def reset(self):
        self.data = []
        
    def update(self,value):
        self.data.append(value)
        if len(self.data) > self.length:
            data.popleft()

    def avg(self):
        return np.mean(self.data)

    def var(self):
        return np.var(self.data)

    def std(self):
        return np.std(self.data)


class GeoFilter():

    def __init__(self, zero, lenght):
        self.zero = zero
        self.lenght = lenght
        self.reset()

    def reset(self):
        self.val_filt = self.zero.copy()
        self.var_filt = 0.0
        self.count = 0
        
    def update(self,value):
        self.count += 1
        flen = min(self.count, self.lenght)
        diff = value - self.val_filt
        self.val_filt += diff / flen
        self.var_filt += (np.sum(diff*diff) - self.var_filt) / flen

    def avg(self):
        return self.val_filt.copy()

    def var(self):
        return self.var_filt.copy()

    def std(self):
        return np.sqrt(self.var_filt)

    
