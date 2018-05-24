# -*- coding: utf-8 -*-

"""
Manage volumes and servers using the Dell Storage Manager REST API.
"""

import argparse
import configparser
import datetime
import getpass
import json
import keyring
import os
import paramiko
import requests
import shlex
import socket
import string
import subprocess
import sys
#from .connection import DSMConnection, SSHConnection
#from .connection import DSMConnection
from .exceptions import CompellentException

# command line parser options applicable to all subcommands
parser = argparse.ArgumentParser(
    prog='compellent',
    description='Manage Dell Compellent storage and servers',
)
parser.add_argument(
    '-c',
    '--config_file',
    type=str,
    default=os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../config.ini')),
    help='path to configuration file in INI format',
)
parser.add_argument(
    '-C',
    '--config_section',
    type=str,
    default='DEFAULT',
    help='specific section of INI config to use',
)
parser.add_argument(
    '-p',
    '--password',
    action='store_true',
    help='prompt for password',
)
parser.add_argument(
    '-i',
    '--insecure',
    action='store_true',
    help='skip TLS certificate and SSH host key checking',
)
subparsers = parser.add_subparsers(
    dest='subparser',
    help='Subcommands available from the Compellent CLI module',
)

# list subcommands
parser_list = subparsers.add_parser(
    'list',
    help='query Compellent objects',
)
parser_list.add_argument(
    'object',
    choices=[
        'server',
        'volume',
    ],
    help='type of object to list',
)
parser_list.add_argument(
    'pattern',
    help="""
    Simple pattern to match against\n
    For example, a server object with pattern 'psdb' would include matches for\n
        psdbprd16a.is.depaul.edu\n
        psdbdev26a.is.depaul.edu\n
        ...\n
    Note that this only shows servers which are attached to the Compellent.\n
    \n
    A volume object pattern 'pdsb' would include matches for\n
        psdbprd16a-u05\n
        psdbdev16a-CSDEV90-data01\n
        ...\n
    \n
    Regular expression syntax is currently not supported, so '*', etc are\n
    taken to be literal characters.\n
    """,
)

# snapshot subcommands
parser_snapshot = subparsers.add_parser(
    'snapshot',
    help='snapshot operations',
)
parser_snapshot.add_argument(
    'volume',
    type=str,
    help='name of volume to snapshot',
)
parser_snapshot.add_argument(
    '-e',
    '--expiration',
    type=str,
    default='7d',
    help="""
    How long until the snapshot will expire, in minutes.\n
    Use 0 to designate that the snapshot should not expire.\n
    \n
    Multiplier values are allowed, e.g.\n
        h = hours = 60 minutes\n
        d = days = 24 hours\n
        w = weeks = 7 days\n
        m = months = 30 days\n
        y = years = 365 days\n
    \n
    For example, 3d = 3 days and  5m = 5 months.\n
    Default is set for 7 days.\n
    """,
)

# refresh subcommands
parser_refresh = subparsers.add_parser(
    'refresh',
    help="""
    Create a view volume of 'source_mount' mounted on 'source' and map\n
    it to 'destination' mounted at 'dest_mount'.\n
    This is mostly intended for Oracle workloads that are refreshing a\n
    test database from production, and as a result it is very opinionated.\n
    As a brief overview, this command will:\n
        1. Determine the corresponding volume that is mounted at 'source_mount'\n
           on the 'source' server.\n
        2. Create a clone of 'source_mount' and expose the volume to 'destination'.\n
        3. Remove anything mounted at 'dest_mount' on 'destination'.\n
        4. Delete any disks/multipath devices associated with the previous\n
           volume mounted at 'dest_mount', if applicable.\n
        5. Mount the newly created view volume on 'destination', modifying\n
           /etc/fstab so that the mountpoint will be persistent.\n
    This option can be potentially dangerous, so use caution.\n
    """,
)
parser_refresh.add_argument(
    'source',
    type=str,
    help='server from which to clone volume',
)
parser_refresh.add_argument(
    'source_mount',
    type=str,
    help='mountpoint of volume on source',
)
parser_refresh.add_argument(
    'destination',
    type=str,
    help='target server to mount cloned volume',
)
parser_refresh.add_argument(
    'dest_mount',
    type=str,
    help='mountpoint of cloned volume on destination',
)
parser_refresh.add_argument(
    'environment',
    type=str,
    help='target environment, e.g. tst, dev, etc.',
)
parser_refresh.add_argument(
    '-y',
    '--assume_yes',
    action='store_true',
    help='Do not prompt for confirmation. Potentially dangerous!',
)

args = parser.parse_args()

if not os.path.isfile(args.config_file):
    sys.exit('Config file {} does not exist.'.format(args.config_file))

# read configuration from INI file
config = configparser.ConfigParser()
with open(args.config_file, 'r') as config_file:
    config.read_string(config_file.read())

if args.config_section != 'DEFAULT' and args.config_section not in config.sections():
    sys.exit(
        'Config file {} does not contain section {}.'.format(
            args.config_file,
            args.config_section,
        )
    )

cfg = config[args.config_section]

# get or set DSM password
dsm_keyring = 'dsm_{}'.format(cfg['dsm_host'])
dsm_pwd = keyring.get_password(dsm_keyring, cfg['dsm_user'])
if args.password or not dsm_pwd:
    keyring.set_password(
        dsm_keyring,
        cfg['dsm_user'],
        getpass.getpass(
            prompt='Enter Dell Storage Manager password for {}@{}'.format(
                cfg['dsm_user'],
                cfg['dsm_host'],
            )
        ),
    )
    dsm_pwd = keyring.get_password(dsm_keyring, cfg['dsm_user'])

# execute pre-task commands from config file
if 'pre_command' in cfg:
    pre_cmd = cfg['pre_command']
    pre_run = shlex.split(pre_cmd)
    pre_result = subprocess.run(
        pre_run,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8',
    )
    print(pre_result.stdout)

#with DSMConnection as dsm:
#    dsm.host = cfg['dsm_host']
#    dsm.port = cfg['dsm_port']
#    dsm.user = cfg['dsm_user']
#    dsm.password = dsm_pwd
#    dsm.api_version = cfg['api_version']
#    dsm.verify = not args.insecure
#    dsm.timeout = cfg['timeout']
#
#    dsm.connect()

if args.subparser == 'list':
    print('In list subparser')
elif args.subparser == 'snapshot':
    print('In snapshot subparser')
elif args.subparser == 'refresh':
    print('In refresh subparser')
    #with SSHConnection, SSHConnection as source_ssh, dest_ssh:
else:
    sys.exit('Invalid subparser: {}'.format(args.subparser))

# execute pre-task commands from config file
if 'post_command' in cfg:
    post_cmd = cfg['post_command']
    post_run = shlex.split(post_cmd)
    post_result = subprocess.run(
        post_run,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8',
    )
    print(post_result.stdout)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
