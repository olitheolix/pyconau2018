"""Update load balancer timeout whenever ingresses change

CHANGEME: you *must* change the GCLOUD_PROJECT variable to match you GCloud
project name.
"""
import json
import os

import googleapiclient.discovery
import utils

from os.path import expanduser

# CHANGEME: replace this value with your own!
GCLOUD_PROJECT = 'pyconau2018-oliver'


def main(gcloud_project=GCLOUD_PROJECT):
    # Get a handle to the GCloud backend services. We will use this handle to
    # patch the Load Balance timeout.
    compute = googleapiclient.discovery.build('compute', 'v1')
    gce_bes = compute.backendServices()

    # Load the access credentials (will ignore the kubeconfig file and use the
    # Pods service account if possible).
    conf = utils.load_auto_config(os.getenv('KUBECONFIG'))
    client = utils.setup_requests(conf)

    # Watch the ingresses.
    ret = client.get(
        f'{conf.url}/apis/extensions/v1beta1/ingresses?watch=true',
        stream=True)
    assert ret.status_code == 200, ret

    # Whenever an ingress changes we will extract the load balancer timeout and
    # its backends from the ingress annotation. Then, set the LB timeout.
    print('Starting to watch ingresses')
    for line in ret.iter_lines():
        line = json.loads(line.decode('utf8'))
        event, obj = line['type'], utils.make_dotdict(line['object'])
        print(event, obj['metadata']['namespace'], obj['metadata']['name'])

        # Ignore added/deleted ingresses (a new ingress will be modified
        # several times during startup so we will not miss it).
        if event.lower() != 'modified':
            continue

        # The ingress controller will add the backends to the annotations, but
        # it may not be there initially (again, we *will* eventually receive a
        # MODIFIED request that has them).
        try:
            backends = obj.metadata.annotations['ingress.kubernetes.io/backends']
        except KeyError:
            print('No backends have been configured yet')
            continue

        # Parse the timeout value. Defaults to 30 if the annotation does not exist.
        timeout = obj.metadata.annotations.get(
            'ingress.kubernetes.io/pycon-demo-timeout', 30
        )

        # Convert the timeout value, which is a string at this point, to an integer.
        try:
            timeout = int(timeout)
            assert timeout > 0
        except (ValueError, AssertionError):
            timeout = 30

        # Iterate over the load balancer backends and use the Google API
        # directly to update their timeout values.
        for backend in json.loads(backends):
            print(event, f'Updating timeout for <{backend}> to {timeout}...', end='', flush=True)

            try:
                # Patch the timeout value.
                gce_bes.patch(
                    project=gcloud_project,
                    backendService=backend,
                    body={'timeoutSec': timeout}
                ).execute()
            except googleapiclient.errors.HttpError:
                print('ignored')
                continue
            print('done')


if __name__ == '__main__':
    main()
