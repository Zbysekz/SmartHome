from logger import Logger
from tcpServer import cTCPServer
import time
from databaseMySQL import cMySQL
from templates.threadModule import cThreadModule
from parameters import parameters

# for periodicity mysql inserts
HOUR = 3600
MINUTE = 60

class cDevice:
    def __init__(self, name, ip_address, timeout_s=None, critical=False):
        self.name = name
        self.ip_address = ip_address
        self.timeout_s = timeout_s
        self.critical = critical
        self.last_activity = None

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
        return [device for device in list if device.handle_timeout()]

    @classmethod
    def get_ip(cls, name, list):
        for item in list:
            if item.name == name:
                return item.ip_address
        return None

class cCommProcessor(cThreadModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = Logger("main", verbosity=Logger.FULL)
        self.devices = {cDevice('IP_METEO', '192.168.0.10', HOUR * 3),
                      cDevice('IP_KEYBOARD', '192.168.0.11', 120),
                      cDevice('IP_ROOMBA', '192.168.0.13'),
                      cDevice('IP_RACKUNO', '192.168.0.5', 200),
                      cDevice('IP_PIR_SENSOR', '192.168.0.14', MINUTE * 10),
                      cDevice('IP_SERVER', '192.168.0.3'),  # it is localhost
                      cDevice('IP_POWERWALL', '192.168.0.12',100, critical=True),
                      cDevice('IP_KEGERATOR', '192.168.0.35', MINUTE * 10),
                      cDevice('IP_CELLAR', '192.168.0.33', MINUTE * 10),
                      cDevice('IP_POWERWALL_THERMOSTAT', '192.168.0.32', MINUTE * 10, critical=True),
                      cDevice('IP_ESP_POWERWALL', '192.168.0.15', 100),
                      cDevice('IP_VICTRON_INVERTER', '192.168.0.16', MINUTE * 10)}

        self.keyboardRefreshCnt = 0
        self.wifiCheckCnt = 0

        self.mySQL = cMySQL()
        self.logger.log(f"Initializing TCP port {parameters.SERVER_PORT} on IP:{parameters.SERVER_IP} ...")
        self.TCP_server = cTCPServer()
        self.house_security = None


        initTCP = True
        nOfTries = 0
        while initTCP:
            try:
                self.TCP_server.init()
                self.TCP_server.handle()
                initTCP = False  # succeeded
            except OSError as e:
                nOfTries += 1
                if (nOfTries > 30):
                    raise Exception('Too much tries to create TCP port', ' ')
                print("Trying to create TCP port again..")
                time.sleep(10)

        self.logger.log("TCP port connected OK")

        self.mySQL.RemoveOnlineDevices()  # clean up online device table

    def _handle(self):
        if self.keyboardRefreshCnt >= 4:
            keyboardRefreshCnt = 0
            self.KeyboardRefresh()
            self.PIRSensorRefresh()
        else:
            self.keyboardRefreshCnt += 1

        if self.wifiCheckCnt >= 30:
            self.wifiCheckCnt = 0
            if not self.TCP_server.Ping("192.168.0.4"):
                self.logger.log("UNABLE TO REACH ROUTER!")
        else:
            self.wifiCheckCnt += 1

        timeout_devices_list = cDevice.get_timeout_devices(self.devices)
        for device in timeout_devices_list:
            if device.critical:
                self.logger.log(f"Lost critical device! IP:{device.ip_address}", Logger.CRITICAL)
            else:
                self.logger.log(f"Lost device! IP:{device.ip_address}", Logger.NORMAL)
            self.TCP_server.RemoveOnlineDevice(device.IP)


        # check if there are data in mysql that we want to send
        data = self.mySQL.getTxBuffer()
        if len(data):
            try:
                for packet in data:
                    byteArray = bytes([int(x) for x in packet[0].split(',')])
                    self.logger.log("Sending data from MYSQL database to:")

                    if packet[1] == parameters.IP_SERVER:
                        self.logger.log("LOCALHOST")
                        self.logger.log(byteArray)
                        self.ExecuteTxCommand(byteArray)
                    else:
                        self.logger.log(packet[1])
                        self.logger.log(byteArray)
                        self.TCP_server.Send(byteArray, packet[1], crc16=True)
            except ValueError:
                self.logger.log("MySQL - getTXbuffer - Value Error:" + str(packet[0]))

    def ExecuteTxCommand(self, data):
        if data[0] == 0:  # resetAlarm
            self.logger.log("Alarm deactivated by Tx interface.")
            self.house_security.unlock_house()
        elif data[0] == 1:
            self.MySQL.insertValue('status', 'heatingControlInhibit', False)
            self.logger.log("Stop heating control by Tx command")
        elif data[0] == 2:
            self.MySQL.insertValue('status', 'heatingControlInhibit', True)
            self.logger.log("Start heating control by Tx command")

    def PIRSensorRefresh(self):
        self.logger.log("PIR sensor refresh!", Logger.FULL)

        self.TCP_server.send(self.mySQL, bytes([0, int(self.house_security.alarm != 0), int(self.house_security.locked)]),  cDevice.get_ip("IP_PIR_SENSOR", self.devices))  # id, alarm(0/1),locked(0/1)

    def KeyboardRefresh(self):
        self.logger.log("Keyboard refresh!", Logger.FULL)
        val = (int(self.house_security.alarm != 0)) + 2 * (int(self.house_security.locked))

        self.TCP_server.send(self.mySQL, bytes([10, val]), cDevice.get_ip("IP_KEYBOARD", self.devices))  # id, alarm(0/1),locked(0/1)

