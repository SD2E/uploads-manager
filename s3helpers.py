
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import *

import re
import os
import sys


class S3HelperException(Exception):
    pass


class S3Helper(object):
    def __init__(self, client=None):
        self.BUCKET = os.environ.get('TACC_S3_BUCKET', 'uploads')
        self.STORAGE_PREFIX = os.environ.get('TACC_S3_ROOTDIR', '/corral/s3/ingest')
        self.STORAGE_PAGESIZE = -1
        self.client = client

    def from_s3_uri(self, uri=None, validate=False):
        """Parse an S3 URI into a tuple (bucketName, directoryPath, fileName)
        Validation that it points to a real resource is not implemented. The
        same caveats about validation apply here as in to_agave_uri()"""
        bucketName = None
        dirPath = None
        fileName = None
        proto = re.compile(r's3:\/\/(.*)$')
        if uri is None:
            raise ValueError("URI cannot be empty")
        resourcepath = proto.search(uri)
        if resourcepath is None:
            raise ValueError("Unable resolve URI")
        resourcepath = resourcepath.group(1)
        firstSlash = resourcepath.find('/')
        if firstSlash is -1:
            raise ValueError("Unable to resolve bucketName")
        try:
            bucketName = resourcepath[0:firstSlash]
            origDirPath = resourcepath[firstSlash + 1:]
            dirPath = os.path.dirname(origDirPath)
            fileName = os.path.basename(origDirPath)
            return (bucketName, dirPath, fileName)
        except Exception as e:
            raise ValueError(
                "Unable to resolve directoryPath or fileName: {}".format(e))

    def mapped_bucket_path(self, path, bucket=None):
        # Project bucket-relative path to absolute posix path
        # if bucket is None:
        #     bucket = self.BUCKET
        #     prefix = AgaveSystems.storage[bucket]['root_dir']
        # else:
        if not path.startswith(self.STORAGE_PREFIX):
            if path.startswith('/'):
                path = path[1:]
            return os.path.join(self.STORAGE_PREFIX, self.BUCKET, path)
        else:
            return path

    def mapped_catalog_path(self, path, bucket=None):
        # Project catalog-relative path to absolute posix path
        # if bucket is None:
        #     bucket = self.BUCKET
        #     prefix = AgaveSystems.storage[bucket]['root_dir']
        # else:
        if not path.startswith(self.STORAGE_PREFIX):
            if path.startswith('/'):
                path = path[1:]
            return os.path.join(self.STORAGE_PREFIX, path)
        else:
            return path

    def exists(self, path, bucket=None):
        # Determine if a catalog-relative path exists
        # Determine if a catalog-relative path is a file
        if bucket is None:
            bucket = self.BUCKET
        checkpath = path
        if checkpath.startswith('/'):
            checkpath = checkpath[1:]
        if not checkpath.startswith(bucket):
            raise S3HelperException('Path must be absolute and references to storage system root')

        print('EXISTS?', self.mapped_catalog_path(path))
        try:
            if os.path.exists(self.mapped_catalog_path(path, bucket)):
                return True
            else:
                return False
        except Exception as exc:
            raise S3HelperException('Function failed', exc)

    def isfile(self, path, bucket=None):
        # Determine if a catalog-relative path is a file
        if bucket is None:
            bucket = self.BUCKET
        try:
            testpath = self.mapped_catalog_path(path, bucket)
            print('ISFILE?', self.mapped_catalog_path(path))
            if os.path.exists(testpath) and os.path.isfile(testpath):
                return True
            else:
                return False
        except Exception as exc:
            raise S3HelperException('Function failed', exc)

    def isdir(self, path, bucket=None):
        # Determine if a catalog-relative path is a directory
        if bucket is None:
            bucket = self.BUCKET
        try:
            testpath = self.mapped_catalog_path(path, bucket)
            if os.path.exists(testpath) and os.path.isdir(testpath):
                return True
            else:
                return False
        except Exception as exc:
            raise S3HelperException('Function failed', exc)

    def paths_to_s3_uris(self, filepaths, bucket=None):
        """Transform a list of absolute catalog paths to s3-canonical URIs"""
        if bucket is None:
            bucket = self.BUCKET
        uri_list = []
        for f in filepaths:
            if f.startswith('/'):
                f = f[1:]
            uri_list.append(os.path.join('s3://', f))
        return uri_list

    def dirname(self, path, bucket=None):
        raise NotImplementedError()

    def islink(self, path, bucket=None):
        raise NotImplementedError()

    def listdir(self, path, recurse=True, bucket=None, directories=True):
        """Return a list containing the names of the entries in the directory
        given by path.

        Gets a directory listing from the default storage system unless specified.
        For performance, direct POSIX is tried first, then API if that fails.

        Parameters:
        path:str - storage system-absolute path to list
        Arguments:
        bucket:str - non-default Agave storage system
        Returns:
        listing:list - all directory contents
        """
        if bucket is None:
            bucket = self.BUCKET
        try:
            return self.listdir_s3_posix(path, recurse, bucket, directories)
        except Exception as exc:
            raise S3HelperException('Function failed', exc)

    def listdir_s3_posix(self, path, recurse=True, bucket=None, directories=True, current_listing=[]):
        if bucket is None:
            bucket = self.BUCKET
        abspath = self.mapped_catalog_path(path, bucket)
        listing = list()
        for dirname, dirnames, filenames in os.walk(abspath):
            if directories is True:
                for subdirname in dirnames:
                    itempath = os.path.join(dirname, subdirname)
                    listing.append(self.relativepath(itempath))
            for filename in filenames:
                itempath = os.path.join(dirname, filename)
                listing.append(self.relativepath(itempath))
        return listing

    def relativepath(self, path, bucket=None):
        if bucket is None:
            bucket = self.BUCKET
        retpath = path.replace(self.STORAGE_PREFIX, '')
        if retpath.startswith('/'):
            retpath = retpath[1:]
        return retpath

    def listdir_s3_lustre(self, path, recurse=True, bucket=None, directories=True, current_listing=[]):
        raise NotImplementedError(
            'Lustre support is not implemented. Consider using listdir_s3_posix().')

    def listdir_s3native(self, path, recurse, bucket=None, directories=True, current_listing=[]):
        raise NotImplementedError(
            'Native S3 support is not implemented. Consider using listdir_s3_posix().')

    def from_s3_uri(self, uri=None, validate=False):
        """Parse an S3 URI into a tuple (bucketName, directoryPath, fileName)
        Validation that it points to a real resource is not implemented. The
        same caveats about validation apply here as in to_agave_uri()"""
        bucketName = None
        dirPath = None
        fileName = None
        proto = re.compile(r's3:\/\/(.*)$')
        if uri is None:
            raise ValueError("URI cannot be empty")
        resourcepath = proto.search(uri)
        if resourcepath is None:
            raise ValueError("Unable resolve URI")
        resourcepath = resourcepath.group(1)
        firstSlash = resourcepath.find('/')
        if firstSlash is -1:
            raise ValueError("Unable to resolve bucketName")
        try:
            bucketName = resourcepath[0:firstSlash]
            origDirPath = resourcepath[firstSlash + 1:]
            dirPath = os.path.dirname(origDirPath)
            fileName = os.path.basename(origDirPath)
            return (bucketName, dirPath, fileName)
        except Exception as e:
            raise ValueError(
                "Unable to resolve directoryPath or fileName: {}".format(e))
