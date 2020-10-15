#!/usr/bin/python3

import os
import io
import sys
import json
import yaml

import logging
import logging.config


def initLogger(configfile=None):
    if configfile:
        with open(configfile) as f:
            logging.config.dictConfig(yaml.safe_load(f))
    else:
        logging.basicConfig(level=logging.INFO)


def getLogger(*args, **kwargs):
    log = logging.getLogger(*args, **kwargs)
    return log


def dprint(level, *args, **kwargs):
    logging.debug(*args, **kwargs)

def iprint(*args, **kwargs):
    logging.info(*args, **kwargs)

def wprint(*args, **kwargs):
    logging.warning(*args, **kwargs)

def eprint(*args, **kwargs):
    logging.error(*args, **kwargs)

def cprint(*args, **kwargs):
    logging.critical(*args, **kwargs)

def exprint(*args, **kwargs):
    logging.exception(*args, **kwargs)


def prints(*args, **kwargs):
    print(*args, end='', flush=True, **kwargs)

def printerr(*args, **kwargs):
    print(*args, file=sys.stderr, flush=True, **kwargs)

