import os
import mmap
import struct
from ..pci import PCI, constants as pci_const


NUM_PORTS = 256
PORT_SIZE = 2 ** 16
REGISTER_SIZE = 4

PORT_SHIFT = 16

class PCR:
    def __init__(self, base):
        self.base = base
        self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        self.backing = mmap.mmap(self.fd, NUM_PORTS * PORT_SIZE, offset=self.base)

    def close(self):
        self.backing.close()
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, ex_t, ex_v, ex_tb):
        self.close()
        return False

    @staticmethod
    def find_pcr_base():
        with PCI(method=pci_const.PCI_ACCESS_I386_TYPE1) as pci:
            dev = pci.get_device(0, 0, 31, 1)
            dev.caching = False
            original = dev.read_long(0xe0)
            try:
                dev.write_long(0xe0, original & ~0x100)
                pcr_base = dev.base_addr[0]
            finally:
                dev.write_long(0xe0, original)
        return pcr_base & pci_const.PCI_BASE_ADDRESS_MEM_MASK

    @staticmethod
    def get_pcr_size():
        return NUM_PORTS * PORT_SIZE

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

class Register:
    """
    A convenience representation of a 32-bit register in the PCR.

    This interface supports three masks, `always_one`, `always_zero`, and `no_modify`,
    that allow for automatic setting of certain bits during writes.
    """
    def __init__(self, pcr, port, offset, always_one=0, always_zero=0, no_modify=0):
        if always_one & always_zero or always_one & no_modify or always_zero & no_modify:
            raise ValueError("always_one, always_zero, and no_modify cannot share bits")

        self.pcr = pcr
        self.port = port
        self.offset = offset
        self.always_one = always_one
        self.always_zero = always_zero
        self.no_modify = no_modify

    def read(self):
        return self.pcr.read_register(self.port, self.offset)

    def _augment_value(self, val, old=None):
        val |=  self.always_one
        val &= ~self.always_zero
        if self.no_modify != 0:
            if old is None:
                old = self.read()
            val &= ~self.no_modify
            val |= old & self.no_modify
        return val

    def get_relevance_mask(self):
        return ~(self.always_one | self.always_zero | self.no_modify)

    def write(self, value, old=None):
        real = self._augment_value(value, old=old)
        self.pcr.write_register(self.port, self.offset, real)
        return real
