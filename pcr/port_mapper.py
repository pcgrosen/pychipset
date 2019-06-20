"""
----------------------------------- WARNING! -----------------------------------

This tool is EXTREMELY DANGEROUS! If you don't know EXACTLY what you are doing,
DO NOT RUN THIS PROGRAM. It can EASILY BRICK YOUR SYSTEM and possibly
PERMANENTLY PHYSICALLY DAMAGE IT AND ITS PERIPHERALS.

--------------------------------------------------------------------------------

Attempt to map a PCR region.

This tool iterates over a PCR port and, for each register, does the following:
  * Reads out the original value ("pre")
  * Sets the register to 00000000
  * Reads out the new value ("after_zeros")
  * Sets the register to ffffffff
  * Reads out the new value ("after_ones")
  * Sets the register back to "pre"
  * Reads out the new value ("post")

A map of the resulting values is returned.
"""
import sys
import logging
import argparse
import progressbar
progressbar.streams.wrap_stderr()
from collections import namedtuple
from . import PCR
from .pcr import PORT_SIZE, REGISTER_SIZE


l = logging.getLogger(__name__)

Register = namedtuple("Register", ("pre", "after_zeros", "after_ones", "post"))

def map_pcr_port(p, port):
    registers = {}
    l.info("Mapping PCR port %x", port)
    for off in progressbar.progressbar(range(0, PORT_SIZE, REGISTER_SIZE)):
        pre = p.read_register(port, off)
        p.write_register(port, off, 0)
        after_zeros = p.read_register(port, off)
        p.write_register(port, off, 0xffffffff)
        after_ones = p.read_register(port, off)
        p.write_register(port, off, pre)
        post = p.read_register(port, off)
        registers[off] = Register(pre, after_zeros, after_ones, post)
    return registers

def main():
    logging.basicConfig()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=lambda x: int(x, 16),
                        help="The PCR port to map.")
    parser.add_argument("outfile", type=argparse.FileType("w"), default=sys.stdout,
                        nargs="?",
                        help="Output file for the map.")
    parser.add_argument("--base", type=lambda x: int(x, 16), default=0xfd000000,
                        help="Base address of PCR region.")

    args = parser.parse_args()

    with PCR(args.base) as p:
        map_pcr_port(p, args.port)

if __name__ == "__main__":
    main()
