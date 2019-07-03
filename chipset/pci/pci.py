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
