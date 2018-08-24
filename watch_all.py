"""Watch several cluster resources with AioHttp."""
import asyncio
import json
import os

import utils


async def watch_resource(config, resource):
    client = utils.setup_aiohttp(config)

    # Make web request.
    ret = await client.get(f'{config.url}/{resource}?watch=true')
    assert ret.status == 200, (ret.status, ret.text)

    # Wait until K8s sends another line (ie another event).
    while True:
        line = await ret.content.readline()
        if len(line) == 0:
            break

        line = json.loads(line.decode('utf8'))
        evt, obj = line['type'], line['object']
        name = obj['metadata'].get('name', '<None>')
        namespace = obj['metadata'].get('namespace', '<Unknown>')
        print(evt, obj['kind'], namespace.upper(), name)
    await client.close()


async def main():
    kubeconf = os.getenv('KUBECONFIG')
    config = utils.load_auto_config(kubeconf)
    assert config is not None

    tasks = [
        watch_resource(config, f'api/v1/namespaces'),
        watch_resource(config, f'api/v1/pods'),
        watch_resource(config, f'api/v1/services'),
        watch_resource(config, f'apis/batch/v1/jobs'),
        watch_resource(config, f'apis/apps/v1/daemonsets'),
        watch_resource(config, f'apis/apps/v1/statefulsets'),
        watch_resource(config, f'apis/extensions/v1beta1/deployments'),
        watch_resource(config, f'apis/extensions/v1beta1/ingresses'),
    ]

    await asyncio.gather(*tasks)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
