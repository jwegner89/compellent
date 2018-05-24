#!/usr/bin/python3.6
# -*- coding: utf-8 -*-

"""
Rescans all block devices and resizes the underlying multipath devices.
This script requires root privileges, so run it as root or use sudo.
This script is intened to be run on the local host.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys


def resize_disks(verbose=False):
    """
    Check all SCSI devices for updated size

    :param bool verbose: enable verbosity
    """
    # list SCSI hosts available to scan
    block_devices = os.listdir('/sys/class/block')
    # make regex to make only standard block devices
    re_block = re.compile(r'^sd[a-zA-Z]$')
    for device in block_devices:
        if re_block.match(device):
            if verbose:
                print('Rescanning {}...'.format(device))
            with open('/sys/class/block/{}/device/rescan'.format(device), 'w') as outfile:
                outfile.write('1\n')


def multipath(verbose=False):
    cmd = 'multipath -l -v 1'
    run = shlex.split(cmd)
    devices = subprocess.run(
        run,
        stdout=subprocess.PIPE,
        encoding='utf-8',
    ).stdout.splitlines()
    for device in devices:
        if verbose:
            print('Resizing multipath device {}'.format(device))
        cmd = 'multipathd resize map {}'.format(device)
        run = shlex.split(cmd)
        subprocess.run(
            run,
            stdout=subprocess.DEVNULL,
        )


def main():
    """
    Function which is executed when this program is run directly
    """
    parser = argparse.ArgumentParser(
        description='Rescan all block devices for size changes',
    )
    parser.add_argument(
        '-m',
        '--multipath',
        action='store_true',
        help='Notify multipathd to resize its devices',
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

    resize_disks(args.verbose)

    # notify multipath of resize if argument given
    if args.multipath:
        multipath(args.verbose)


if __name__ == '__main__':
    # only run when program is run as a script
    main()


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
