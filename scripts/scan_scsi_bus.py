#!/usr/bin/python3.6
# -*- coding: utf-8 -*-

"""
Scans all SCSI hosts to detect new SCSI devices.
This script requires root privileges, so run it as root or use sudo.
This script is intened to be run on the local host.
"""

import argparse
import os
import sys


def scan_hosts(verbose=False):
    """
    Scan the SCSI bus on the local machine

    :param bool verbose: enable verbosity
    """
    # list SCSI hosts available to scan
    scsi_hosts = os.listdir('/sys/class/scsi_host')
    for host in scsi_hosts:
        if verbose:
            print('Scanning {}...'.format(host))
        with open('/sys/class/scsi_host/{}/scan'.format(host), 'w') as outfile:
            outfile.write('- - -\n')


def main():
    """
    Function which is executed when this program is run directly
    """
    parser = argparse.ArgumentParser(
        description='Scan all SCSI hosts to detect new SCSI devices.',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Be verbose and print status messages',
    )
    args = parser.parse_args()

    if os.getuid() != 0:
        sys.exit('Insufficient privileges. Run this program as root.')

    scan_hosts(args.verbose)


if __name__ == '__main__':
    # only run when program is run as a script
    main()


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
