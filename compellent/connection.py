# -*- coding: utf-8 -*-

"""
Operations using a connection to the Dell Storage Manager server
"""

import datetime
import fnmatch
import json
import paramiko
import re
import requests
import sys
from .exceptions import CompellentException
from .utils import minutes_conversion, resolve_host


class DSMConnection:
    """
    Dell Storage Manager connection
    Basically a wrapper around requests.Session storing extra variables
    Can be used as a context manager.
    """

    def __init__(self)
        """
        Establish a connection with a Dell Storage Manager server
        """

        self.host = None
        self.port = None
        self.sc_id = None
        self.user = None
        self.password = None
        self.api_version = None
        self.verify = True
        self.timeout = None
        self.connection = None
        self.base_url = None
        self.headers = dict()


    def __enter__(self):
        """
        Required for use as a context manager
        """
        return self


    def __exit__(self):
        """
        Required for use as a context manager
        """
        self.disconnect()


    def connect(self):
        """
        Initiate connection using previously set parameters

        :raises CompellentException: catch-all exception for Compellent module
        """
        # disable warnings from requests module
        if not self.verify:
            requests.packages.urllib3.disable_warnings()

        # define base URL for DSM REST API interface
        self.base_url = 'https://{}:{}/api/rest'.format(self.host, self.port)

        # define HTTP content headers
        self.headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
            'x-dell-api-version': self.api_version,
        }

        # define the connection session
        self.connection = requests.Session()
        self.connection.auth = (self.user, self.password)

        # login to DSM instance
        path = '/ApiConnection/Login'
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            self.connection.post(
                complete_url,
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            self.connection.close()
            raise CompellentException('Unable to login: timeout exceeded or invalid credentials')


    def disconnect(self):
        """
        Logout from the Dell Storage Manager

        :raises CompellentException: catch-all exception for Compellent module
        """
        path = '/ApiConnection/Logout'
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            self.connection.post(
                complete_url,
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            pass
        if self.connection:
            self.connection.close()


    def check_response(self, response):
        """
        Check the response of an HTTP operation.

        :param requests.models.Response response: HTTP response object
        :return: True if response status code in [200, 299]
        """
        return 200 <= response.status_code < 300


    def list_server_mappings(self, server_id):
        """
        Return all mappings associated with server

        :param str server_id: Compellent ID of server in question
        :return: JSON object containing all mappings for server_id
        :raises CompellentException: Compellent module catch-all exception
        """
        path = '/StorageCenter/ScServer/{}/MappingList'.format(source_id)
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            response = self.connection.get(
                complete_url,
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Exceeded timeout during request: {}'.format(complete_url))
        return response.json()


    def search_server_mappings(self, server_id, mapping_name):
        """
        Search for server mapping name from string pattern.
        The matching criteria is based on the fnmatch module, which allows
        simple shell-like filename pattern matching.

        :param str server_id: ID of server to search for mappings
        :param str mapping_name: pattern to match name of the target mapping
        :raises CompellentException: Compellent module catch-all exception
        :return: dictionary version of a JSON object containing all matching objects
        """
        mappings = self.list_server_mappings(server_id)
        matches = list()
        for mapping in mappings:
            # ensure mapping object is not null
            if mapping:
                if fnmatch.fnmatch(mapping['volume']['instanceName'], mapping_name):
                    matches.append(mapping)
        return matches


    def list_volume_mapping_profiles(self, volume_id):
        """
        Return all mapping profiles associated with volume

        :param str volume_id: Compellent ID of volume in question
        :return: JSON object containing all mappings for volume_id
        :raises CompellentException: Compellent module catch-all exception
        """
        path = '/StorageCenter/ScVolume/{}/MappingProfileList'.format(volume_id)
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            response = self.connection.get(
                complete_url,
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Exceeded timeout during request: {}'.format(complete_url))
        return response.json()


    def list_volume_folders(self, folder_id='0'):
        """
        List all volume folders from the specified level.
        Defaults to listing from the root level.

        :param str folder_id: Instance ID of folder to list children folders
        :raises CompellentException: Compellent module catch-all exception
        :return: dictionary of all folders which are children of the folder_id parent
        """
        if '.' not in folder_id:
            folder_id = self.sc_id + folder_id
        path = '/StorageCenter/ScVolumeFolder/{}/VolumeFolderList'.format(folder_id)
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            response = self.connection.get(
                complete_url,
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Timeout exceeded while listing folders.')
        return response.json()


    def search_volume_folder(self, folder_name):
        """
        Search for volume folder name from string pattern.
        The matching criteria is based on the fnmatch module, which allows
        simple shell-like filename pattern matching.

        :param str folder_name: pattern to match name of the target folder
        :raises CompellentException: Compellent module catch-all exception
        :return: dictionary version of a JSON object containing all matching objects
        """
        folders = self.list_volume_folders()
        matches = list()
        for folder in folders:
            # ensure folder object is not null
            if folder:
                if fnmatch.fnmatch(folder['name'], folder_name):
                    matches.append(folder)
        return matches


    def create_volume_folder(self, name, parent, notes=None):
        """
        Create new volume folder

        :param str name: name of the volume folder to create
        :param str parent: instance ID of the parent folder
        :param str notes: Optional notes to add to the volume folder
        :raises CompellentException: Compellent module catch-all exception
        :return: newly created folder object
        """
        path = '/StorageCenter/ScVolumeFolder'
        complete_url = '{}{}'.format(self.base_url, path)
        data = {
            'StorageCenter': self.sc_id,
            'Name': name,
            'Parent': parent,
        }
        if notes:
            data['Notes'] = notes
        try:
            response = self.connection.post(
                complete_url,
                data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Timeout exceeded while listing folders.')
        return response.json()


    def list_volumes(self):
        """
        List all volumes managed by Dell Storage Manager

        :raises CompellentException: Compellent module catch-all exception
        :return: dictionary version of a JSON object containing all volumes
        """
        path = '/StorageCenter/ScVolumeFolder/{}/VolumeList'.format(self.sc_id)
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            response = self.connection.get(
                complete_url,
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Timeout exceeded while listing volumes.')
        return response.json()


    def map_volume(self, volume_id, server_id):
        """
        Map volume object to server object

        :param str volume_id: Compellent ID for the volume object
        :param str server_id: Compellent ID for the server object
        :raises CompellentException: Compellent module catch-all exception
        """
        # check if volume is already mapped to server
        mappings = self.list_volume_mappings(volume_id)
        for mapping in mappings:
            if mapping['Server'] == server_id:
                return mapping
        # otherwise create new mapping
        path = '/StorageCenter/ScVolume/{}/MapToServer'.format(volume_id)
        complete_url = '{}{}'.format(self.base_url, path)
        data = {
            'Server': server_id,
        }
        try:
            response = self.connection.post(
                complete_url,
                data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Timeout exceeded while mapping server to volume.')
        return response.json()


    def unmap_volume(self, volume_id, server_id):
        """
        Unmap volume object from server object

        :param str volume_id: Compellent ID for the volume object
        :param str server_id: Compellent ID for the server object
        :raises CompellentException: Compellent module catch-all exception
        """
        # retrieve all of volume's mapping
        mappings = self.list_volume_mappings(volume_id)
        # iterate through and delete any mapping profiles that match server ID
        for mapping in mappings:
            if mapping['Server'] == server_id:
                mapping_id = mapping['instanceId']
                path = '/StorageCenter/ScMappingProfile/{}'.format(mapping_id)
                complete_url = '{}{}'.format(self.base_url, path)
                try:
                    response = self.connection.delete(
                        complete_url,
                        headers=self.headers,
                        verify=self.verify,
                        timeout=self.timeout,
                    )
                except:
                    raise CompellentException('Timeout exceeded while deleting mapping profile.')


    def recycle_volume(self, volume_id):
        """
        Move volume object to the recycling bin

        :param str volume_id: Compellent ID for the volume object
        :raises CompellentException: Compellent module catch-all exception
        """
        path = '/StorageCenter/ScVolume/{}/Recycle'.format(volume_id)
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            response = self.connection.post(
                complete_url,
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Timeout exceeded while recycling volume with ID {}.'.format(volume_id))


    def search_volume(self, volume_name):
        """
        Search for volume name from string pattern.
        The matching criteria is based on the fnmatch module, which allows
        simple shell-like filename pattern matching.

        :param str volume_name: pattern to match name of the target volume
        :raises CompellentException: Compellent module catch-all exception
        :return: dictionary version of a JSON object containing all matching objects
        """
        volumes = self.list_volumes()
        matches = list()
        for volume in volumes:
            # ensure volume object is not null
            if volume:
                if fnmatch.fnmatch(volume['name'], volume_name):
                    matches.append(volume)
        return matches


    def view_volume(self, snapshot_id, volume_name):
        """
        Create cloned volume from snapshot

        :param str snapshot_id: Compellent ID of snapshot from which to create a view volume
        :param str volume_name: name to assign to newly created volume
        :raises CompellentException: Compellent module catch-all exception
        :return: Compellent ID of newly created volume
        """
        path = '/StorageCenter/ScServer/{}/MapToVolume'.format(server_id)
        complete_url = '{}{}'.format(self.base_url, path)
        data = {
            'Volume': volume_id,
        }
        try:
            response = self.connection.post(
                complete_url,
                data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Timeout exceeded while mapping server to volume.')
        return response.json()


    def list_servers(self):
        """
        List all servers managed by Dell Storage Manager

        :raises CompellentException: Compellent module catch-all exception
        :return: dictionary version of a JSON object containing all servers
        """
        path = '/StorageCenter/StorageCenter/{}/ServerList'.format(self.sc_id)
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            response = self.connection.get(
                complete_url,
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Exceeded timeout during request: {}'.format(complete_url))
        return response.json()


    def search_server(self, server_name):
        """
        Search for server from string pattern.
        The matching criteria is based on the fnmatch module, which allows
        simple shell-like filename pattern matching.

        :param str server_name: name of server for which to search
        :raises CompellentException: Compellent module catch-all exception
        :return: dictionary version of a JSON object containing all matching objects
        """
        servers = self.list_servers()
        matches = list()
        for server in servers:
            # make sure the server object is not null
            if server:
                if fnmatch.fnmatch(server['name'], server_name):
                    matches.append(server)
        return matches


    def get_server(self, server_name):
        """
        Retrieve server object with name server_name.

        :param str server_name: name of server to retrieve
        :raises CompellentException: Compellent module catch-all exception
        :return: server object corresponding to server_name
        """
        data = {
            'filter': {
                'filterType': 'AND',
                'filters': [
                    {
                        'attributeName': 'scSerialNumber',
                        'attributeValue': self.sc_id,
                        'filterType': 'Equals'
                    },
                    {
                        'attributeName': 'instanceName',
                        'attributeValue': server_name,
                        'filterType': 'Equals'
                    },
                ],
            },
        }
        path = '/StorageCenter/ScServer/GetList'
        complete_url = '{}{}'.format(base_url, path)
        try:
            response = connection.post(
                complete_url,
                data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise DellStorageException('Exceeded 10 second timeout during request: {}'.format(complete_url))
        return response.json()


    def snapshot(self, volume, description, expiration='1w'):
        """
        Create a snapshot from volume that will expire after the specified expiration

        :param str volume: Compellent ID of volume to snapshot
        :param str description: description of the snapshot
        :param str expiration: encoded string of desired expiration time in minutes
        :raises CompellentException: Compellent module catch-all exception
        :return: JSON object of created snapshot
        """
        data = {
            'Description': description,
            'ExpireTime': str(minutes_conversion(expiration)),
        }

        path = '/StorageCenter/ScVolume/{}/CreateReplay'.format(volume)
        complete_url = '{}{}'.format(self.base_url, path)
        try:
            response = self.connection.post(
                complete_url,
                data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
        except:
            raise CompellentException('Exceeded timeout during request: {}'.format(complete_url))
        return response.json()


class SSHConnection:
    """
    An SSH connection to a Linux host.
    Mostly a wrapper around a paramiko SSH connection with some Compellent-
    specific functionally added on top.
    Can be used as a context manager.
    """

    def __init__(self)
        """
        Establish a connection with remote Linux host
        """

        self.host = None
        self.port = 22
        self.user = 'root'
        self.password = None
        self.check_host_key = True
        self.connection = None


    def __enter__(self):
        """
        Required for use as a context manager.
        """
        return self


    def __exit__(self):
        """
        Required for use as a context manager.
        """
        self.close()


    def connect(self):
        """
        Initiate connection using previously set parameters.
        Paramiko will use SSH Agent keys if they are available.

        :raises CompellentException: catch-all exception for Compellent module
        """

        self.connection.load_system_host_keys()

        if not self.check_host_key:
            self.connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.connection.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
            )
        except paramiko.SSHException:
            raise CompellentException('Unable to connect as {}@{} using SSH'.format(self.user, self.host))


    def close(self):
        """
        Close paramiko.SSHClient connection.
        """
        if self.connection:
            self.connection.close()


    def mountpoint_to_serial(self, mountpoint):
        """
        Determine the Compellent serial number of the specified mountpoint.

        :param str mountpoint: mountpoint of Compellent device
        :return: string representing the Compellent serial number of the device
        :raises CompellentException: catch-all exception for Compellent module
        """
	# find device name of mountpoint
        stdin, stdout, stderr = self.connection.exec_command('findmnt --noheadings --list --output SOURCE {}'.format(args.mountpoint))
        device = stdout.read().decode('utf-8').strip()

        # find serial number of device
        stdin, stdout, stderr = self.connection.exec_command('lsblk --noheadings --list --output SERIAL {}'.format(device))
        serial = stdout.read().decode('utf-8').strip()

        return(serial)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
