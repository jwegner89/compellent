#!/usr/bin/python3.6
# -*- coding: utf-8 -*-

"""
Update /etc/multipath.conf with new WWID aliases.
This script requires root privileges, so run as root or use sudo.
This script is intended to be run on the local host.
"""

import argparse
import fileinput
import os
import platform
import re
import shlex
import subprocess
import sys


def restart_multipath(verbose=False):
    """
    Restart the multipathd service

    :param bool verbose: toggle verbose messages
    """
    # determine whether under sysvinit or systemd
    release_full = platform.linux_distribution()
    #('Red Hat Enterprise Linux Server', '7.3', 'Maipo')
    release_short = release_full[1][0]
    #'7'

    # prepare service restart command before confirmation
    cmd = ''
    if release_short == '6':
        cmd = 'service multipathd reload'
    elif release_short == '7':
        cmd = 'systemctl reload multipathd.service'
    else:
        sys.exit('Error: unsupported release {}'.format(' '.join(release_full)))
    run = shlex.split(cmd)

    if verbose:
        print('Reloading multipath daemon.')
    subprocess.run(run)


def process_aliases(wwids, wwid_aliases, verbose=False):
    """
    Update WWID dictionary in-place with new wwid:alias pairs

    :param dict wwids: current wwid:alias mappings
    :param list wwid_aliases: list of strings with new mappings to apply, of the form 'wwid:alias'
    :param bool verbose: toggle verbose messages
    :raises CompellentException: if wwid_aliases are not of the correct form
    """
    # create regex for wwid:alias parameter groupings
    re_pair = re.compile(r'(?P<wwid>\w+):(?P<alias>\w+)')
    for pair in wwid_aliases:
        if re_pair.match(pair):
            wwid = re_pair.match(pair).group('wwid')
            new_alias = re_pair.match(pair).group('alias')

            # check if device associated to current alias is mounted
            if wwid in wwids.keys():
                current_alias = wwids[wwid]
                cmd = 'findmnt --noheadings --list --output target --source /dev/mapper/{}'.format(current_alias)
                run = shlex.split(cmd)
                mounted = ''
                try:
                    mounted = subprocess.run(run, stdout=subprocess.PIPE, encoding='utf-8').stdout
                except subprocess.SubprocessError:
                    # this is okay, since check_ouput raises an excecption for no
                    # output, but that is our desired state
                    pass
                # sample output
                #findmnt --noheadings --list --output target --source /dev/mapper/testvol1
                #/mnt/testvol1

                if len(mounted) > 0:
                    if verbose:
                        print('Refusing to change alias {} to {} because it is currently mounted!'.format(current_alias, new_alias))
                else:
                    wwids[wwid] = new_alias
        else:
            # argument did not match required format
            sys.exit("{} does not match the 'wwid:alias' format.".format(pair))


def update_config(filename, wwids):
    """
    Update multipath configuration file inplace with new wwid:alias pairs

    :param str filename: location of multipath configuration file to edit
    :param dict wwids: mappings of alias to wwid
    """
    # flag specifying current config block
    multipaths_block = False
    # flag in case multipath block is not present
    multipath_configured = False
    # keep track of tab and bracket levels
    tab_level = 0
    bracket_level = 0
    # set up regular expressions for different criteria
    re_comment = re.compile(r'^\s*#')
    re_blank = re.compile(r'^\s*$')
    re_multipaths = re.compile(r'^\s*multipaths')
    re_open = re.compile(r'^.*{')
    re_close = re.compile(r'^.*}')
    # process lines of config file in place
    for line in fileinput.input(filename, inplace=True):
        # interested in the following portion
        #multipaths {
        #        multipath {
        #                wwid    36000d31000d5f00000000000000000a5
        #                alias   testvol1
        #        }
        # ... other multipath blocks
        #}

        # need to keep track of opening and closing brackets
        if re_open.match(line):
            bracket_level += 1
        if re_close.match(line):
            bracket_level -= 1
            if multipaths_block and bracket_level == 0:
                multipaths_block = False

        if re_multipaths.match(line):
            multipaths_block = True
            multipath_configured = True
            # entering multipath alias config
            print(line, end='')
            tab_level += 1
            # start printing out wwid and alias configs
            for wwid, alias in wwids.items():
                print('{}multipath {{'.format('\t' * tab_level))
                tab_level += 1
                print('{}wwid\t{}'.format('\t' * tab_level, wwid))
                print('{}alias\t{}'.format('\t' * tab_level, alias))
                tab_level -= 1
                print('{}}}'.format('\t' * tab_level))
            tab_level -= 1
        elif multipaths_block:
            # old multipath config, do not write
            continue
        else:
            # print all other lines
            print(line, end='')

    # flag was never triggering, so we need to append the multipath
    # configuration to the end of the file
    if not multipath_configured and wwids:
        with open(filename, 'a', encoding='utf-8') as outfile:
            # start with blank line for spacing and open multipaths block
            outfile.write('\nmultipaths {\n')

            # print wwid and alias config
            for wwid, alias in wwids.items():
                outfile.write('\tmultipath {\n')
                outfile.write('\t\twwid\t{}\n'.format(wwid))
                outfile.write('\t\talias\t{}\n'.format(alias))
                outfile.write('\t}\n')

            # close multipaths block
            outfile.write('}\n')


def wwid_alias():
    """
    Build dictionary of wwid to alias mappings and return
    """
    # create dictionary mapping wwid to alias
    wwids = dict()

    # query multipath about volume
    cmd = 'multipath -ll'
    run = shlex.split(cmd)
    multipath = str()
    try:
        multipath = subprocess.run(run, stdout=subprocess.PIPE, encoding='utf-8').stdout
    except subprocess.SubprocessError:
        # no multipath config returned
        pass
    # sample output
    #testvol2 (36000d31000d5f00000000000000000a6) dm-3 COMPELNT,Compellent Vol
    #size=20G features='1 queue_if_no_path' hwhandler='0' wp=rw
    #`-+- policy='round-robin 0' prio=0 status=active
    #  |- 34:0:0:1 sdg 8:96  active ready running
    #  |- 39:0:0:1 sdi 8:128 active ready running
    #  |- 36:0:0:1 sdh 8:112 active ready running
    #  `- 40:0:0:1 sdj 8:144 active ready running
    # ... other multipath devices

    # create regex to match multipath disks
    re_multipath = re.compile(r'(?P<alias>\w+)\s+\((?P<wwid>\w+)\)\s+dm-\d+\s+COMPELNT,Compellent Vol')
    for line in multipath.splitlines():
        if re_multipath.match(line):
            wwid = re_multipath.match(line).group('wwid')
            alias = re_multipath.match(line).group('alias')
            wwids[wwid] = alias

    return wwids


def main():
    """
    Function which is executed when this program is run directly
    """
    if os.getuid() != 0:
        sys.exit('Insufficient privileges. Run this program as root.')

    parser = argparse.ArgumentParser(
        description="""
            Update wwids with new aliases.

            Specify wwid and alias as pairs separated by colons.
            For example, the following is a valid wwid:alias pair:
                '36000d31000d5f00000000000000000a5:testvol1'

            Note that this does not modify /etc/fstab, so that must be done
            separately if the new name should be mounted at boot.

            Also note that this is not idempotent; a successful run will always
            rewrite /etc/multipath.conf with the current running configuration for
            multipath aliases.
        """
    )
    parser.add_argument(
        'wwids',
        metavar='wwid:alias',
        type=str,
        nargs='+',
        help='WWID and alias pair to update',
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

    wwids = wwid_alias()
    process_aliases(wwids, args.wwids, args.verbose)

    if args.assume_yes:
        if args.verbose:
            print('Updating multipath configuration file.')
        update_config('/etc/multipath.conf', wwids)
        restart_multipath(args.verbose)
    else:
        confirm = input('Are you sure you want to change these aliases? (y/N) ')
        if confirm.lower() == 'y':
            if args.verbose:
                print('Updating multipath configuration file.')
            update_config('/etc/multipath.conf', wwids)
            restart_multipath(args.verbose)


if __name__ == '__main__':
    # only run when program is run as a script
    main()


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
