"""
---------------------------------- WARNING! ----------------------------------

This tool is EXTREMELY DANGEROUS! If you don't know EXACTLY what you are
doing, DO NOT RUN THIS PROGRAM. It can EASILY BRICK YOUR SYSTEM and possibly
PERMANENTLY PHYSICALLY DAMAGE IT AND ITS PERIPHERALS.

------------------------------------------------------------------------------

Attempt to map a PCR region.

This tool iterates over a PCR port and, for each register, does the following:
  * Reads out the original value ("pre_value")
  * Sets the register to 00000000
  * Reads out the new value ("zero_phase")
  * Sets the register to ffffffff
  * Reads out the new value ("one_phase")
  * Sets the register back to "pre_value"
  * Reads out the new value ("reset_phase")

A map of the resulting values is returned.
"""
import sys
import enum
import logging
import argparse
import progressbar
progressbar.streams.wrap_stderr()
from collections import namedtuple
from .pcr import PCR, Register, PORT_SIZE, REGISTER_SIZE


l = logging.getLogger(__name__)

class RegisterTester:
    class BitClassification(enum.Enum):
        READ_WRITE    = "RW"
        CONSTANT_ZERO = "0"
        CONSTANT_ONE  = "1"
        LOCK_ON_ZERO  = "L0"
        LOCK_ON_ONE   = "L1"
        NOT_TESTED    = "NT"
        UNKNOWN       = "UK"

    PhaseRecord = namedtuple("PhaseRecord", ("attempted_write", "result"))
    def __init__(self, reg):
        self.reg = reg
        self.relevance_mask = self.reg.get_relevance_mask()
        self.pre_value = None
        self.zero_phase = None
        self.one_phase = None
        self.reset_phase = None
        self._record()

    def _record(self):
        # "Pre" phase
        pre_read = self.reg.read()
        # "Zero" phase
        zero_write = self.reg.write(0x00000000)
        zero_read = self.reg.read()
        # "One" phase
        one_write = self.reg.write(0xffffffff)
        one_read = self.reg.read()
        # "Reset" phase
        reset_write = self.reg.write(pre_read)
        reset_read = self.reg.read()

        # Cleanup
        self.pre_value = pre_read
        self.zero_phase = self.PhaseRecord(zero_write, zero_read)
        self.one_phase = self.PhaseRecord(one_write, one_read)
        self.reset_phase = self.PhaseRecord(reset_write, reset_read)

    @property
    def appears_implemented(self):
        values = (self.pre_value, self.zero_phase.result,
                  self.one_phase.result, self.reset_phase.result)

        return not all(v == 0xffffffff for v in values)

    def classify_bit(self, bit_index):
        def get_bit(field):
            return (field & (1 << bit_index)) >> bit_index

        if get_bit(self.relevance_mask) == 0:
            return self.BitClassification.NOT_TESTED

        pb = get_bit(self.pre_value)
        zb = get_bit(self.zero_phase.result)
        ob = get_bit(self.one_phase.result)
        rb = get_bit(self.reset_phase.result)

        if zb == 0 and ob == 1 and rb == pb:
            return self.BitClassification.READ_WRITE

        if pb == 0 and zb == 0 and ob == 0 and rb == 0:
            return self.BitClassification.CONSTANT_ZERO

        if pb == 1 and zb == 1 and ob == 1 and rb == 1:
            return self.BitClassification.CONSTANT_ONE

        if pb == 1 and zb == 0 and ob == 0 and rb == 0:
            return self.BitClassification.LOCK_ON_ZERO

        if pb == 0 and zb == 0 and ob == 1 and rb == 1:
            return self.BitClassification.LOCK_ON_ONE

        return self.BitClassification.UNKNOWN

    def classify_bits(self):
        return [self.classify_bit(i) for i in range(REGISTER_SIZE * 8)]

    def pretty(self):
        header = "Port %02x at +%04x; original: %08x" \
                 % (self.reg.port, self.reg.offset, self.pre_value)
        bits = self.classify_bits()
        fancy_bits = []
        for i, b in reversed(list(enumerate(bits))):
            fancy_bits.append(("%02d" % (i,), "%s" % (b.value,)))
        def section(s):
            return "| " + s.ljust(2) + " "
        lines = ["".join(section(s) for s in l) + "|\n" for l in zip(*fancy_bits)]
        splitter = "-" * (len(lines[0]) - 1) + "\n"
        padded_header = "|" + header.center(len(lines[0]) - 3) + "|" + "\n"
        return splitter + padded_header + splitter + lines[0] + lines[1] + splitter

def map_pcr_port(pcr, port, always_one=None, always_zero=None, no_modify=None):
    if always_one is None:
        always_one = {}
    if always_zero is None:
        always_zero = {}
    if no_modify is None:
        no_modify = {}
    records = {}
    l.info("Mapping PCR port %x", port)
    for off in progressbar.progressbar(range(0, PORT_SIZE, REGISTER_SIZE)):
        reg = Register(pcr, port, off,
                       always_one=always_one.get(off, 0),
                       always_zero=always_zero.get(off, 0),
                       no_modify=no_modify.get(off, 0))
        records[off] = RegisterTester(reg)
    return records

def main():
    logging.basicConfig()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("port", type=lambda x: int(x, 16),
                        help="The PCR port to map.")
    parser.add_argument("outfile", type=argparse.FileType("w"), default=sys.stdout,
                        nargs="?",
                        help="Output file for the map.")
    parser.add_argument("--base", type=lambda x: int(x, 16), default=0xfd000000,
                        help="Base address of PCR region.")

    args = parser.parse_args()

    with PCR(args.base) as p:
        res = map_pcr_port(p, args.port)
        filtered = [reg.pretty() for reg in res.values() if reg.appears_implemented]
        args.outfile.write("\n".join(filtered) + "\n")

if __name__ == "__main__":
    main()
