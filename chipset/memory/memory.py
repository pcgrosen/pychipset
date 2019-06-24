import os
import struct
import argparse


class Memory:
    STRUCT_SIZES = {8: "Q", 4: "I", 2: "H", 1: "B"}
    def __init__(self):
        self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, ex_t, ex_v, ex_tb):
        self.close()
        return False

    def read(self, address, length):
        os.lseek(self.fd, address, os.SEEK_SET)
        return os.read(self.fd, length)

    def read_unsigned(self, address, size):
        if size not in self.STRUCT_SIZES:
            raise ValueError("size %d not supported" % (size,))
        content = self.read(address, size)
        return struct.unpack("<" + self.STRUCT_SIZES[size], content)[0]

    def read_qword(self, address):
        return self.read_unsigned(address, 8)

    def read_dword(self, address):
        return self.read_unsigned(address, 4)

    def read_word(self, address):
        return self.read_unsigned(address, 2)

    def read_byte(self, address):
        return self.read_unsigned(address, 1)

    def write(self, address, content):
        os.lseek(self.fd, address, os.SEEK_SET)
        os.write(self.fd, content)

    def write_unsigned(self, address, value, size):
        if size not in self.STRUCT_SIZES:
            raise ValueError("size %d not supported" % (size,))
        self.write(address, struct.pack("<" + self.STRUCT_SIZES[size], value))

    def write_qword(self, address, value):
        return self.write_unsigned(address, value, 8)

    def write_dword(self, address, value):
        return self.write_unsigned(address, value, 4)

    def write_word(self, address, value):
        return self.write_unsigned(address, value, 2)

    def write_byte(self, address, value):
        return self.write_unsigned(address, value, 1)


def main():
    def read(args):
        fmt = "%08x : %0" + str(args.size * 2) + "x"
        with Memory() as mem:
            for addr in args.address:
                print(fmt % (addr, mem.read_unsigned(addr, args.size)))

    def write(args):
        fmtr = "%08x : %0" + str(args.size * 2) + "x"
        fmtw = "%08x = %0" + str(args.size * 2) + "x"
        with Memory() as mem:
            print(fmtr % (args.address, mem.read_unsigned(args.address, args.size)))
            print(fmtw % (args.address, args.value))
            mem.write_unsigned(args.address, args.value, args.size)
            print(fmtr % (args.address, mem.read_unsigned(args.address, args.size)))

    def rmw(args):
        f = "%0" + str(args.size * 2) + "x"
        fmtr = "%08x : " + f
        fmtw = "%08x = " + f + " = (" + f + " & " + f + ") | (" + f + " & ~" + f + ")"
        with Memory() as mem:
            prev = mem.read_unsigned(args.address, args.size)
            print(fmtr % (args.address, prev))
            new_val = (prev & args.mask) | (args.update & ~args.mask)
            print(fmtw % (args.address, new_val, prev, args.mask, args.update, args.mask))
            mem.write_unsigned(args.address, new_val, args.size)
            print(fmtr % (args.address, mem.read_unsigned(args.address, args.size)))

    parser = argparse.ArgumentParser(description="Read and write to physical memory via /dev/mem")
    subp = parser.add_subparsers()

    reader = subp.add_parser("read", help="Read from physical memory")
    reader.set_defaults(func=read)
    reader.add_argument("address", type=lambda x: int(x, 16), nargs="+",
                        help="The address(es) from which to read")

    writer = subp.add_parser("write", help="Write to physical memory")
    writer.set_defaults(func=write)
    writer.add_argument("address", type=lambda x: int(x, 16),
                        help="The address to which the write should occur")
    writer.add_argument("value", type=lambda x: int(x, 16),
                        help="The value to write")

    rmwp = subp.add_parser("rmw", help="Perform a read-modify-write operation to physical memory")
    rmwp.set_defaults(func=rmw)
    rmwp.add_argument("address", type=lambda x: int(x, 16),
                     help="The address that should be read and modified")
    rmwp.add_argument("mask", type=lambda x: int(x, 16),
                     help="The mask for the bits that should be preserved")
    rmwp.add_argument("update", type=lambda x: int(x, 16),
                     help="The new value that should be ORed into the read value")
    def add_sizes(p):
        meg = p.add_mutually_exclusive_group()
        meg.add_argument("--byte", dest="size", action="store_const", const=1,
                         help="Operate on bytes")
        meg.add_argument("--word", dest="size", action="store_const", const=2,
                         help="Operate on words")
        meg.add_argument("--dword", dest="size", action="store_const", const=4,
                         help="Operate on dwords")
        meg.add_argument("--qword", dest="size", action="store_const", const=8,
                         help="Operate on qwords")
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
