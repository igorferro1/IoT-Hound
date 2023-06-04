import threading, random, time, datetime
from . import Sniffer
from logs.logger import logger
from devices.device import Device
from devices.network import Network
from serial import Serial, SerialException


class ZigBeeSniffer(Sniffer.Sniffer, threading.Thread):

    def __init__(self, serialport, baudrate):
        super().__init__(serialport, baudrate, type='ZigBee')

        self.oldChannels = []
        self.channels = []
        valueTimeout = 10
        self.serial = Serial(serialport, baudrate, timeout=valueTimeout)
        self.devices = {}
        self.networks = {}
        self.logger = logger
        self.restart = False

    def start(self, add_zigbee_device_row, update_zigbee_device_row, remove_zigbee_device_row,
              add_zigbee_network_row, update_zigbee_network_row, remove_zigbee_network_row):
        # device row operations
        self.add_zigbee_device_row = add_zigbee_device_row
        self.remove_zigbee_device_row = remove_zigbee_device_row
        self.update_zigbee_device_row = update_zigbee_device_row
        # network row operations
        self.add_zigbee_network_row = add_zigbee_network_row
        self.update_zigbee_network_row = update_zigbee_network_row
        self.remove_zigbee_network_row = remove_zigbee_network_row

        self.running = True
        super().start()

    def stop(self):
        self.running = False
        self.serial.close()

    def findChannels(self):

        for _ in range(1):
            for channel in range(11, 27):

                self.serial.reset_input_buffer()
                timeout_start = time.time()
                self.serial.write("receive\r\n".encode())
                rec = self.serial.readline()
                self.serial.write("channel {}\r\n".format(channel).encode())
                rec = self.serial.readline()
                rec = None

                while time.time() < timeout_start + 10:

                    rec = self.serial.readline()

                    if not rec:
                        break

                    if (rec.decode().split())[0] == "channel":
                        continue
                        
                    elif channel not in self.channels:
                        self.channels.append(channel)
                        self.serial.reset_input_buffer()
                        break

    def sniff(self):
        if not self.channels:
            return

        for channel in self.channels:
            self.dataVal = 0
            timeout_start = time.time()
            self.serial.write("channel {}\r\n".format(channel).encode())
            
            rec = self.serial.readline()
            rec = None

            while time.time() < timeout_start + random.randint(20, 30):

                if not self.running or self.restart:
                    self.restart = False
                    return

                rec = self.serial.readline()

                if not rec:
                    continue

                if (rec.decode().split())[0] == "channel":
                    continue

                message = (rec.decode().split())[1]
                rssi = (rec.decode().split())[3]

                # Convert the message in hex to binary with padding
                messageBinSize = len(message) * 4
                messageBin = (bin(int(message, 16))[2:]).zfill(messageBinSize)

                frameTypeIEEE = messageBin[5:8]
                addressingModeIEEE = messageBin[8:10]
                destAddrModeIEEE = messageBin[12:14]
                intraPAN = messageBin[1]


                # First: Get the Frame Control Field bits that matter (Frame type and source addressing mode)

                
                # Doing the bytes checks
                if (frameTypeIEEE != "010" and addressingModeIEEE == "10" and destAddrModeIEEE == "10" and intraPAN == "1"):
                    extAddr = ""

                    srcAddress = message[16:18] + message[14:16]
                    value = "Source address: " + \
                        srcAddress + ", RSSI: " + \
                        rssi + ", Channel: " + \
                            str(channel) + ", Type: " + frameTypeIEEE

                    # If it is a frame type of data, then it has the upper layers heaers and we can explore the extended addresses.
                    if (frameTypeIEEE == "001"):

                        # If the bit for extended source on the FCF on the Network layer is true, then we can get the address from there
                        if (int(messageBin[83])):
                            extAddr = ""
                            for i in range(0, 16, 2):
                                extAddr = message[34+i:36+i] + extAddr
                                if (i != 14):
                                    extAddr = ":" + extAddr

                        elif (messageBin[138] == "1"):
                            extAddr = ""
                            for i in range(0, 16, 2):
                                extAddr = message[44+i:46+i] + extAddr
                                if (i != 14):
                                    extAddr = ":" + extAddr
        
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    new_device = Device(address=srcAddress, name=(None, "Hub")[srcAddress == "0000"], RSSI=rssi, type='ZigBee', channel=channel, extAddress=extAddr, timestamp=timestamp)

                    if (srcAddress == "0000" and intraPAN == "1"):
                        panID = message[8:10] + message[6:8]
                        new_network = Network(ID=panID, RSSI=rssi, channel=channel, type="ZigBee", timestamp=timestamp)
                        self.addOrUpdateNetwork(new_network)

                    self.addOrUpdateDevice(new_device)

    def run(self):
        while self.running:
            try:
                if not self.channels:
                    self.findChannels()
                else:
                    self.sniff()

            except SerialException as e:
                self.logger.error(f'Error while reading data from nRF ZigBee Sniffer serial: {e}')
            except Exception as e:
                self.logger.error(f'Error in ZigbeeSniffer thread: {e}')

    def addOrUpdateDevice(self, new_device):
        
        # Update existing device
        if( new_device.key in self.devices):
            device = self.devices[new_device.key]
            if (device.RSSI != new_device.RSSI):
                device.RSSI = new_device.RSSI
                self.update_zigbee_device_row(new_device.key, "RSSI", new_device.RSSI)
            if(device.name != new_device.name and new_device.name != ""):
                device.name = new_device.name
                self.update_zigbee_device_row(new_device.key, "name", new_device.name)
            if(device.extAddress != new_device.extAddress and new_device.extAddress != "" and new_device.extAddress):
                device.extAddress = new_device.extAddress
                self.update_zigbee_device_row(new_device.key, "extAddress", new_device.extAddress)
            if(device.timestamp != new_device.timestamp):
                device.timestamp = new_device.timestamp
                self.update_zigbee_device_row(new_device.key, "timestamp", new_device.timestamp)
        
        # Add new device
        else:
            self.devices[new_device.key] = new_device
            self.add_zigbee_device_row(new_device)

    def addOrUpdateNetwork(self, new_network):
        key = new_network.key

        # Update existing network
        if(key in self.networks):
            network = self.networks[new_network.key]
            key = network.key
            if(network.RSSI != new_network.RSSI):
                network.RSSI = new_network.RSSI
                self.update_zigbee_network_row(key, "RSSI", new_network.RSSI)
            if(network.timestamp != new_network.timestamp):
                network.timestamp = new_network.timestamp
                self.update_zigbee_network_row(key, "timestamp", new_network.timestamp)
        
        # Add new network
        else:
            self.networks[key] = new_network
            self.add_zigbee_network_row(new_network)

    def setChannel(self, channel):
        if (not self.oldChannels):
            self.oldChannels = self.channels
        self.restart = True
        self.channels = []
        self.channels.append(channel)

    def unsetChannel(self):
        self.restart = True
        self.channels = self.oldChannels
        self.oldChannels = []
