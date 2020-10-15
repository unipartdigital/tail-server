#!/usr/bin/python3

import argparse

from logger import *
from server import *
from config import *


DEFAULT_CONFIG = 'rtls.conf'

DEFAULT_LOGGING = None


def main():

    parser = argparse.ArgumentParser(description="Tail RTLS Server")
    
    parser.add_argument('-D', '--debug', action='count', default=0)
    parser.add_argument('-L', '--logging', type=str, default=DEFAULT_LOGGING)
    parser.add_argument('-c', '--config', type=str, default=DEFAULT_CONFIG)
    
    args = parser.parse_args()

    if args.config:
        config.loadYAML(args.config)

    logger.initLogger(args.logging)

    
    server = Server()

    iprint('Tail RTLS daemon starting...')

    try:
        server.run()
        
    finally:
        server.stop()


if __name__ == "__main__": main()

