import os


def get_posix_paths(s3_uri, settings):
    '''Get absolute POSIX paths to source and destination'''
    file_path = s3_uri.replace(settings.source.bucket, '')
    if file_path.startswith('/'):
        file_path = file_path[1:]
    src = os.path.join(settings.source.posix_path, file_path)
    dst = os.path.join(settings.destination.posix_path, file_path)
    return src, dst


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


def get_agave_dest(dest_path, settings):
    '''Get full agave-canonical URI for destination'''
    return dest_path.replace(settings.destination.posix_path,
                             settings.destination.bucket)


def get_agave_parents(posix_dest_path, posix_base, bucket):
    '''Get list of Agave uri paths including self and parents from POSIX path'''
    # Strip filesystem mount path
    path_list = []
    agave_path = posix_dest_path.replace(posix_base, bucket)
    while agave_path != bucket:
        path_list.append(agave_path)
        agave_path = os.path.dirname(agave_path)
    return path_list
