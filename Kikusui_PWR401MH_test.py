#!python3
# -*- coding:utf-8 -*-
"""

"""

import select,os,sys

from pyhislip import HiSLIP
from cVXI11 import Vxi11Device
from PyUSBTMC import USB488_device
from logging import info,warn,debug, error
import logging
logging.getLogger().setLevel(logging.DEBUG)

class PWR(HiSLIP):
    """
    This device support only synchronized mode. So it is safe to use ask(), anytime.
    SYST:ERR?\n *ESR?
    SYST:ERR:COUN?
    STAT:OPER? /STAT:OPER:COND?
    STAT:OPER:INST?
    STAT:QUES?
    SYST:COMM:RLST? 
    FETC[<n>]:ALL?/MEAS[<n>]:ALL?
    SYSTem:ERRor:TRACe ON|OFF
    """
    def __init__(self,host="192.168.2.5"):
        super(PWR, self).__init__()
        self.connect(host)
        self.po=select.poll()
        self.po.register(self.sync_channel,  select.POLLIN | select.POLLPRI)
        self.po.register(self.async_channel, select.POLLIN | select.POLLPRI)
        self.fd2chan=dict(((self.sync_channel.fileno(),  self.sync_channel),
                           (self.async_channel.fileno(), self.async_channel)))
        try:
            self.vdev=Vxi11Device(host.encode(),"inst0".encode())
        except:
            pass

    def write(self, data):
        super(PWR, self).write(data)
        return self.most_recent_message_id
    
    def poll(self):
        return self.po.poll(self.SOCKET_TIMEOUT)

    def read_waiting(self):
        return [
            self._read_hislip_message(self.fd2chan[fd])
            for fd, event in self.poll() if (event & select.POLLIN)
        ]
        
    def readstb(self):# status_query
        """
        message_types["AsyncStatusQuery"] = 21                   # C, A
        message_types["AsyncStatusResponse"] = 22                # S, A
        """
        msg=self._create_hislip_message(self.message_types["AsyncStatusQuery"],
                                        self.rmt_delivered,
                                        self.most_recent_message_id,
                                        "")
        self.async_channel.send(msg)
        po=select.poll()
        po.register(self.async_channel, select.POLLIN | select.POLLPRI)
        po.poll()
        hdr,data=self._read_hislip_message(self.async_channel, self.message_types["AsyncStatusResponse"])
        return hdr['control_code']

    def OPC(self,callback=None):
        self.write("*OPC")
        po=select.poll()
        po.register(self.async_channel, select.POLLIN | select.POLLPRI)
        def wait_srq(callback=callback):
            po.poll()
            hdr,data=self._read_hislip_message(self.async_channel, self.message_types["AsyncServiceRequest"])

        
def test(host="192.168.2.5"):
    dev=PWR(host)
    dev.set_max_message_size(1024)
    print("actual maximum message size is:",dev.MAXIMUM_MESSAGE_SIZE)
    sys.stdout.flush()
    print("Overlap_mode:",dev.overlap_mode)
    dev.device_clear()
    print("Overlap_mode after_device clear:",dev.overlap_mode)
    dev.request_lock() # exclusive lock
    print (dev.ask("*IDN?;"))
    print (dev.ask("*IDN?;", reqRaw=True))
    #print (dev.vdev.qIDN())
    dev.release_lock()
    print ("lock info",dev.lock_info())
    return dev

def test_SRQ(dev):
    import time
    print("SRQ test:")
    dev.write("*CLS;")
    dev.write("TRIG:TRAN:SOUR BUS")
    dev.write("INIT:TRAN")# 'イニシエート
    print("*ESE:", dev.ask("*ESE?"))
    print("*ESE:", dev.ask("*ESE?",reqRaw=True))
    print("*SRE:", dev.ask("*SRE?"), dev.status_query())
    print("*SRE:", dev.ask("*SRE?",reqRaw=True), dev.status_query())
    dev.write("*SRE 32")
    dev.write("*ESE 1")
    #dev.write("TRIG:TRAN") # ' ソフトウェアトリガを与える
    def callback(dev=dev):
        time.sleep(1.0)
    dev.start_SRQ_thread(callback=callback)
    s=time.time()
    print("thread status1:",dev.srq_thread.is_alive())
    #dev.write("TRIG:TRAN") # ' ソフトウェアトリガを与える
    dev.write("*CLS;*TRG;*OPC;")
    print("thread status2:",dev.srq_thread.is_alive())
    #dev.srq_lock.acquire()
    r=dev.srq_thread.join()
    print(r)
    e=time.time()-s
    debug("thread status3: thread_alive:{} dt:{:.3f}".format(dev.srq_thread.is_alive(),e))
    print(dev.status_query())
    while  [s for s,m in dev.poll() if (m & (~select.POLLOUT &0xff))]:
        print("resp",dev.read_waiting())
    print("*SRE",dev.ask("*SRE?",reqRaw=True))
    dev.write("*CLS;"); print("*STB", dev.ask("*STB?"), dev.status_query())
    dev.write("*CLS;"); print("*ESR", dev.ask("*ESR?"), dev.status_query())
    return 

def test_lock(dev):
    print("lock/rerease test\n")
    dev.request_lock("Shared Lock")
    print ("have a shared lock", dev.lock_info())
    dev.request_lock() # exclusive lock
    print ("have an exclusive lock",dev.lock_info())
    dev.release_lock()
    print ("have a shared lock",dev.lock_info())
    dev.release_lock()
    print ("have a no lock",dev.lock_info())    
    dev.request_lock() # exclusive lock
    print ("have an exclusive lock",dev.lock_info())
    dev.release_lock()
    print ("have no lock",dev.lock_info())    

def test_multi_response(dev):
    print("multi response test")
    print("operation mode:",dev.overlap_mode)

    print ("ask:", dev.ask("*IDN?"))
    print ("ask:", dev.ask("*IDN?",reqRaw=True))
    
    dev.write("*IDN?")
    print("write message ID:", dev.most_recent_message_id)
    print(" response",  dev.read_waiting())

    dev.write("*IDN?")
    print("message ID for *IDN?:", dev.most_recent_message_id)
    dev.write("*STB?")
    print("message ID for *STB?:", dev.most_recent_message_id)
    print("response", dev.read_waiting())
    print(dev.read_waiting())

    print ("write and ask")
    dev.write("*IDN?")
    print("message ID for *IDN?:", dev.most_recent_message_id)
    try:
        print("Ask STB:",dev.ask("*STB?"))
    except TypeError as m:
        print("Erro Msg",m)
    # message for "*IDN?;" is missing.
    finally:
        print("message ID for *STB?:", dev.most_recent_message_id)
        print("response",dev.read_waiting())
        print(dev.read_waiting())
    dev.write("*IDN?;*STB?")
    print("write message ID:", dev.most_recent_message_id)
    print("response:",dev.read_waiting())
    
def test_multi_response_vxi11(dev):
    print("vxi11 test")
    dev=dev.vdev

    print ("ask:", dev.ask("*IDN?"))
    
    dev.write("*IDN?")
    print(" response",  dev.read())

    dev.write("*IDN?")
    dev.write("*STB?") # in cVXI11, the previous command will be ignored.
    print("responce",dev.read())
    print(dev.read())

    dev.write("*IDN?")
    dev.ask("*STB?") # in cVXI11, the previous command will be ignored.
    print("responce",dev.read())

    print("response to a combined message")
    dev.write("*IDN?;*STB?")
    print("response:",dev.read())

def main(host="192.168.2.5"):
    dev=test(host)
    test_lock(dev)
    test_multi_response(dev)
    test_SRQ(dev)
    print("make sure no more input from device\n")
    while dev.poll():
        dev.read_waiting()
    test_lock(dev)
    
if __name__ == "__main__":
    main("169.254.100.192")
