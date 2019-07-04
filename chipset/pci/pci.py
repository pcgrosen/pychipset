import re
import struct
import argparse
from ._libpci import lib, ffi


constants = lib
PCI_ADDR_SIZE = ffi.sizeof(ffi.cast("pciaddr_t", 0))

class PCI:
    def __init__(self, method=lib.PCI_ACCESS_AUTO):
        self.access = lib.pci_alloc()
        self.access.method = method
        lib.pci_init(self.access)
        self.rescan_bus()

    def close(self):
        lib.pci_cleanup(self.access)

    def __enter__(self):
        return self

    def __exit__(self, ex_t, ex_v, ex_tb):
        self.close()
        return False

    def rescan_bus(self):
        lib.pci_scan_bus(self.access)

    @property
    def first_device(self):
        return Device(self.access.devices)

    @property
    def devices(self):
        return self.first_device

    def search_for_device(self, bus, device, function):
        """
        This function may return None if the system does not find a device at
        the specified address.
        """
        current = self.first_device
        while current:
            if current.bus == bus and \
               current.dev == device and \
               current.func == function:
                return current
            current = current.next
        return None

    def get_device(self, domain, bus, device, function):
        """
        This function will always return a device object, even if the system
        doesn't think that there is a device at the corresponding address.
        """
        raw = lib.pci_get_dev(self.access, domain, bus, device, function)
        if not raw:
            return None
        return Device(raw)

class Capability:
    def __init__(self, raw_cap):
        self.raw_cap = raw_cap

    @property
    def next(self):
        raw = self.raw_cap.next
        if not raw:
            return None
        return Capability(raw)

    @property
    def id(self):
        return self.raw_cap.id

    @property
    def type(self):
        return self.raw_cap.type

    @property
    def addr(self):
        return self.raw_cap.addr

class Device:
    def __init__(self, raw_dev, caching=False):
        self.raw_dev = raw_dev
        self.caching = caching

    def _fill(self, flags):
        flags |= 0 if self.caching else lib.PCI_FILL_RESCAN
        return lib.pci_fill_info(self.raw_dev, flags)

    @staticmethod
    def _safe_string(thing):
        if not thing:
            return None
        return ffi.string(thing)

    def clear_cache(self):
        lib.pci_fill_info(self.raw_dev, lib.PCI_FILL_RESCAN)

    @property
    def next(self):
        raw = self.raw_dev.next
        if not raw:
            return None
        return Device(raw)

    @property
    def bus(self):
        return self.raw_dev.bus

    @property
    def dev(self):
        return self.raw_dev.dev

    @property
    def func(self):
        return self.raw_dev.func

    @property
    def vendor_id(self):
        if not self._fill(lib.PCI_FILL_IDENT):
            return None
        return self.raw_dev.vendor_id

    @property
    def device_id(self):
        if not self._fill(lib.PCI_FILL_IDENT):
            return None
        return self.raw_dev.device_id

    @property
    def device_class(self):
        if not self._fill(lib.PCI_FILL_CLASS):
            return None
        return self.raw_dev.device_class

    @property
    def irq(self):
        if not self._fill(lib.PCI_FILL_IRQ):
            return None
        return self.raw_dev.irq

    @property
    def base_addr(self):
        if not self._fill(lib.PCI_FILL_BASES):
            return None
        return self.raw_dev.base_addr

    @property
    def sizes(self):
        if not self._fill(lib.PCI_FILL_SIZES):
            return None
        return self.raw_dev.size

    @property
    def rom_base_addr(self):
        if not self._fill(lib.PCI_FILL_ROM_BASE):
            return None
        return self.raw_dev.rom_base_addr

    @property
    def rom_size(self):
        res = self._fill(lib.PCI_FILL_ROM_BASE | lib.PCI_FILL_SIZES)
        if res & lib.PCI_FILL_ROM_BASE == 0 or res & lib.PCI_FILL_SIZES == 0:
            return None
        return self.raw_dev.rom_size

    @property
    def first_cap(self):
        if not self._fill(lib.PCI_FILL_CAPS):
            return None
        raw = self.raw_dev.first_cap
        if not raw:
            return None
        return Capability(raw)

    @property
    def phy_slot(self):
        if not self._fill(lib.PCI_FILL_PHYS_SLOT):
            return None
        return self._safe_string(self.raw_dev.phy_slot)

    @property
    def module_alias(self):
        if not self._fill(lib.PCI_FILL_MODULE_ALIAS):
            return None
        return self._safe_string(self.raw_dev.module_alias)

    @property
    def label(self):
        if not self._fill(lib.PCI_FILL_LABEL):
            return None
        return self._safe_string(self.raw_dev.label)

    @property
    def numa_node(self):
        if not self._fill(lib.PCI_FILL_NUMA_NODE):
            return None
        return self.raw_dev.numa_node

    @property
    def flags(self):
        if not self._fill(lib.PCI_FILL_IO_FLAGS):
            return None
        return self.raw_dev.flags

    @property
    def rom_flags(self):
        if not self._fill(lib.PCI_FILL_IO_FLAGS):
            return None
        return self.raw_dev.rom_flags

    @property
    def domain(self):
        return domain

    def find_capability(self, cap_id, cap_type):
        current = self.first_cap
        while current:
            if current.id == cap_id and current.type == cap_type:
                return current
            current = current.next
        return None

    def read_byte(self, pos):
        return lib.pci_read_byte(self.raw_dev, pos)

    def read_word(self, pos):
        return lib.pci_read_word(self.raw_dev, pos)

    def read_long(self, pos):
        return lib.pci_read_long(self.raw_dev, pos)

    def read_block(self, pos, length):
        backing = ffi.new("char[]", length)
        res = lib.pci_read_block(self.raw_dev, pos, backing, length)
        if res <= 0:
            return None
        return ffi.unpack(backing, length)

    def write_byte(self, pos, byte):
        return lib.pci_write_byte(self.raw_dev, pos, byte) > 0

    def write_word(self, pos, word):
        return lib.pci_write_word(self.raw_dev, pos, word) > 0

    def write_long(self, pos, long):
        return lib.pci_write_long(self.raw_dev, pos, long) > 0

    def write_block(self, pos, data):
        data = bytes(data)
        return lib.pci_write_block(self.raw_dev, pos, data, len(data)) > 0


def main():
    def parse_address(addr):
        pat = r"([0-9a-fA-F]{1,2}):([0-9a-fA-F]{1,2}).([0-9a-fA-F])\+([0-9a-fA-F]{1,4})"
        res = re.fullmatch(pat, addr)
        if res is None:
            raise ValueError("Couldn't parse %r as a PCI address" % (addr,))
        return tuple(map(lambda x: int(x, 16), res.group(1, 2, 3, 4)))

    def format_addr(bus, device, func, offset):
        return "%02x:%02x.%01x+%04x" % (bus, device, func, offset)

    def unpack(thing):
        m = {8: "Q", 4: "I", 2: "H", 1: "B"}
        if len(thing) not in m:
            raise ValueError("Can't process block of length %d" % (len(thing),))
        return struct.unpack("<" + m[len(thing)], thing)[0]

    def pack(thing, length):
        m = {8: "Q", 4: "I", 2: "H", 1: "B"}
        if length not in m:
            raise ValueError("Can't process block of length %d" % (length,))
        return struct.pack("<" + m[length], thing)

    def read(args):
        fmt = "%s : %0" + str(args.size * 2) + "x"
        with PCI(method=constants.PCI_ACCESS_I386_TYPE1) as p:
            for addr in args.address:
                dev = p.get_device(0, addr[0], addr[1], addr[2])
                print(fmt % (format_addr(*addr), unpack(dev.read_block(addr[3], args.size))))

    def write(args):
        fmtr = "%s : %0" + str(args.size * 2) + "x"
        fmtw = "%s = %0" + str(args.size * 2) + "x"
        with PCI(method=constants.PCI_ACCESS_I386_TYPE1) as p:
            s = format_addr(*args.address)
            dev = p.get_device(0, args.address[0], args.address[1], args.address[2])
            print(fmtr % (s, unpack(dev.read_block(args.address[3], args.size))))
            print(fmtw % (s, args.value))
            dev.write_block(args.address[3], pack(args.value, args.size))
            print(fmtr % (s, unpack(dev.read_block(args.address[3], args.size))))

    def rmw(args):
        f = "%0" + str(args.size * 2) + "x"
        fmtr = "%s : " + f
        fmtw = "%s = " + f + " = (" + f + " & " + f + ") | (" + f + " & ~" + f + ")"
        with PCI(method=constants.PCI_ACCESS_I386_TYPE1) as p:
            s = format_addr(*args.address)
            dev = p.get_device(0, args.address[0], args.address[1], args.address[2])
            prev = unpack(dev.read_block(args.address[3], args.size))
            print(fmtr % (s, prev))
            new_val = (prev & args.mask) | (args.update & ~args.mask)
            print(fmtw % (s, new_val, prev, args.mask, args.update, args.mask))
            dev.write_block(args.address[3], pack(new_val, args.size))
            print(fmtr % (s, unpack(dev.read_block(args.address[3], args.size))))

    parser = argparse.ArgumentParser(description="Read and write to PCI devices")
    subp = parser.add_subparsers()

    reader = subp.add_parser("read", help="Read from PCI spaces")
    reader.set_defaults(func=read)
    reader.add_argument("address", type=parse_address, nargs="+",
                        help="The address(es) from which to read, in format bb:dd:f+offset")

    writer = subp.add_parser("write", help="Write to physical memory")
    writer.set_defaults(func=write)
    writer.add_argument("address", type=parse_address,
                        help="The address to which the write should occur, " + \
                             "in format bb:dd:f+offset")
    writer.add_argument("value", type=lambda x: int(x, 16),
                        help="The value to write")

    rmwp = subp.add_parser("rmw", help="Perform a read-modify-write operation to a PCI device")
    rmwp.set_defaults(func=rmw)
    rmwp.add_argument("address", type=parse_address,
                     help="The address that should be read and modified, in format bb:dd:f+offset")
    rmwp.add_argument("mask", type=lambda x: int(x, 16),
                     help="The mask for the bits that should be preserved")
    rmwp.add_argument("update", type=lambda x: int(x, 16),
                     help="The new value that should be ORed into the read value")
    def add_sizes(p):
        meg = p.add_mutually_exclusive_group()
        meg.add_argument("--byte", dest="size", action="store_const", const=1,
                         help="Operate on bytes")
        meg.add_argument("--word", dest="size", action="store_const", const=2,
                         help="Operate on words (2 bytes)")
        meg.add_argument("--long", dest="size", action="store_const", const=4,
                         help="Operate on longs (4 bytes)")
        meg.add_argument("--qword", dest="size", action="store_const", const=8,
                         help="Operate on qwords (8 bytes)")
        p.set_defaults(size=4)

    add_sizes(reader)
    add_sizes(writer)
    add_sizes(rmwp)

    args = parser.parse_args()
    if "func" not in args:
        parser.error("must specify a mode")
    args.func(args)

if __name__ == "__main__":
    main()
