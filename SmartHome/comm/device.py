import time

class cDevice:
    def __init__(self, name, ip_address, timeout_s=None, critical=False):
        self.name = name
        self.ip_address = ip_address
        self.timeout_s = timeout_s
        self.critical = critical
        self.last_activity = None
        self.online = False

    def handle_timeout(self):
        if self.last_activity:
            if self.timeout_s is not None and time.time() - self.last_activity >= self.timeout_s:
                return True
            else:
                return False
        else:
            return False

    def mark_activity(self):
        self.last_activity = time.time()

    @classmethod
    def get_timeout_devices(cls, list):
        return [device for device in list if device.handle_timeout() and device.online]

    @classmethod
    def get_ip(cls, name, list):
        for item in list:
            if item.name == name:
                return item.ip_address
        return None

    @classmethod
    def get_name(cls, ip, list):
        for item in list:
            if item.ip_address == ip:
                return item.name
        return None

    @classmethod
    def get_device(cls, ip, list):
        for item in list:
            if item.ip_address == ip:
                return item
        return None

    @classmethod
    def get_device_by_name(cls, name, list):
        ip = cls.get_ip(name, list)
        for item in list:
            if item.ip_address == ip:
                return item
        return None

    def __str__(self):
        return f"{self.name}({self.ip_address})"

