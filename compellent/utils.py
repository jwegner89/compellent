# -*- coding: utf-8 -*-

"""
Utility functions used by other parts of the Compellent module
"""

import socket
import string
from .connection import DSMConnection, SSHConnection
from .exceptions import CompellentException


def minutes_conversion(time):
    """
    Converts time-formatted strings to integer minute equivalents.

    Acceptable values are of the forms [positive integer] or 
    [positive integer][modifier], where [modifier] are short subsitutions
    for a time period. Modifier values are as follows:

        h = hours = 60 minutes
        d = days = 24 hours = 1440 minutes
        w = weeks = 7 days = 10080 minutes
        m = months = 30 days = 43200 minutes
        y = years = 365 days = 525600 minutes

    Examples:
        5d returns 7200
        3m returns 129600

    :param time: coded time string to convert to minutes
    :raises CompellentException: Compellent module catch-all exception
    :return: integer value of provided time string
    """

    # check if plain integer without modifier
    if time[-1] in string.digits:
        try:
            value = int(time)
        except ValueError:
            # integer conversion error
            raise CompellentException('Cannot convert {} to integer'.format(time))
        # make sure value is positive
        if int(time) < 0:
            raise CompellentException('Expiration time value cannot be negative')
        return int(time)

    # split off value from modifier, ensure modifier has consistent case
    value, modifier = time[:-1], time[-1].lower()

    try:
        value = int(value)
    except ValueError:
        # integer conversion failed
        raise CompellentException('Invalid time string format {}'.format(time))

    # make sure value is positive
    if value < 0:
        raise CompellentException('Expiration time value cannot be negative')

    if modifier not in 'hdwmy':
        raise CompellentException('Invalid time modifier: {}'.format(modifier))

    multiplier = None
    if modifier == 'h':
        multiplier = 60
    elif modifier == 'd':
        multiplier = 24 * 60
    elif modifier == 'w':
        multiplier = 7 * 24 * 60
    elif modifier == 'm':
        multiplier = 30 * 24 * 60
    elif modifier == 'y':
        multiplier = 365 * 24 * 60
    else:
        raise CompellentException('Multiplier not assigned correctly')

    return value * multiplier


def resolve_host(hostname, domains):
    """
    Attempt to resolve hostname to its fully-qualified domain name.

    :param str hostname: hostname to resolve
    :param list domains: list of domains to attempt
    :raises CompellentException: Compellent module catch-all exception
    :return: tuple containing short name and fully-qualified name
    """
    # unify to lowercase
    hostname = hostname.lower()
    for i in range(len(domains)):
        domains[i] = domains[i].lower()

    short = ''
    fqdn = ''
    if '.' in hostname:
        # assume name is fully qualified
        short = hostname.split('.')[0]
        fqdn = hostname
        try:
            socket.gethostbyname(fqdn)
        except:
            raise CompellentException('Unable to resolve hostname {}'.format(hostname))
    else:
        short = hostname
        resolved = False
        for domain in domains:
            fqdn = '{}{}'.format(short, domain)
            try:
                socket.gethostbyname(fqdn)
                # no exception thrown, so name was resolved
                resolved = True
                # do not consider other domains
                break
            except:
                # name was not resolved
                pass
        if not resolved:
            raise CompellentException('Unable to resolve hostname {}'.format(hostname))

    if short == '' or fqdn == '':
        raise CompellentException('Unable to resolve hostname {}'.format(hostname))

    return short, fqdn


def refresh(dsm, ssh, src_server, dest_server, volume, environment, mountpoint):
    """
    Refresh clone of volume from src_server to dest_server

    :param DSMConnection dsm: connection to Dell Storage Manager server
    :param SSHConnection ssh: SSH connection to destination server
    :param str src_server: name of source server from which to clone volume
    :param str dest_server: name of destination server to mount the cloned volume
    :param str volume: name of the volume to clone from src to dest
    :param str environment: name of destination environment, e.g. CSTST92
    :param str mountpoint: mountpoint for cloned volume on destination server
    :raises CompellentException: Compellent module catch-all exception
    """
    # canonicalize server names to lower case
    src_server = src_server.lower()
    dest_server = dest_server.lower()

    if src_server == dest_server:
        raise CompellentException('Source cannot be the same as destination')

    if 'prd' in dest_server:
        raise CompellentException('We do not allow refreshing to production servers')

    # ensure that provided source and target servers are resolvable
    src_short, src_fqdn = resolve_host(src_server)
    dest_short, dest_fqdn = resolve_host(dest_server)

    ### TODO: remove organization-specific logic
    mount = mountpoint
    if '/' in mount:
        mount = mount.split('/')[-1]
    if '-' in mount:
        mount = mount.split('-')[-1]
    if '_' in mount:
        mount = mount.split('_')[-1]

    date_string = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    vol_name = 'vv_{src}_{mount}_{environment}_{date_string}'.format(
        src=src_short,
        mount=mount,
        environment=environment,
        date_string=date_string,
    )

    # retrieve source and destination server objects
    src_matches = dsm.search_server(src_short)
    if len(src_matches) != 1:
        raise CompellentException(
            'Ambiguous or non-existent server {}'.format(src_server))
    dest_matches = dsm.search_server(dest_short)
    if len(dest_matches) != 1:
        raise CompellentException(
            'Ambiguous or non-existent server {}'.format(dest_server))

    src = src_matches[0]
    dest = dest_matches[0]
    src_id = src['instanceId']
    dest_id = dest['instanceId']
    # retrieve source's volume object
    src_mappings = dsm.search_server_mappings(src_id, volume)
    if len(src_mappings) != 1:
        raise CompellentException(
            'Ambiguous or non-existent volume {}'.format(volume))
    src_volume = src_mappings[0]
    # clean old clone of volume from dest if present
    # unmap old clone of volume mappings if present
    # move old clone volume to recycle bin if present
    # take snapshot of volume, retain snapshot ID
    src_snapshot = dsm.snapshot(src_id, 'temp view vol snap', '15m')
    # retrieve view volume folder object
    folder_name = 'Linux/View Volumes/{}/'.format(src_short)
    folders = dsm.search_volume_folder(folder_name)
    if len(folders) == 0:
        # folder not found, so we need to create it
        folder = dsm.create_volume_folder(folder_name)
    else:
        # folder exists, so unpack it
        folder = folders[0]
    # create view volume from snapshot, retain new volume ID
    dest_volume = dsm.view_volume(src_snapshot['instanceId'], vol_name, folder['instanceId'])
    # change dest_volume's storage profile to recommended/all tiers
    recommended_profile = dsm.sc_id + '.1'
    dsm.modify_volume_configuration()
    # map view volume to dest
    # change filesystem UUID to prevent future clone errors
    # rescan disks on dest
    # fix multipath friendly name for new volume
    # mount new volume at previous mount location


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
