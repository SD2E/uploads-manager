import json
import re
from pprint import pprint


def routemsg(r, agave_dest):
    # Kick off downstream Reactors by filename glob match
    message = {'uri': agave_dest}
    for routename, globs in r.settings.routings.items():
        actor_id = r.settings.linked_reactors.get(routename, {}).get('id')
        for glob in globs:
            if re.compile(glob).search(agave_dest):
                r.logger.debug('Route: dest={}, content={}'.format(actor_id, message))
                try:
                    if r.local is False:
                        resp = r.send_message(actor_id, message=message)
                        if resp is not None:
                            if 'executionId' in resp:
                                r.logger.debug(
                                    'Route: executionId={}, actorId={}'.format(
                                        resp['executionId'], actor_id))
                    else:
                        pprint(message)
                    break
                except Exception as exc:
                    r.on_failure('Route: Failed to launch {}:{} for {}'.format(
                        routename, actor_id, agave_dest), exc)
