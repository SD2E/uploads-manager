"""
Copy from (TACC) S3 storage to Agave-managed storage and route filename to
downstream processors based on rules defined in config.yml#routings
"""
import json
import re
import os
from attrdict import AttrDict
from reactors.runtime import Reactor, agaveutils, process
from tenacity import retry
from tenacity import stop_after_delay
from tenacity import wait_exponential


def get_posix_paths(s3_uri, settings):
    '''Get absolute POSIX paths to source and destination'''
    file_path = s3_uri.replace(settings.source.bucket, '')
    if file_path.startswith('/'):
        file_path = file_path[1:]
    src = os.path.join(settings.source.posix_path, file_path)
    dst = os.path.join(settings.destination.posix_path, file_path)
    return src, dst


def get_agave_dest(dest_path, settings):
    '''Get full agave-canonical URI for destination'''
    return dest_path.replace(settings.destination.posix_path,
                             settings.destination.bucket)


def get_posix_mkdir(dest_path, settings, validate_path=True):
    '''Get a command in params[] form to make destination directory'''
    dest_parent = os.path.dirname(dest_path)
    if validate_path:
        if os.path.isdir(dest_parent):
            return []

    command_params = ['mkdir', '-p', dest_parent]
    return command_params


def get_posix_copy(src, dest, settings, validate_path=True):
    '''Get a command in params[] form to copy a file'''
    command_params = []
    if validate_path:
        if not os.path.isfile(src):
            return []
        if not os.path.isdir(os.path.dirname(dest)):
            return []

    command_params = ['cp', '-af', src, dest]
    return command_params


def get_agave_parents(posix_dest_path, posix_base, bucket):
    '''Get list of Agave uri paths including self and parents from POSIX path'''
    # Strip filesystem mount path
    path_list = []
    agave_path = posix_dest_path.replace(posix_base, bucket)
    while agave_path != bucket:
        path_list.append(agave_path)
        agave_path = os.path.dirname(agave_path)
    return path_list


@retry(stop=stop_after_delay(32), wait=wait_exponential(multiplier=2, max=8))
def resilient_files_pems(agaveClient, agaveUri, username, permission, recursive=False):
    response = None
    try:
        systemId, agavePath, agaveFile = agaveutils.from_agave_uri(agaveUri)
        agaveAbsolutePath = os.path.join(agavePath, agaveFile)
        pemBody = {'username': username,
                   'permission': permission,
                   'recursive': recursive}
        response = agaveClient.files.updatePermissions(systemId=systemId,
                                                       filePath=agaveAbsolutePath,
                                                       body=pemBody)
        return True
    except Exception:
        raise
    return False


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
        r.on_failure('Invalid message received', None)

    # Rename m.Key so it makes semantic sense elsewhere in the code
    s3_uri = m.get('uri')
    only_sync = m.get('sync', False)
    r.logger.debug(s3_uri)

    # Map POSIX source and destination
    posix_src, posix_dest = get_posix_paths(s3_uri, r.settings)

    # Map the Agave path for destination
    agave_dest = get_agave_dest(posix_dest, r.settings)

    if os.path.exists(posix_dest) and only_sync is True:
        r.on_success('Destination exists and event mode==sync: Skipping file copy and event triggering.')

    # Create POSIX directory path at destination
    do_validate = not r.local
    cmdset = get_posix_mkdir(posix_dest, r.settings, do_validate)
    created_path = None
    if len(cmdset) > 0:
        r.logger.debug('Process: "{}"'.format(cmdset))
        if r.local is True:
            created_path = os.path.dirname(posix_dest)
        else:
            response = process.run(cmdset)
            if response.return_code > 0:
                r.on_failure('Failed with code {}'.format(
                    response.return_code), None)
            else:
                r.logger.debug('{} ran in {} msec'.format(
                    cmdset[0], response.elapsed_msec))
                created_path = cmdset[2]

    # Do POSIX copy with forced overwrite
    do_validate = not r.local
    cmdset = get_posix_copy(posix_src, posix_dest, r.settings, do_validate)
    copied_path = None
    if len(cmdset) > 0:
        if r.local is True:
            r.logger.debug('Process: "{}"'.format(cmdset))
        else:
            response = process.run(cmdset)
            if response.return_code > 0:
                r.on_failure('Failed with code {}'.format(
                    response.return_code), None)
            else:
                r.logger.debug('{} ran in {} msec'.format(
                    cmdset[0], response.elapsed_msec))
                copied_path = cmdset[3]

    # Do Agave permission grants on the copied file
    for grant in r.settings.destination.grants:
        r.logger.debug('Grant {} to {} on {}'.format(
            grant.pem, grant.username, agave_dest))
        if r.local is False:
            try:
                resilient_files_pems(r.client, agave_dest, grant.username,
                                    grant.pem, grant.recursive)
            except Exception:
                r.logger.warning('Grant failed for {}'.format(agave_dest))

    # Do Agave permission grants on created parent directories
    if created_path is not None:
        agave_path_list = get_agave_parents(
            created_path, r.settings.destination.posix_path,
            r.settings.destination.bucket)
        r.logger.debug('Do grants for {}'.format(agave_path_list))
        if r.local is False:
            for ag_uri in agave_path_list:
                for grant in r.settings.destination.grants:
                    try:
                        resilient_files_pems(r.client, ag_uri, grant.username,
                                            grant.pem, grant.recursive)
                    except Exception:
                        r.logger.warning('Grant failed for {}'.format(ag_uri))

    # Kick off downstream Reactors by filename glob match
    message = {'uri': agave_dest}
    for routename, globs in r.settings.routings.items():
        actor_id = r.settings.linked_reactors.get(routename, {}).get('id')
        for glob in globs:
            if re.compile(glob).search(agave_dest):
                try:
                    r.send_message(actor_id, message=message)
                    break
                except Exception as exc:
                    r.on_failure('Failed to launch {}:{} for {}'.format(
                        routename, actor_id, agave_dest), exc)


        r.on_success('Completed in {} usec'.format(r.elapsed()))

if __name__ == '__main__':
    main()
