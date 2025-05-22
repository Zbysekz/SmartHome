import logging
from abc import ABC, abstractmethod
import threading
import traceback
from logger import Logger

class cThreadModule:
    modules = {}
    logger = None

    def __init__(self, period_s=None):
        self.period_s = period_s
        self.terminate = False
        self.tmr = None
        cThreadModule.logger.log(f"Spawned thread {self._type}")

    def handle(self):
        threading.excepthook = self.exception_in_thread
        self._handle()
        if not self.terminate and self.period_s is not None:
            self.tmr = threading.Timer(self.period_s, self.handle)  # calling itself periodically
            #self.tmr.daemon = True
            self.tmr.start()
            cThreadModule.modules[self._type] = self

    def exception_in_thread(self, args):
        txt = f"Exception in thread for '{self._type}', ending! {args} "
        txt += ''.join(traceback.format_tb(args.exc_traceback)) if hasattr(args,"exc_traceback") else "no info"
        self.logger.log(txt, Logger.CRITICAL)
        self.terminate = True

    @classmethod
    def checkTermination(cls):
        result = False

        for name, module in cThreadModule.modules.items():
            if module.terminate:
                cThreadModule.logger.log(f"Terminating all threads, triggered by thread module {name}")

                cThreadModule.terminateAll()
                result = True
                break
        return result


    @classmethod
    def terminateAll(cls):
        for name, module in cThreadModule.modules.items():
            module.terminate = True
    @abstractmethod
    def _handle(self):
        pass

    @property
    def _type(self):
        return self.__class__.__name__

