from logger import Logger
from tcpServer import cTCPServer
import time
from databaseMySQL import cMySQL
from templates.threadModule import cThreadModule
from parameters import parameters
from comm.device import cDevice
import datetime

# for periodicity mysql inserts
HOUR = 3600
MINUTE = 60


class cCommProcessor(cThreadModule):
    devices = {cDevice('METEO', '192.168.0.10', HOUR * 3),
               cDevice('KEYBOARD', '192.168.0.11', 120),
               cDevice('ROOMBA', '192.168.0.13'),
               cDevice('RACKUNO', '192.168.0.5', 200, critical=True),
               cDevice('PIR_SENSOR', '192.168.0.14', MINUTE * 10),
               cDevice('SERVER', '192.168.0.3'),  # it is localhost
               cDevice('POWERWALL', '192.168.0.12', 100, critical=True),
               cDevice('KEGERATOR', '192.168.0.35', MINUTE * 10),
               cDevice('CELLAR', '192.168.0.33', MINUTE * 10),
               cDevice('POWERWALL_THERMOSTAT', '192.168.0.32', MINUTE * 30, critical=True),
               cDevice('ESP_POWERWALL', '192.168.0.15', 100),
               cDevice('VICTRON_INVERTER', '192.168.0.16', MINUTE * 10),
               cDevice('MARTHA_TENT', '192.168.0.37', MINUTE * 10),
               cDevice('ISPINDEL1', '192.168.0.34', MINUTE * 120),
               cDevice('OLD_FRIDGE_THERMOSTAT', '192.168.0.36', MINUTE * 600),
               cDevice('GEIGER_MULLER_COUNTER', '192.168.0.39', MINUTE * 10)}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mySQL = cMySQL()

        self.logger = Logger("commProcessor", verbosity=parameters.VERBOSITY, mySQL=self.mySQL)

        self.keyboardRefreshCnt = 0
        self.wifiCheckCnt = 0


        self.logger.log(f"Initializing TCP port {parameters.SERVER_PORT} on IP:{parameters.SERVER_IP} ...")
        self.TCP_server = cTCPServer(period_s=1)
        self.TCP_server.devices = cCommProcessor.devices
        self.house_security = None

        initTCP = True
        nOfTries = 0
        while initTCP:
            try:
                self.TCP_server.init()
                initTCP = False  # succeeded
            except OSError as e:
                nOfTries += 1
                if (nOfTries > 30):
                    raise Exception('Too much tries to create TCP port', ' ')
                print(f"Trying to create TCP port again..{repr(e)}")

                time.sleep(10)

        self.logger.log("TCP port connected OK")

        self.mySQL.RemoveOnlineDevices()  # clean up online device table

    def _handle(self):
        self.mySQL.PersistentConnect()
        if self.keyboardRefreshCnt >= 40:
            self.keyboardRefreshCnt = 0
            self.KeyboardRefresh()
            self.PIRSensorRefresh()
        else:
            self.keyboardRefreshCnt += 1

        if self.wifiCheckCnt >= 30:
            self.wifiCheckCnt = 0
            if not self.TCP_server.Ping("192.168.0.1"):
                self.logger.log("UNABLE TO REACH ROUTER!")
        else:
            self.wifiCheckCnt += 1

        timeout_devices_list = cDevice.get_timeout_devices(cCommProcessor.devices)
        for device in timeout_devices_list:
            if device.critical:
                self.logger.log(f"Lost critical device! {str(device)}", Logger.CRITICAL)
            else:
                self.logger.log(f"Lost device! {str(device)}", Logger.NORMAL)
            self.TCP_server.RemoveOnlineDevice(self.mySQL, device.ip_address)


        # check if there are data in mysql that we want to send
        data = self.mySQL.getTxBuffer()
        if len(data):
            try:
                for packet in data:
                    ip = packet[1]
                    byteArray = bytes([int(x) for x in packet[0].split(',')])
                    self.logger.log("Sending data from MYSQL database to:")

                    if packet[1] == parameters.SERVER_IP:
                        self.logger.log("LOCALHOST")
                        self.logger.log(byteArray)
                        self.ExecuteTxCommand(byteArray)
                    else:
                        device = cDevice.get_device(ip, cCommProcessor.devices)
                        self.logger.log(str(device))
                        self.logger.log(byteArray)
                        self.TCP_server.send(byteArray, ip, crc16=True)
            except ValueError as e:
                self.logger.log("MySQL - getTXbuffer - Value Error:" + str(packet[0]))
                self.logger.log_exception(e)
            except Exception as e:
                self.logger.log("MySQL - getTXbuffer - Exception:")
                self.logger.log_exception(e)
        self.mySQL.PersistentDisconnect()

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

        self.TCP_server.send(bytes([0, int(self.house_security.alarm != 0), int(self.house_security.locked)]),  cDevice.get_ip("PIR_SENSOR", cCommProcessor.devices))  # id, alarm(0/1),locked(0/1)

    def KeyboardRefresh(self):
        self.logger.log("Keyboard refresh!", Logger.FULL)
        val = (int(self.house_security.alarm != 0)) + 2 * (int(self.house_security.locked))

        #self.TCP_server.send(bytes([10, val]), cDevice.get_ip("KEYBOARD", cCommProcessor.devices))  # id, alarm(0/1),locked(0/1)

    def send_ack_keyboard(self, data):
        #self.TCP_server.SendACK(data, cDevice.get_ip("IP_KEYBOARD", cCommProcessor.devices))
        pass

    def heating_inhibition(self, on_off):
        self.logger.log(f"Rackuno inhibition {on_off}!", Logger.FULL)

        self.TCP_server.send(bytes([1, int(on_off)]), cDevice.get_ip("RACKUNO", cCommProcessor.devices))  # id, alarm(0/1),locked(0/1)

    def switch_to_grid(self):
        self.TCP_server.send(bytes([3]), cDevice.get_ip("RACKUNO", cCommProcessor.devices))  # Switch to GRID command

    def switch_to_solar(self):
        self.TCP_server.send(bytes([4]), cDevice.get_ip("RACKUNO", cCommProcessor.devices))  # Switch to SOLAR command
    def send_clock(self, ip):
        now = datetime.datetime.now()
        self.TCP_server.send(bytes([66, now.hour, now.minute]), ip)