#!/usr/bin/env python
import logging
import serial

logger = logging.getLogger('paradox_mqtt').getChild(__name__)


class Serial_Connection():

    def __init__(self,
                 port='/dev/ttyUSB0',
                 baudrate=9600,
                 timeout=5,
                 rtscts=False):
        """Initialise Serial_Connection."""
        logger.debug("Initialising Serial_Connection...")
        self.connection = None
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.rtscts = rtscts
        logger.debug("Initialised Serial_Connection.")

    def connect(self):
        """Connect to serial port."""
        logger.debug("Connecting to serial port...")
        self.connection = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            rtscts=self.rtscts)
        try:
            self.connection.open()
            logger.debug("Connected to serial port.")
            return True
        except:
            logger.error("Could not connect to serial port.")
            return False

    def write(self, data):
        """Write data to serial port."""
        self.connection.write(data)

    def read(self, bytes=37, timeout=1):
        """Read bytes from serial port waiting up to timeout."""
        old_timeout = self.connection.timeout
        self.connection.timeout = timeout
        data = self.connection.read(bytes)
        self.connection.timeout = old_timeout
        return data

    def in_waiting(self):
        """Check how many butes are waiting on connection."""
        return self.connection.in_waiting

    def reset_input_buffer(self):
        """Clear input buffer."""
        return self.connection.reset_input_buffer()

    def reset_output_buffer(self):
        """Clear output buffer."""
        return self.connection.reset_output_buffer()
