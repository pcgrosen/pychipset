import os
import mmap
import struct


NUM_PORTS = 256
PORT_SIZE = 2 ** 16
REGISTER_SIZE = 4

PORT_SHIFT = 16

class PCR:
    def __init__(self, base):
        self.base = base
        self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        self.backing = mmap.mmap(self.fd, NUM_PORTS * PORT_SIZE, offset=self.base)

    def __enter__(self):
        return self

    def __exit__(self, ex_t, ex_v, ex_tb):
        self.backing.close()
        os.close(self.fd)
        return False

    @staticmethod
    def _translate_address(port, offset):
        return (port << PORT_SHIFT) + offset

    def read_register(self, port, offset):
        addr = self._translate_address(port, offset)
        raw = self.backing[addr:addr + REGISTER_SIZE]
        return struct.unpack("<I", raw)[0]

    def write_register(self, port, offset, value):
        addr = self._translate_address(port, offset)
        raw = struct.pack("<I", value)
        self.backing[addr:addr + REGISTER_SIZE] = raw
