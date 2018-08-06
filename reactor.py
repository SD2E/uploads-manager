"""
Copy from (TACC) S3 storage to Agave-managed storage
"""
import json
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
    r.logger.debug(s3_uri)

    # Map POSIX source and destination
    posix_src, posix_dest = get_posix_paths(s3_uri, r.settings)

    # Map the Agave path for destination
    agave_dest = get_agave_dest(posix_dest, r.settings)

    # TODO Implement routings

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

    # Do copy with forced overwrite
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


    # Grant Agave permissions on the copied file
    for grant in r.settings.destination.grants:
        r.logger.debug('Grant {} to {} on {}'.format(
            grant.pem, grant.username, agave_dest))
        if r.local is False:
            try:
                resilient_files_pems(r.client, agave_dest, grant.username,
                                    grant.pem, grant.recursive)
            except Exception:
                r.logger.warning('Grant failed for {}'.format(agave_dest))

    # Agave permission grants on created parent directories
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

    # TODO Kick off downstream Reactors
    # capture-fixity
    actor_id = r.settings.linked_reactors.get(
        'capture-fixity', {}).get('id', None)
    message = {'uri': agave_dest}
    try:
        r.send_message(actor_id, message=message)
    except Exception as exc:
        r.on_failure("Failed to launch 'capture-fixity'", exc)

    r.on_success('Task completed')

if __name__ == '__main__':
    main()
