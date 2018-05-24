Compellent REST Utilities
=========================

This project comprises utilities to interact with a Dell Compellent Storage
Manager server using the REST API that the Data Collector exposes. Python 3.6 is
a hard requirement due to some features of subprocess that I used. Python is
available to install through most package managers (yum, apt, homebrew) or
directly from the `Python website <https://www.python.org/downloads/>`_.

The utility is accessed through the compellent module, and exposes simple
access to query information about volumes mapped to servers, take snapshots
of a particular volume, and create and mount a view volume of a volume from
a source server to a target server.

This module layout was adapted from Kenneth Reitz's
`samplemod <https://github.com/kennethreitz/samplemod>`_, with the intent to
package the module using `WinPython <https://winpython.github.io/>`_ and
`Inno Setup <http://www.jrsoftware.org/isinfo.php>`_.

Certain code was inspired by the official `Dell Storage Flocker Driver 
<https://github.com/dellstorage/storagecenter-flocker-driver>`_, but none has
been intentionally copied.

The code is hosted on my 
`Compellent repo <https://github.com/jwegner89/compellent>`_.
