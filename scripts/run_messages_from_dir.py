#!/usr/bin/env python

import json
import os
import sys
from agavepy.agave import Agave, AgaveError

jobs_dir = sys.argv[1]
actor = sys.argv[2]
session = os.path.basename(__file__)

ag = Agave.restore()
jobs = os.listdir(sys.argv[1])
for j in jobs:
    with open(os.path.join(jobs_dir, j), 'r') as jsondoc:
        try:
            jsonobj = json.load(jsondoc)
            print(jsonobj)
            resp = ag.actors.sendMessage(
                actorId=actor,
                body={'message': jsonobj},
                environment={'x-session': session})
            # print(resp)
            print(resp.get('executionId', 'Message failed'))
        except Exception as exc:
            raise AgaveError(exc)
