"""
Copy from (TACC) S3 storage to Agave-managed storage and route filename to
downstream processors based on rules defined in config.yml#routings
"""
import json
import re
import os
import shutil
import sys

from pprint import pprint
from time import sleep
from random import random, shuffle
from attrdict import AttrDict
from datetime import datetime, timedelta
from agavepy.agave import AgaveError

from datacatalog.agavehelpers import AgaveHelper, AgaveHelperException
from datacatalog.utils import safen_path

from reactors.runtime import Reactor, agaveutils, process
from agavehelpers import resilient_files_pems
from s3helpers import S3Helper, S3HelperException
from copyfile import copyfile
from routemsg import routemsg

from posixhelpers import get_posix_paths, get_posix_mkdir, get_posix_copy
from posixhelpers import get_agave_dest, get_agave_parents

EXCLUDES = ['.placeholder$']


def main():
    # Minimal Message Body:
    # { "uri": "s3://uploads/path/to/target.txt"}

    r = Reactor()
    m = AttrDict(r.context.message_dict)
    # ! This code fixes an edge case and will be moved lower in the stack
    if m == {}:
        try:
            jsonmsg = json.loads(r.context.raw_message)
            m = jsonmsg
        except Exception:
            pass

    # Use JSONschema-based message validator
    if not r.validate_message(m):
        r.on_failure('Received invalid message', None)

    # Rename m.Key so it makes semantic sense elsewhere in the code
    s3_uri = m.get('uri')
    if s3_uri.endswith('/'):
        s3_uri = s3_uri[:-1]
    only_sync = m.get('sync', False)
    generated_by = m.get('generated_by', [])
    r.logger.info('Processing {}'.format(s3_uri))

    sh = S3Helper()
    ah = AgaveHelper(r.client)

    # Map POSIX source and destination
    s3_bucket, srcpath, srcfile = sh.from_s3_uri(s3_uri)
    print(s3_bucket, srcpath, srcfile)
    s3_full_relpath = os.path.join(s3_bucket, srcpath, srcfile)
    if r.settings.safen_paths:
        # Munge out unicode characters on upload. Default for safen_path
        # also transforms spaces into hyphen character
        ag_full_relpath = safen_path(s3_full_relpath,
                                     no_unicode=True,
                                     no_spaces=True)
        if ag_full_relpath != s3_full_relpath:
            r.logger.warning(
                'Transformed original path from {} to {}'.format(
                    s3_full_relpath, ag_full_relpath))
    else:
        ag_full_relpath = s3_full_relpath

    ag_uri = 'agave://data-sd2e-community/' + ag_full_relpath
    print(ag_full_relpath, ag_uri)
    posix_src = sh.mapped_catalog_path(s3_full_relpath)
    posix_dest = ah.mapped_posix_path(os.path.join('/', ag_full_relpath))
    # agave_full_path = agave_dest
    to_process = []

    r.logger.debug('posix_src: {}'.format(posix_src))
    r.logger.debug('posix_dst: {}'.format(posix_dest))

    def cmpfiles(posix_src, posix_dest, mtime=True, size=True, cksum=False):

        # Existence
        if not os.path.exists(posix_dest):
            print('DESTINATION.MISSING')
            return False

        if not os.path.exists(posix_src):
            print('SOURCE.MISSING')
            return False

        # Both files exist, so read in POSIX stat
        stat_src = os.stat(posix_src)
        stat_dest = os.stat(posix_dest)

        # Modification time (conditional)
        if mtime:
            # Mtime on source should never be more recent than
            # destination, as destination is a result of a copy
            # operation. We might need to add ability to account
            # for clock skew but at present we assume source and
            # destination filesystems are managed by the same host
            if stat_src.st_mtime > stat_dest.st_mtime:
                print('MODTIME')
                return False
        # Size (conditional)
        if size:
            if stat_src.st_size != stat_dest.st_size:
                print('SIZE')
                return False
        if cksum:
            # Not implemented
            # TODO Implement very fast hasher instead of sha256 for sync
            #      1. https://github.com/kalafut/py-imohash
            #      2. https://pypi.org/project/xxhash/
            raise NotImplementedError('Checksum comparison is not yet implemented')

        # None of the False tests returned so we can safely return True
        return True

    # Is the source physically a FILE?
    if not sh.isdir(posix_src):
        # If in sync mode, check if source and destination differ
        if only_sync is True and cmpfiles(posix_src, posix_dest, mtime=False):
            # if os.path.exists(posix_dest) and only_sync is True:
            r.logger.debug('Source == destination for {}'.format(os.path.basename(posix_src)))
        else:
            # Not in sync mode - force overwrite destination with source
            r.logger.info('Source != destination for {}'.format(os.path.basename(posix_src)))
            print(posix_src, posix_dest, ag_uri)
            copyfile(r, posix_src, posix_dest, ag_uri)
            routemsg(r, ag_uri)
    else:
        # It's a directory. Recurse through it and launch file messages to self
        r.logger.debug('Listdir: {}'.format(posix_src))
        to_process = sh.listdir(posix_src, recurse=True, bucket=s3_bucket, directories=False)
        pprint(to_process)
        r.logger.info('Found: {} sync tasks'.format(len(to_process)))

        # List to_list is constructed in POSIX ls order. Adding a shuffle
        # spreads the processing evenly over all files
        shuffle(to_process)
        batch_sub = 0
        for procpath in to_process:
            try:
                print('PROCPATH: ', procpath)
                # Here is the meat of the directory syncing behavior
                posix_src = sh.mapped_catalog_path(procpath)
                posix_dest = ah.mapped_posix_path(os.path.join('/', procpath))
                if (only_sync is False or cmpfiles(posix_src, posix_dest, mtime=False) is False):
                    r.logger.debug('Launch: {}'.format(procpath))
                    actor_id = r.uid
                    resp = dict()
                    s3_msg_uri = 's3://' + procpath
                    r.logger.info('s3_uri: {}'.format(s3_msg_uri))
                    message = {'uri': s3_msg_uri,
                               'generated_by': generated_by,
                               'sync': only_sync}
                    if r.local is False:
                        try:
                            resp = r.send_message(
                                actor_id, message, retryMaxAttempts=3,
                                ignoreErrors=False)
                            if 'executionId' in resp:
                                r.logger.info('Task Id for {}: {}'.format(
                                    procpath, resp['executionId']))
                            else:
                                raise AgaveError(
                                    'Task not submitted for {}'.format(procpath))
                        except Exception as lexc:
                            raise AgaveError('Failed to message self')
                    else:
                        pprint(message)

                    batch_sub += 1
                    # Always sleep a little bit between task submissions
                    sleep(random() * r.settings.batch.task_sleep_duration)
                    # Sleep a little longer every N submissions
                    if batch_sub > r.settings.batch.size:
                        batch_sub = 0
                        if r.settings.batch.randomize_sleep:
                            sleep(random() * r.settings.batch.sleep_duration)
                        else:
                            sleep(r.settings.batch.sleep_duration)
                else:
                    r.logger.debug('Source == destination for {}'.format(os.path.basename(procpath)))
            except Exception as exc:
                r.logger.critical(
                    'Failed to dispatch task to self: {}, {}'.format(ag_full_relpath, exc))


if __name__ == '__main__':
    main()
