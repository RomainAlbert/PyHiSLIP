# -*- coding: utf-8 -*-

'''
This module provide HiSLIP protocol client work.

Created on 28 feb 2017

@author: Levshinovskiy Mikhail

modified by N.Yamamoto@kek.jp May 7,2020.
'''

import socket
import struct
from time import sleep

from collections import OrderedDict
from select import poll, POLLIN, POLLPRI
import threading
from logging import warn,debug,info,error


class HiSLIPFatalError(Exception):
    '''
    Exception raised up for HiSLIP fatal errors
    '''

    def __init__(self, expression, message):
        self.expression = expression
        self.message = message

class HiSLIPError(Exception):
    '''
    Exception raised up for HiSLIP errors
    '''

    def __init__(self, expression, message):
        self.expression = expression
        self.message = message

class _HiSLIP(object):
    '''
    This class is abstract and content main methods and attributes for HiSLIP protocol
    '''
    # class constants.
    _Default_Port=4880  # HiSLIP default port number

    
    # Maximum supported protocol version
    _PROTOCOL_VERSION_MAX = 257  # <major><minor> = <1><1> that is 257
    _INITIAL_MESSAGE_ID = 0xffffff00
    _UNKNOWN_MESSAGE_ID  = 0xffffffff
    
    # Maximum Message Size
    _MAXIMUM_MESSAGE_SIZE = 272  # Following VISA 256 bytes + header length 16 bytes

    # Socket timeout
    _SOCKET_TIMEOUT = 1

    # Lock timeout
    _LOCK_TIMEOUT = 3000
    #
    '''
        Initialize dictionary, that storage HiSLIP message types

        Comment use order "Sender", "Channel"
        In the Sender column :
            S indicates Server generated message
            C indicates Client generated message
            E indicates A message that may be generated by either the client or server
        In the channel column :
            S indicates Synchronous channel message
            A indicates Asynchronous channel message
            E indicates A message that may be send on either the synchronous or asynchronous channel
    '''
    message_types=OrderedDict((
        ('Initialize', 0),                          # C, S
        ('InitializeResponse', 1),                  # S, S
        ('FatalError', 2),                          # E, E
        ('Error', 3),                               # E, E
        ('AsyncLock', 4),                           # C, S
        ('AsyncLockResponse', 5),                   # S, A
        ('Data', 6),                                # E, S
        ('DataEnd', 7),                             # E, S
        ('DeviceClearComplete', 8),                 # C, S
        ('DeviceClearAcknowledge', 9),              # S, S
        ('AsyncRemoteLocalControl', 10),            # C, A
        ('AsyncRemoteLocalResponse', 11),           # S, A
        ('Trigger', 12),                            # C, S
        ('Interrupted', 13),                        # S, S
        ('AsyncInterrupted', 14),                   # S, A
        ('AsyncMaximumMessageSize', 15),            # C, A
        ('AsyncMaximumMessageSizeResponse', 16),    # S, A
        ('AsyncInitialize', 17),                    # C, A
        ('AsyncInitializeResponse', 18),            # S, A
        ('AsyncDeviceClear', 19),                   # C, A
        ('AsyncServiceRequest', 20),                # S, A
        ('AsyncStatusQuery', 21),                   # C, A
        ('AsyncStatusResponse', 22),                # S, A
        ('AsyncDeviceClearAcknowledge', 23),        # S, A
        ('AsyncLockInfo', 24),                      # C, A
        ('AsyncLockInfoResponse', 25)               # S, A
    ))
    #
    '''
        Create a list that storage HiSLIP fatal error codes
    '''
    fatal_error_codes = [
        'Unidentified error',                                          #0
        'Poorly formed message header',                                #1  
        'Attempt to use connection without both channels established', #2
        'Invalid Initialization Sequence',                             #3
        'Server refused connection due to maximum number of clients exceeded' #4
        # 5..127 reserved for HiSLIP extensions
        # 128..255 Device-defined errors
    ]

    '''
        Create a list that storage HiSLIP error codes
    '''
    error_codes = [
        'Unidentified error',               #0
        'Unrecognized Message Type',        #1
        'Unrecognized control code',        #2
        'Unrecognized Vendor Defined Message',#3
        'Message too large'                 #4
        # 5..127 reserved for HiSLIP extensions
        # 128..255 Device-defined errors
    ]
    
    def __init__(self):
        self.MAXIMUM_MESSAGE_SIZE=self._MAXIMUM_MESSAGE_SIZE
        self.SOCKET_TIMEOUT = self._SOCKET_TIMEOUT
        self.LOCK_TIMEOUT = self._LOCK_TIMEOUT 

    def _create_hislip_message(self, message_type, control_code=0, message_parameter=0, data=''):
        '''
        This method creates HiSLIP message following next format:
        <Prologue><Message Type><Control Code><Message Parameter><Payload Length><Data>
        where:
            Prologue: is ASCII “HS”
            Message Type: 1 byte, message identifier
            Control Code: 1 byte, general parameter of message.
                            If the field is not defined for a message, 0 shall be sent.
            Message Parameter: 4 bytes, include one or more parameters of message.
                            If the field is not defined for a message, 0 shall be sent.
            Payload Length: 8 bytes,  indicates the length in octets of the payload data contained in the message.
                            This field is an unsigned 64-bit integer
        '''
        message_dict = dict()

        # Prologue
        message_dict['prologue'] = b'HS'

        # Message Type
        try:
            message_dict['message_type'] = struct.pack('>B', message_type)
        except TypeError:
            raise TypeError('Message type TypeError!')

        # Control Code
        try:
            message_dict['control_code'] = struct.pack('>B', control_code)
        except TypeError:
            raise TypeError('Control Code TypeError!')

        # Message Parameter
        '''
        Currently message parameter supported only when:
            * 1 parameter with length 4 bytes
            * list of 2 parameters each length 2 bytes
        '''

        try:
            if type(message_parameter) == list:
                message_parameters = str().encode()
                for parameter in message_parameter:
                    if type(parameter) == str:
                        message_parameters = message_parameters + parameter.encode()
                    else:
                        message_parameters = message_parameters + struct.pack('>H', parameter)
                message_dict['message_parameter'] = message_parameters
            else:
                if type(message_parameter) == str:
                    message_dict['message_parameter'] = message_parameter.encode()
                else:
                    message_dict['message_parameter'] = struct.pack('>I', message_parameter)
        except TypeError:
            raise TypeError('Message parameter error!')

        # Payload Length

        try:
            message_dict['payload_length'] = struct.pack('>Q', len(data))
        except TypeError:
            raise TypeError('Payload length error!')

        # Data

        try:
            if type(data) != bytes:
                message_dict['data'] = data.encode()
            else:
                message_dict['data'] = data
        except TypeError:
            raise TypeError('Data type error!')

        message = message_dict['prologue'] + message_dict['message_type'] + message_dict['control_code'] + \
            message_dict['message_parameter'] + message_dict['payload_length'] + message_dict['data']

        return message

    def _read_socket(self, sock):
        ''' This method organize reciver of messages by socket TCP connection '''

        #data = str().encode()
        data = ""
        while True:
            try:
                sock.settimeout(self.SOCKET_TIMEOUT)
                current_data = sock.recv(self.MAXIMUM_MESSAGE_SIZE)
                data = data + current_data
            except socket.timeout:
                break
        return data

    def _split_hislip_header(self, header, expected_message_type=-1):
        '''
        This method tries to create dictionary following hislip protocol from gotten message.
        HiSLIP protocol has next format:
        <Prologue><Message Type><Control Code><Message Parameter><Payload Length><Data>
        where:
            Prologue: is ASCII “HS”
            Message Type: 1 byte, message identifier
            Control Code: 1 byte, general parameter of message.
                            If the field is not defined for a message, 0 shall be sent.
            Message Parameter: 4 bytes, include one or more parameters of message.
                            If the field is not defined for a message, 0 shall be sent.
            Payload Length: 8 bytes,  indicates the length in octets of the payload data contained in the message.
                            This field is an unsigned 64-bit integer

        '''

        message = OrderedDict()

        try:

            # Prologue
            message['prologue'] = header[0:2]

            # Message Type
            message['message_type'] = ord(header[2:3])

            # Control Code
            message['control_code'] = ord(header[3:4])

            # Message parameter
            raw_message_parameter = header[4:8]
            '''
            As i could mark, in all transaction except Initialize and InitializeResponce Message Parameter
            is 8-bit unsigned integer, so check and decode it.
            '''
            message['message_parameter'] = self._get_message_parameter(raw_message_parameter, message['message_type'])

            # Payload length
            message['payload_length'] = struct.unpack('>Q', header[8:16])[0]

        except (TypeError, NameError):
            ''' Raise fatal error, cause header has oncorrect format '''
            self._raise_fatal_error(1, 1)

        return message

    def _message_exceptions(self, header, data='', expected_message_type=-1):
        '''
        Catch HiSLIP exceptions and check correction of message
        '''

        # Prologue analyze
        if header['prologue'] != b'HS':
            self._raise_fatal_error(1, 1)

        # Compare Payload length with length of data
        if len(data) > 0 and header['payload_length'] != len(data):
            self._raise_fatal_error(1, 1)

        # Raise error if message length is bigger than MAXIMUM BUFFER SIZE without header length
        if header['payload_length'] > self.MAXIMUM_MESSAGE_SIZE:
            self._raise_error(4, 1)

        # Check if message is Fatal Error or Error
        if header['message_type'] == self.message_types['FatalError']:
            debug(data)
            self._raise_fatal_error(header['control_code'])
        elif header['message_type'] == self.message_types['Error']:
            debug(data)
            self._raise_error(header['control_code'])

        # Check if message type is expected
        if expected_message_type != -1:
            if header['message_type'] != expected_message_type:
                warn('Unexpectable message type!')
                self._raise_fatal_error(0, 1)

    def _get_message_parameter(self, raw_message_parameter, message_type):
        '''
        Decode message parameter
        '''
        if message_type == self.message_types['Initialize']:
            message_parameter = list()
            message_parameter.append(struct.unpack('>H', raw_message_parameter[0:2])[0])
            message_parameter.append(raw_message_parameter[2:4].decode())
        elif message_type == self.message_types['InitializeResponse']:
            message_parameter = list()
            message_parameter.append(struct.unpack('>H', raw_message_parameter[0:2])[0])
            message_parameter.append(struct.unpack('>H', raw_message_parameter[2:4])[0])
        else:
            message_parameter = struct.unpack('>I', raw_message_parameter)[0]

        return message_parameter

    def _read_hislip_data(self, raw_data, message_type=-1):
        '''
        Decode data. As i could mark, in all case, 
        except AsyncMaximumMessageSizeResponse data is byte string,
        check it and decode.
        modification by Yamamoto: 
        for Data and DataEnd, retusn Raw data for binaries in Osc.
        '''
        if message_type == self.message_types['AsyncMaximumMessageSizeResponse']:
            data = str(struct.unpack('>q', raw_data)[0])
        elif message_type in (self.message_types['Data'],self.message_types['DataEnd']):
            data=raw_data
        else:
            data=raw_data.decode()
        return data

    def _read_hislip_message(self, sock, expected_message_type=-1):
        ''' This method read hislip message '''

        # intialization
        sock.settimeout(self.SOCKET_TIMEOUT)
        raw_data = str()

        # read header and data
        try:
            raw_header = sock.recv(16)
            header = self._split_hislip_header(raw_header)
            if header['payload_length'] > 0:
                raw_data = sock.recv(header['payload_length'])
                data = self._read_hislip_data(raw_data, header['message_type'])
            else:
                data = str()
        except socket.timeout:
            self._raise_fatal_error(1, 1)
        self._message_exceptions(header, raw_data, expected_message_type)
        return header, data

    def set_timeout(self, timeout):
        ''' Set timeout for socket '''
        self.SOCKET_TIMEOUT = timeout

    def set_lock_timeout(self, timeout):
        ''' Set timeout in seconds for client, to wait lock from server '''
        self.LOCK_TIMEOUT = timeout

class HiSLIP(_HiSLIP):
    pass # to access class members in the HiSLIP declaration.

class HiSLIP(_HiSLIP):
    '''
    This class provide work of client part following HiSLIP protocol
    '''

    def __init__(self):
        super(HiSLIP, self).__init__()
        self.srq_lock=threading.Lock()

    def _read_hislip_message(self, sock, expected_message_type=-1):
        '''
            Except basic reading of HiSLIP message, we always shoud check RTM delivered from server
        '''
        [header, data] = super(HiSLIP, self)._read_hislip_message(sock, expected_message_type)
        self.rmt_delivered = self._RMT_delivered(header['message_type'], data)
        return header, data

    def _raise_fatal_error(self, error_code, source=0):
        '''
        Raise HiSLIPFatalError exception.

        Attributes:
            error code: error code following HiSLIP fatal error codes
            source: this parameter shows, was exception raised on client or server side. In case if
                    client is source of fatal error, send FatalError Transaction server
        '''

        error_message = 'HiSLIP Fatal Error!'
        error_expression = self.fatal_error_codes[error_code]

        if source == 1:
            self._send_fatal_error_to_server(error_code)

        raise HiSLIPFatalError(error_message, error_expression)

    def _send_fatal_error_to_server(self, error_code):
        message = self._create_hislip_message(self.message_types['FatalError'], error_code)
        self.sync_channel.send(message)
        try:
            peer=self.sync_channel.getpeername()
            self.sync_channel.close()
            self.async_channel.close()
            # reconnect to server
            self.connect(peer[0])
        except NameError:
            pass

    def _raise_error(self, error_code, source=0):
        '''
        Raise HiSLIPError exception.

        Attributes:
            error code: error code following HiSLIP error codes
            source: this parameter shows, was exception raised on client or server side. In case if
                    client is source of fatal error, send FatalError Transaction server
        '''

        error_message = 'HiSLIP Error!'
        error_expression = self.error_codes[error_code]

        if source == 1:
            self._send_error_to_server(error_code)

        raise HiSLIPError(error_message, error_expression)

    def _send_error_to_server(self, error_code):
        message = self._create_hislip_message(self.message_types['Error'], error_code)
        self.sync_channel.send(message)
        # self.sync_channel.close()
        # self.async_channel.close()
        raise TypeError('Error with code ' + str(error_code))

    def _RMT_delivered(self, message_type, data):
        '''
        Set RMT-delivered if delivered RMT
        '''
        rmt_delivered = False

        if len(data) >= 1:
            if message_type == self.message_types['DataEnd'] and data[len(data) - 1] == '\n':
                rmt_delivered = True

        return rmt_delivered

    def _add_new_line(self, data):
        ''' If sending data doesn't have '\n' in the end, add it '''
        if data[ - 1] != '\n':
            data = data + '\n'

        return data

    def connect(self, ip, sub_adress='hislip0', port=HiSLIP._Default_Port, vendor_id='ZL'):
        '''
        This method tries initialize connection to HiSLIP server, based on input parameters
        '''

        ''' Create Synchronized TCP connection '''
        self.sync_channel = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sync_channel.connect((ip, port))

        ''' Start the initialization, send protocol version and VendorID '''
        message = self._create_hislip_message(self.message_types['Initialize'],
                                              0,
                                              [self._PROTOCOL_VERSION_MAX, vendor_id],
                                              sub_adress)
        self.sync_channel.send(message)

        ''' Get answer from server '''
        header = self._read_hislip_message(self.sync_channel, self.message_types['InitializeResponse'])[0]

        ''' Get information from server answer '''

        # Get overlap/synchronize mode
        self.overlap_mode = header['control_code']
        # Get SessionID
        self.session_id = header['message_parameter'][1]

        ''' Create Asynchronized TCP connection '''
        self.async_channel = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.async_channel.connect((ip, port))

        ''' Start the asynchronize initialization, send SessionID '''
        message = self._create_hislip_message(
            self.message_types['AsyncInitialize'], 0, self.session_id)
        self.async_channel.send(message)

        ''' Get answer from server '''
        header = self._read_hislip_message(
            self.async_channel,
            self.message_types['AsyncInitializeResponse'])[0]
        self.server_vendorID=header['message_parameter']
        
        ''' Set work parameters '''
        self.message_id = self._INITIAL_MESSAGE_ID
        self.most_recent_message_id = self.message_id
        self.rmt_delivered = False

        """ for poll waiting """
        # poll object for sync_channel
        self.sync_poll=poll()
        self.sync_poll.register(self.sync_channel, POLLIN | POLLPRI)
        # poll object for async_channel
        self.async_poll=poll()
        self.async_poll.register(self.async_channel, POLLIN | POLLPRI)

    def set_max_message_size(self, message_size):
        '''  This method set maximal available message size '''

        # Create message and send it through async channel
        message = self._create_hislip_message(
            self.message_types['AsyncMaximumMessageSize'],
            0, 0,
            struct.pack('>q', message_size)
        )
        self.async_channel.send(message)

        data = self._read_hislip_message(
            self.async_channel,
            self.message_types['AsyncMaximumMessageSizeResponse']
        )[1]

        self.MAXIMUM_MESSAGE_SIZE = min(message_size, int(data))

    def status_query(self):
        ''' try to read MAV and status byte'''

        message = self._create_hislip_message(
            self.message_types['AsyncStatusQuery'],
            self.rmt_delivered,
            self.most_recent_message_id)

        self.async_channel.send(message)

        header = self._read_hislip_message(
            self.async_channel,
            self.message_types['AsyncStatusResponse']
        )[0]
        status = header['control_code']
        status &= 0xff # a contro_code is one byte data.
        mav = status & 0x10 # select bit 4
        #print "status:",mav,status
        return mav, status

    def _wait_for_answer(self, wait_time):
        ''' wait reply from server'''
        res=self.sync_poll.poll(wait_time)
        return res

    def increment_message_id(self):#3.1.2 Synchronized Mode Client Requirements
        self.most_recent_message_id = self.message_id
        self.message_id = (self.message_id + 2) & 0xffffffff # for wrap-around

    def write(self, data_str):
        ''' Method send "data" to server. "data" is string '''

        ''' Count maximal available length of message without header, what can be send in one transaction '''
        max_message_length = self.MAXIMUM_MESSAGE_SIZE - 16

        ''' If neccessary, and new line to data_str '''
        data_str = self._add_new_line(data_str)

        ''' Split original data-string. Get list of strings, where each string can be sent in one transaction '''
        data = [data_str[i:i + max_message_length] for i in range(0, (len(data_str) - len(data_str) % max_message_length), max_message_length)]
        if len(data_str) % max_message_length != 0:
            data.append(data_str[(len(data_str) // max_message_length) * max_message_length:len(data_str)])

        ''' Send data '''

        for i in range(len(data)):
            if i == len(data) - 1:
                message = self._create_hislip_message(self.message_types['DataEnd'], self.rmt_delivered, self.message_id, data[i])
            else:
                message = self._create_hislip_message(self.message_types['Data'], self.rmt_delivered, self.message_id, data[i])

            self.sync_channel.send(message)

            self.increment_message_id()

    def ask(self, data_str, wait_time = 3000, reqRaw=False):
        ''' Method send query to server and read answer '''

        # send request
        self.write(data_str)

        # we should wait till the time when information from device will be ready.
        self._wait_for_answer(wait_time)

        # read and analyze answer
        if reqRaw:
            full_data = b""
        else:
            full_data = str()
        eom = False
        while not eom:
            [header, data] = self._read_hislip_message(self.sync_channel)
            if not reqRaw:
                data=data.decode()
            if ((header['message_parameter'] == self.most_recent_message_id)
                or ( not self.overlap_mode and
                     (header['message_parameter'] == self._UNKNOWN_MESSAGE_ID)
                )
            ):
                if header['message_type'] == self.message_types['Data']:
                    full_data = full_data + data
                elif header['message_type'] == self.message_types['DataEnd']:
                    full_data = full_data + data
                    eom = True
                else:
                    self._raise_error(1, 1)
                    full_data = str()
                    break
            else:
                #self._raise_error(1, 1)
                full_data = str()
                break
        return full_data

    def lock_info(self):
        ''' This method get Lock information '''

        message = self._create_hislip_message(self.message_types['AsyncLockInfo'], 0, 0)

        self.async_channel.send(message)

        header = self._read_hislip_message(self.async_channel, self.message_types['AsyncLockInfoResponse'])[0]

        exclusive_lock = header['control_code']
        locks_granted = header['message_parameter']

        return exclusive_lock, locks_granted

    def device_clear(self):
        ''' Clear communication channel '''

        message = self._create_hislip_message(self.message_types['AsyncDeviceClear'], 0, 0)

        self.async_channel.send(message)

        header = self._read_hislip_message(self.async_channel, self.message_types['AsyncDeviceClearAcknowledge'])[0]

        feature_preference = header['control_code']

        message = self._create_hislip_message(self.message_types['DeviceClearComplete'], feature_preference, 0)
        self.sync_channel.send(message)

        header = self._read_hislip_message(self.sync_channel, self.message_types['DeviceClearAcknowledge'])[0]

        feature_setting = header['control_code']

        self.overlap_mode = feature_setting

        self.message_id = self._INITIAL_MESSAGE_ID
        self.most_recent_message_id = 0
        self.rmt_delivered = False

    def trigger_message(self):
        ''' This method emulate a GPIB Group Execute Trigger '''
        message = self._create_hislip_message(self.message_types['Trigger'], self.rmt_delivered, self.message_id)
        self.sync_channel.send(message)
        
        self.increment_message_id()

    def remote_local(self, request):
        '''
        This method realize GPIB-like remote/local control.
        Possible request values:
            0 - Disable remote
            1 - Enable remote
            2 - Disable remote and go to local
            3 - Enable remote and go to remote
            4 - Enable remote and lock out local
            5 - Enable remote, got to remote, and set local lockout
            6 - go to local without changing state of remote enable
        '''

        message = self._create_hislip_message(self.message_types['AsyncRemoteLocalControl'], request, self.most_recent_message_id)
        self.async_channel.send(message)

        self._read_hislip_message(self.async_channel, self.message_types['AsyncRemoteLocalResponse'])

    def request_lock(self, lock_string=''):
        ''' This method send lock request to server and get the answer.
            lock string:
                '' - exclusive lock
                any other - shared lock
        '''

        message = self._create_hislip_message(self.message_types['AsyncLock'], 1, self.LOCK_TIMEOUT, lock_string)
        self.async_channel.send(message)

        # read Answer
        header = self._read_hislip_message(self.async_channel, self.message_types['AsyncLockResponse'])[0]

        result = header['control_code']

        return result

    def release_lock(self):
        ''' this method release lock from server '''
        if self.most_recent_message_id == self._INITIAL_MESSAGE_ID:
            #message_id = self.most_recent_message_id - 2 ?
            message_id = 0
        else:
            message_id = self.most_recent_message_id

        message = self._create_hislip_message(self.message_types['AsyncLock'], 0, message_id)
        self.async_channel.send(message)

        # read answer
        header = self._read_hislip_message(self.async_channel, self.message_types['AsyncLockResponse'])[0]

        result = header['control_code']

        return result

    def release_srq_lock(self):
        debug( "releasing srq lock:{}".format(self.srq_lock.locked()))
        if self.srq_lock.locked():
            self.srq_lock.release()
        debug( "released srq lock:{}".format(self.srq_lock.locked()))
            
    def wait_for_SRQ(self, callback):
        self.async_poll.poll(None) # None: wait forever
        header = self._read_hislip_message(
            self.async_channel,
            self.message_types['AsyncServiceRequest']
        )[0]
        if callback:
            callback()
        self.release_srq_lock()
        debug("SRQ lock released {}".format(header))
        return
    
    def start_SRQ_thread(self, callback=None):
        if not self.srq_lock.locked():
            self.srq_lock.acquire()
        self.srq_thread=threading.Thread(
            name="SRQ_wait",
            target=self.wait_for_SRQ,
            args=(callback,)
        )
        self.srq_thread.start()
        debug("SRQ thread started")
