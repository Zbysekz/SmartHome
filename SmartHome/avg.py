class cMovingAvg:
    def __init__(self, window_size):
        self.window_size = window_size

        self.buffer = []

    def append_value(self, value):
        if len(self.buffer) >= self.window_size:
            del self.buffer[0]
        else:
            self.buffer.append(value)
    @property
    def value(self):
        if len(self.buffer) > 0:
            return sum(self.buffer) / len(self.buffer)
        else:
            return None

