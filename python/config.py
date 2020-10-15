#!/usr/bin/python3

import json
import yaml



class Config(object):

    def __init__(self, mapping=None, **kwargs):
        if mapping:
            self.load(mapping)
        else:
            self.load(kwargs)

    def __len__(self):
        return len(self.__dict__)

    def __repr__(self):
        return repr(self.__dict__)

    def __iter__(self):
        return iter(self.__dict__)


    def __getitem__(self, key):
        return getattr(self,key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __delitem__(self, key):
        delattr(self, key)
    

    def get(self, *args):
        return self.__dict__.get(*args)
    
    def pop(self, *args):
        return self.__dict__.pop(*args)

    def popitem(self):
        return self.__dict__.popitem()

    def clear(self):
        self.__dict__.clear()
    
    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def copy(self):
        return self.__class__(self)

        
    def load(self, data):
        if isinstance(data,dict):
            for (key,value) in data.items():
                if isinstance(value, dict):
                    value = Config(value)
                setattr(self,key,value)

    def loadJSON(self, name):
        with open(name) as f:
            self.load(json.load(f))

    def loadYAML(self, name):
        with open(name) as f:
            self.load(yaml.safe_load(f))


config = Config()

