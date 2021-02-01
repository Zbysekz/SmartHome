
import time

class MeasureTime:
    def __init__(self):
        self.timestamp = 0
        self.printTmr = time.time()

        self.period_max = 0
        self.period_avg = 0
        self.cnt = 0
        self.last_period = 0

    def Start(self):
        self.timestamp = time.time()

    def Measure(self):

        self.last_period = time.time() - self.timestamp


        self.period_avg += self.last_period
        self.cnt += 1

        self.period_max = max(self.last_period,self.period_max)

    def PrintOncePer(self, seconds, printCallback, prefix):
        if time.time() - self.printTmr > seconds:
            printCallback(prefix + " : cycle time [avg,max]:"+"{:.1f}, {:.1f}".format((self.period_avg/self.cnt),self.period_max))
            self.period_max = 0
            self.period_avg = 0
            self.cnt = 0
            self.printTmr = time.time()

    def getMaxPeriod(self):
        return self.period_max

    def getLastPeriod(self):
        return self.last_period