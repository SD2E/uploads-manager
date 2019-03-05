import os
import re
import shutil
from agavehelpers import resilient_files_pems


def copyfile(r, posix_src, posix_dest, agave_dest=None):
    # Create POSIX directory path at destination
    do_validate = not r.local
    try:
        dest_parent = os.path.dirname(posix_dest)
        os.makedirs(dest_parent, exist_ok=True)
    except Exception as exc:
        r.on_failure('Mkdir {} failed.'.format(dest_parent), exc)

    # Do POSIX copy with forced overwrite
    try:
        shutil.copy(posix_src, posix_dest)
    except Exception as exc:
        r.on_failure('Copy from {} failed.'.format(posix_src), exc)

    if agave_dest is not None:
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

    # # Do Agave permission grants on created parent directories
    # if created_path is not None:
    #     agave_path_list = get_agave_parents(
    #         created_path, r.settings.destination.posix_path,
    #         r.settings.destination.bucket)
    #     r.logger.debug('Do grants for {}'.format(agave_path_list))
    #     if r.local is False:
    #         for ag_uri in agave_path_list:
    #             for grant in r.settings.destination.grants:
    #                 try:
    #                     resilient_files_pems(r.client, ag_uri, grant.username,
    #                                          grant.pem, grant.recursive)
    #                 except Exception:
    #                     r.logger.warning('Grant failed for {}'.format(ag_uri))
