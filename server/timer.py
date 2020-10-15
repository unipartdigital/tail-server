#!/usr/bin/python3

import os
import time
import threading

from logger import *


_TIMER_EXP_WAIT    = 10e-3
_TIMER_MIN_WAIT    = 10e-6
_TIMER_EMPTY_WAIT  = 0.1


log = getLogger(__name__)


class Timer():

    def __init__(self, thread, delay, func=None, **args):
        self.thread  = thread
        self.armed   = False
        self.expired = False
        self.expiry  = None
        self.delay   = delay
        self.func    = func
        self.args    = args

    def expire(self):
        if self.armed:
            self.armed   = False
            self.expired = True
            if self.func:
                try:
                    self.func(**self.args)
                except Exception:
                    log.exception('Timer::expire() callback failed:')

    def arm(self, when=None, delay=None, rearm=False):
        if not self.armed:
            if when is None:
                if delay is None:
                    delay = self.delay
                if rearm and self.expiry is not None:
                    when = self.expiry + delay
                else:
                    when = time.time() + delay
            self.armed   = True
            self.expired = False
            self.expiry  = when
            self.thread.arm(self)
            log.debug(f'armed @ {when}')

    def unarm(self):
        if self.armed:
            self.thread.unarm(self)
            self.armed   = False
            self.expired = False
            log.debug(f'unarmed')


class PeriodicTimer(Timer):

    def expire(self):
        if self.armed:
            Timer.expire(self)
            self.arm(rearm=True)


class TimerThread(threading.Thread):
    
    def __init__(self):
        threading.Thread.__init__(self)
        self.running = False
        self.lock = threading.Condition()
        self.next = None
        self.list = []
        self.start()

    def Timer(self, delay, func, **args):
        return Timer(self,delay,func,**args)

    def update_next(self):
        if self.list:
            self.next = min(self.list,key=lambda tm: tm.expiry)
        else:
            self.next = None
    
    def arm(self,timer):
        self.lock.acquire()
        self.list.append(timer)
        self.update_next()
        self.lock.notify_all()
        self.lock.release()

    def unarm(self,timer):
        self.lock.acquire()
        if timer in self.list:
            self.list.remove(timer)
            self.update_next()
            self.lock.notify_all()
        self.lock.release()

    def wait(self,timer):
        self.lock.acquire()
        while self.running and timer.armed and not timer.expired:
            self.lock.wait()
        self.lock.release()

    def run(self):
        self.lock.acquire()
        self.running = True
        while self.running:
            if self.next:
                timed = self.next
                sleep = timed.expiry - time.time()
                if sleep < _TIMER_MIN_WAIT:
                    self.list.remove(timed)
                    self.update_next()
                    timed.expire()
                    self.lock.notify_all()
                else:
                    if sleep > _TIMER_EXP_WAIT:
                        self.lock.wait(sleep)
                    else:
                        self.lock.wait(sleep / 2)
            else:
                self.lock.wait(_TIMER_EMPTY_WAIT)
        self.lock.release()

    def stop(self):
        self.lock.acquire()
        self.running = False
        self.lock.notify_all()
        self.lock.release()

