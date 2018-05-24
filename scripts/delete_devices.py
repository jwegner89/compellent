#!/usr/bin/python3.6
# -*- coding: utf-8 -*-

"""
Remove all block or multipath devices specified as arguments
This script will refuse to delete any mounted filesystem or any block device
in an LVM configuration.
This script requires root privileges, so run it as root or use sudo.
This script is intended to be run on the local host.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
import textwrap


def disk_associations():
    """
    Return a dictionary of all block devices mapped to their associated volumes.
    This has a 'protected' key which is associated with all block devices that
    are currently 1) mounted; or 2) in an LVM configuration.
    """
    # create dictionary mapping device name to set of disks
    disk_mappings = dict()
    # create regex to match multipath disks
    re_multipath = re.compile(r'\s+[|`]-\s+\d+:\d+:\d+:\d+\s+(?P<disk>\w+)\s+\d+:\d+')

    # check that specified volume is mounted on this host
    cmd = 'multipath -l -v 1'
    run = shlex.split(cmd)
    multipath_devices = str()
    try:
        multipath_devices = subprocess.run(
            run,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        ).stdout
    except subprocess.SubprocessError:
        # no multipath aliases returned
        pass
    # sample output
    #testvol1
    #testvol2

    for device in multipath_devices.splitlines():
        device = device.strip()
        disk_mappings[device] = set()
        # query multipath about volume
        cmd = 'multipath -ll {}'.format(device)
        run = shlex.split(cmd)
        multipath_info = str()
        try:
            multipath_info = subprocess.run(
                run,
                stdout=subprocess.PIPE,
                encoding='utf-8',
            ).stdout
        except subprocess.SubprocessError:
            # no multipath info returned
            pass
        # sample output
        #testvol2 (36000d31000d5f00000000000000000a6) dm-3 COMPELNT,Compellent Vol
        #size=20G features='1 queue_if_no_path' hwhandler='0' wp=rw
        #`-+- policy='round-robin 0' prio=0 status=active
        #  |- 34:0:0:1 sdg 8:96  active ready running
        #  |- 39:0:0:1 sdi 8:128 active ready running
        #  |- 36:0:0:1 sdh 8:112 active ready running
        #  `- 40:0:0:1 sdj 8:144 active ready running

        for line in multipath_info.splitlines():
            if re_multipath.match(line):
                disk_mappings[device].add(re_multipath.match(line).group('disk'))

    # 'protected' mapping for all block devices that should not be deleted
    disk_mappings['protected'] = set()

    # retrieve all mounted filesystems
    cmd = 'findmnt --noheadings --list --type ext2,ext3,ext4,xfs --output SOURCE'
    run = shlex.split(cmd)
    mounted_devices = str()
    try:
        mounted_devices = subprocess.run(
            run,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        ).stdout
    except subprocess.SubprocessError:
        # no mounted disks returned
        pass
    # sample output
    #/dev/mapper/vgROOT-lvROOT
    #/dev/sda2
    #/dev/mapper/testvol2
    #/dev/mapper/testvol1

    # create regex to match devices
    re_mounted = re.compile(r'(/dev/(?!mapper)(?P<disk>[a-zA-Z]+)\d*)|(/dev/mapper/(?P<alias>\w+))')
    for device in mounted_devices.splitlines():
        device = device.strip()
        if re_mounted.match(device):
            disk_match = re_mounted.match(device).group('disk')
            alias_match = re_mounted.match(device).group('alias')
            if disk_match:
                disk_mappings['protected'].add(disk_match)
            elif alias_match:
                disk_mappings['protected'].add(alias_match)
                # add disks for multipath device if applicable
                if alias_match in disk_mappings:
                    disk_mappings['protected'] |= disk_mappings[alias_match]

    # look at all LVM physical volumes
    cmd = 'pvs --noheadings --options pv_name'
    run = shlex.split(cmd)
    lvm_disks = str()
    try:
        lvm_disks = subprocess.run(
            run,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        ).stdout
    except subprocess.SubprocessError:
        # no lvm disks returned
        pass
    # sample output
    #  /dev/sda3
    #  /dev/sdb1

    # create regex capturing disk associations with volume groups
    re_lvm = re.compile(r'/dev/(?P<disk>[a-zA-Z]+)\d*')
    for disk in lvm_disks.splitlines():
        disk = disk.strip()
        if re_lvm.match(disk):
            disk_mappings['protected'].add(re_lvm.match(disk).group('disk'))

    return(disk_mappings)


def delete_devices(disks, aliases, assume_yes=False, verbose=False):
    """
    Delete specified block devices from local system

    :param set disks: basic block devices for deletion
    :param set aliases: multipath device aliases to delete
    :param bool assume_yes: toggle checking for confirmation
    :param bool verbose: toggle verbose messages
    """
    # retrieve list of volumes and associated disks
    device_groups = disk_associations()

    # retrieve protected disks
    protected_devices = device_groups.pop('protected')

    # make sure that if a selected disk is part of a multipath device
    # that all other disks are cleaned along with the multipath device
    for disk in list(disks):
        for group in device_groups:
            group_disks = device_groups[group]
            if disk in group_disks:
                if verbose:
                    print('Disk {disk} is a part of the multipath device {alias}. Adding the other disks from {alias}.'.format(alias=group, disk=disk))
                aliases.add(group)
                disks |= group_disks

    # check that none of the provided disks are system volume or currently mounted
    selected_protected_devices = (protected_devices & disks) | (protected_devices & aliases)
    if selected_protected_devices:
        if verbose:
            refusal_message = 'Refusing to delete the following protected devices: {}'.format(' '.join(selected_protected_devices))
            print(refusal_message)
        # remove system disks from disks to process
        aliases -= protected_devices
        disks -= protected_devices

    for alias in aliases:
        disks |= device_groups[alias]

    if assume_yes:
        if verbose:
            print('Flushing the following multipath devices: {}'.format(' '.join(aliases)))
        for alias in aliases:
            cmd = 'multipath -f {}'.format(alias)
            run = shlex.split(cmd)
            exit_code = subprocess.run(run).returncode
            if exit_code != 0:
                print('Error: cannot flush multipath device {}'.format(alias))
        if verbose:
            print('Deleting the following disks: {}'.format(' '.join(disks)))
        for disk in disks:
            with open('/sys/block/{}/device/state'.format(disk), 'w') as outfile:
                outfile.write('offline\n')
            with open('/sys/block/{}/device/delete'.format(disk), 'w') as outfile:
                outfile.write('1\n')

    elif aliases or disks:
        warning_message = 'You have selected the following devices for removal:'
        if aliases:
            warning_message += '\n\tAliases: ' + ' '.join(aliases)
        if disks:
            warning_message += '\n\tDisks: ' + ' '.join(disks)
        warning_message += '\nAre you sure you want to delete these devices? (y/N) '
        response = raw_input(warning_message)
        if response.lower() == 'y':
            if verbose:
                print('Flushing the following multipath devices: {}'.format(' '.join(aliases)))
            for alias in aliases:
                cmd = 'multipath -f {}'.format(alias)
                run = shlex.split(cmd)
                exit_code = subprocess.run(run).returncode
                if exit_code != 0:
                    print('Error: cannot flush multipath device {}'.format(alias))
            if verbose:
                print('Deleting the following disks: {}'.format(' '.join(disks)))
            for disk in disks:
                with open('/sys/block/{}/device/state'.format(disk), 'w') as outfile:
                    outfile.write('offline\n')
                with open('/sys/block/{}/device/delete'.format(disk), 'w') as outfile:
                    outfile.write('1\n')


def main():
    """
    Function which is executed when this program is run directly
    """
    if os.getuid() != 0:
        sys.exit('Insufficient privileges. Run this program as root.')

    parser = argparse.ArgumentParser(
        description="""
            Delete disks specified as arguments. Both standard block devices and
            multipath device aliases are accepted as parameters.

            Be very careful, as this can destroy data if the wrong device is specified!
            There are protections in place to prevent the deletion of currently mounted
            filesystems, but still use caution.
        """
    )
    parser.add_argument(
        '-s',
        '--standard',
        metavar='sdX',
        type=str,
        nargs='+',
        help='standard block devices to remove',
    )
    parser.add_argument(
        '-m',
        '--multipath',
        metavar='alias',
        type=str,
        nargs='+',
        help='multipath devices to remove',
    )
    parser.add_argument(
        '-y',
        '--assume_yes',
        action='store_true',
        help='Do not prompt for confirmation and assume yes',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Be verbose and print status messages',
    )
    args = parser.parse_args()

    disks = set()
    aliases = set()
    # valid devices to accept as parameters
    block_devices = os.listdir('/sys/block')
    # only include SCSI devices, not floppy, cdrom, or device mapper devices
    valid_disks = set()
    for disk in block_devices:
        if disk[:2] == 'sd':
            valid_disks.add(disk)
    # setup command to build set of multipath devices
    cmd = 'multipath -l -v 1'
    run = shlex.split(cmd)
    multipath_devices = str()
    try:
        multipath_devices = subprocess.run(
            run,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        ).stdout
    except subprocess.SubprocessError:
        # no multipath aliases returned
        pass
    valid_multipaths = multipath_devices.split()

    if args.standard:
        for disk in args.standard:
            if disk in valid_disks:
                disks.add(disk)
            else:
                sys.exit(
                    textwrap.dedent(
                        """\
                        Invalid block device: {}
                        Choose from the following devices: {}\
                        """.format(
                            disk, 
                            ' '.join(valid_disks),
                        )
                    )
                )

    if args.multipath:
        for alias in args.multipath:
            if alias in valid_multipaths:
                aliases.add(alias)
            else:
                sys.exit(
                    textwrap.dedent(
                        """\
                        Invalid multipath alias: {}
                        Choose from the following aliases: {}\
                        """.format(
                            alias,
                            ' '.join(multipath_devices.splitlines()),
                        )
                    )
                )

    # ensure at least one alias or disk selected
    if not disks and not aliases:
        sys.exit('Select at least one disk or alias.')

    delete_devices(disks, aliases, args.assume_yes, args.verbose)


if __name__ == '__main__':
    # only run when program is run as a script
    main()


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
