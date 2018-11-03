import os
from reactors import agaveutils
from tenacity import retry
from tenacity import stop_after_delay
from tenacity import wait_exponential


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
