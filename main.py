import tkinter as tk
import signal, os
from gui.gui import GUI
from sniffers.BLE_Sniffer import BLESniffer
from sniffers.WiFi_Sniffer import WiFiSniffer
from sniffers.ZigBee_Sniffer import ZigBeeSniffer

MyBLESniffer = None
MyWiFiSniffer = None
MyZigBeeSniffer = None

def signal_handler(sig, frame):
    on_closing()

def on_closing():
    try: 
        MyBLESniffer.stop()
    except Exception as e:
        pass
    try:
        MyWiFiSniffer.stop()
    except Exception as e:
        pass
    try:
        MyZigBeeSniffer.stop()  
    except Exception as e:
        pass
    os._exit(1)

def main():   
    # Create Sniffers
    global MyBLESniffer, MyWiFiSniffer, MyZigBeeSniffer

    MyBLESniffer = BLESniffer(serialport="COM3", baudrate=1000000) # change serialport to match with the corresponding serial port number of BLE sniffer
    MyWiFiSniffer = WiFiSniffer(serialport="COM5", baudrate=115200) # change serialport to match with the corresponding serial port number of WiFi sniffer
    MyZigBeeSniffer = ZigBeeSniffer(serialport="COM7", baudrate=115200) # change serialport to match with the corresponding serial port number of WiFi sniffer


    signal.signal(signal.SIGINT, signal_handler)

    # Create the main window
    root = tk.Tk()
    root.title("IoT Hound")
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Create GUI instance
    gui = GUI(root, MyBLESniffer, MyWiFiSniffer, MyZigBeeSniffer)

    
    root.mainloop()
    

if __name__ == '__main__':
    main()