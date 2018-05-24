# -*- coding: utf-8 -*-

"""
Script to snapshot a specific Compellent volume using the Dell Compellent
Storage Manager REST API.
"""

import argparse
import datetime
import getpass
import json
import keyring
import paramiko
import requests
import socket
import string
import sys
from .exceptions import CompellentException


def main():
    # parser options applicable to all subcommands
    parser = argparse.ArgumentParser(
        description='Manage Dell Compellent storage and servers',
    )
    parser.add_argument(
        '-d',
        '--dsm_user',
        type=str,
        help='Dell Storage Manager username',
    )
    parser.add_argument(
        '-D',
        '--dsm_password',
        action='store_true',
        help='change cached Dell Storage Manager password in keyring',
    )
    parser.add_argument(
        '-m',
        '--dsm_host',
        type=str,
        help='hostname of the Dell Storage Manager server',
    )
    parser.add_argument(
        '-M',
        '--dsm_port',
        type=int,
        default=3033,
        help='Dell Storage Manager Data Collector port',
    )
    parser.add_argument(
        '-a',
        '--api_version',
        type=str,
        default='3.4',
        help='version of Dell Storage Manager API to use',
    )
    parser.add_argument(
        '-t',
        '--timeout',
        type=int,
        default=None,
        help='optional timeout for Dell Storage Manager API calls',
    )
    parser.add_argument(
        '-l',
        '--linux_user',
        type=str,
        default='root',
        help='Linux host username',
    )
    parser.add_argument(
        '-L',
        '--linux_password',
        action='store_true',
        help='change cached Linux password in keyring',
    )
    parser.add_argument(
        '-s',
        '--linux_host',
        type=str,
        help='hostname of the remote Linux server',
    )
    parser.add_argument(
        '-S',
        '--linux_port',
        type=int,
        default=22,
        help='port used to connect to the remote Linux server',
    )
    parser.add_argument(
        '-i',
        '--insecure',
        action='store_true',
        help='skip TLS certificate and SSH host key checking',
    )
    parser.add_argument(
        'datacenter',
        type=str,
        help='datacenter hosting the server or volume',
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
        Note that this only shows servers which are attached to the Compellent.\n
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

    # clone subcommands
    parser_clone = subparsers.add_parser(
        'clone',
        help="""
        Create a view volume of 'volume' and map it to 'server' mounted at 'mountpoint'.\n
        This is mostly intended for Oracle workloads that are refreshing a\n
        test database from production, and as a result is very opinionated.\n
        As a brief overview, this command will:\n
            1. Create a clone from 'volume' and present the new volume to 'server'.\n
            2. Remove anything mounted at 'mountpoint' on 'server'.\n
            3. Clean any old disks/multipath devices associated with the\n
               the previous volume mounted at 'mountpoint', if applicable.\n
            4. Mount the newly created view volume on 'server', modifying\n
               /etc/fstab so that the mountpoint will be persistent.\n
        This option can be potentially dangerous, so use caution.\n
        """,
    )
    parser_clone.add_argument(
        'volume',
        type=str,
        help='volume to clone',
    )
    parser_clone.add_argument(
        'server',
        type=str,
        help='target server to mount cloned volume',
    )
    parser_clone.add_argument(
        'mountpoint',
        type=str,
        help='mountpoint for cloned volume on server',
    )
    parser_clone.add_argument(
        '-y',
        '--assume_yes',
        action='store_true',
        help='Do not prompt for confirmation. Potentially dangerous!',
    )

    args = parser.parse_args()

    # determine which controller to use based on datacenter
    host = args.host
    sc_id = None
    ### TODO: replace organization-specific logic
    if args.datacenter == '':
        sc_id = ''

    if not host or not sc_id:
        raise CompellentException('Unable to determine which Dell Storage Manager to use')

    # use local user keyring to store password securely
    password = keyring.get_password('dell_storage_manager', args.user)

    if args.change_password or not password:
        keyring.set_password(
            'dell_storage_manager',
            args.user,
            getpass.getpass(prompt='Enter Dell Storage Manager password for user {}: '.format(args.user)),
        )
        password = keyring.get_password('dell_storage_manager', args.user)

    # disable warnings from requests module
    if args.insecure:
        requests.packages.urllib3.disable_warnings()

    # define base URL for DSM REST API interface
    base_url = 'https://{}:{}/api/rest/'.format(host, args.port)

    # define HTTP content headers
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'x-dell-api-version': args.api_version,
    }

    # define the connection session
    connection = requests.Session()
    connection.auth = (args.user, password)

    # login to DSM instance
    path = '/ApiConnection/Login'
    complete_url = '{}{}'.format(base_url, path if path[0] != '/' else path[1:])
    try:
        connection.post(complete_url, headers=headers, verify=args.verify_certificate, timeout=3)
    except:
        raise CompellentException('Unable to login, server has not responded for 3 seconds')

    # enclose all steps in try-finally to ensure connection closed at end
    try:
        if args.server:
            # search for server
            path = '/StorageCenter/StorageCenter/{}/ServerList'.format(sc_id)
            complete_url = '{}{}'.format(base_url, path if path[0] != '/' else path[1:])
            try:
                response = connection.get(complete_url, headers=headers, verify=args.verify_certificate, timeout=3)
            except:
                raise CompellentException('Exceeded 3 second timeout during request: {}'.format(complete_url))
            servers = response.json()

            server_id = None
            for server in servers:
                # make sure the server object is not null
                if server:
                    # retrieve instanceId value for server
                    if server['name'] == server_short or server['name'] == server_fqdn:
                        server_id = server['instanceId']

            if not server_id:
                raise CompellentException('Could not find server {}'.format(args.server))

            # retrieve list of volumes mapped to server
            path = '/StorageCenter/ScServer/{}/MappingList'.format(server_id)
            complete_url = '{}{}'.format(base_url, path if path[0] != '/' else path[1:])
            try:
                response = connection.get(complete_url, headers=headers, verify=args.verify_certificate, timeout=3)
            except:
                raise CompellentException('Exceeded 3 second timeout during request: {}'.format(complete_url))
            server_mappings = response.json()

            server_volumes = set()
            for mapping in server_mappings:
                # make sure the mapping object is not null
                if mapping:
                    server_volumes.add(mapping['volume']['instanceName'])

            print('List of volumes mapped to server {}:'.format(args.server))
            for volume in server_volumes:
                print(volume)

        elif args.volume:
            # retrieve list of all volumes
            path = '/StorageCenter/StorageCenter/{}/VolumeList'.format(sc_id)
            complete_url = '{}{}'.format(base_url, path if path[0] != '/' else path[1:])
            try:
                response = connection.get(complete_url, headers=headers, verify=args.verify_certificate, timeout=3)
            except:
                raise CompellentException('Exceeded 3 second timeout during request: {}'.format(complete_url))
            volumes = response.json()

            volume_object = None
            for volume in volumes:
                # ensure volume object is not null
                if volume:
                    if volume['name'] == args.volume:
                        volume_object = volume
            if not volume_object:
                raise CompellentException('Could not find volume {}'.format(args.volume))

            # create snapshot of volume
            volume_id = volume_object['instanceId']
            data = {
                'Description': '{} on-demand'.format(args.user),
                'ExpireTime': str(expiration),
            }

            path = '/StorageCenter/ScVolume/{}/CreateReplay'.format(volume_id)
            complete_url = '{}{}'.format(base_url, path if path[0] != '/' else path[1:])
            try:
                response = connection.post(
                    complete_url,
                    data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                    headers=headers,
                    verify=args.verify_certificate,
                    timeout=3
                )
            except:
                raise CompellentException('Exceeded 3 second timeout during request: {}'.format(complete_url))
            snapshot = response.json()
            print(json.dumps(snapshot, indent=4))

    finally:
        # logout from DSM instance
        path = '/ApiConnection/Logout'
        complete_url = '{}{}'.format(base_url, path if path[0] != '/' else path[1:])
        try:
            connection.post(complete_url, headers=headers, verify=args.verify_certificate, timeout=3)
        except:
            raise CompellentException('Unable to logout, server has not responded for 3 seconds')


if __name__ == '__main__':
    main()


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
