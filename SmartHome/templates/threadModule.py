from abc import ABC, abstractmethod
import threading

class cThreadModule:
    modules = []

    def __init__(self, period_s=None):
        self.period_s = period_s
        self.terminate = False

    def handle(self):
        self._handle()
        if not self.terminate or self.period_s is None:
            tmr = threading.Timer(self.period_s, self.handle)  # calling itself periodically
            tmr.start()
            cThreadModule.modules[self._type] = tmr
    @abstractmethod
    def _handle(self):
        pass

    @property
    def _type(self):
        return self.__class__.__name__

