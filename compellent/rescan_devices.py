#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Rescans all SCSI hosts to detect new SCSI devices and geometries.
This script requires root privileges, so run it as root or use sudo.
This script is intened to be run on the local host.
"""

from __future__ import print_function
import os
import sys
import textwrap


def rescan_devices(verbose=False):
    """
    Rescan the SCSI bus on the local machine

    :param bool verbose: enable verbosity
    """
    # list SCSI hosts available to scan
    scsi_hosts = os.listdir('/sys/class/scsi_host')
    for host in scsi_hosts:
        if verbose:
            print('Scanning {}...'.format(host))
        with open('/sys/class/scsi_host/{}/scan'.format(host), 'w') as outfile:
            outfile.write('- - -\n')


def print_usage():
    """
    Simple function to print usage details
    """
    print(textwrap.dedent("""\
        usage: rescan_devices.py [-h] [-v]

        Rescan all SCSI hosts to detect new SCSI devices and geometries.

        optional arguments:
          -h, --help        show this help message and exit
          -v, --verbose     Be verbose and print status messages\
        """)
    )


def main():
    """
    Function which is executed when this program is run directly
    """
    # flag for verbosity
    verbose = False
    # iterate through args since argparse not available for Python 2.6
    for arg in sys.argv[1:]:
        if arg in ['-h', '--help']:
            print_usage()
            sys.exit()
        elif arg in ['-v', '--verbose']:
            verbose = True
        else:
            print('Error: unrecognized argument {}'.format(arg))
            print_usage()
            sys.exit(1)

    if os.getuid() != 0:
        sys.exit('Insufficient privileges. Run this program as root.')

    rescan_devices(verbose)


if __name__ == '__main__':
    # only run when program is run as a script
    main()


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
