from abc import ABC, abstractmethod
import threading

class cThreadModule:
    modules = {}
    logger = None

    def __init__(self, period_s=None):
        self.period_s = period_s
        self.terminate = False
        self.tmr = None

    def handle(self):
        threading.excepthook = self.exception_in_thread
        self._handle()
        if not self.terminate or self.period_s is None:
            self.tmr = threading.Timer(self.period_s, self.handle)  # calling itself periodically
            #self.tmr.daemon = True
            self.tmr.start()
            cThreadModule.modules[self._type] = self

    def exception_in_thread(self, args):
        self.logger.log(f"Exception in thread, ending! {args}")
        self.terminate = True
    @classmethod
    def checkTermination(cls):
        for name, module in cThreadModule.modules.items():
            if module.terminate:
                cThreadModule.logger.log(f"Terminating all threads, triggered by thread module {name}")
                cThreadModule.terminateAll()
                break

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

