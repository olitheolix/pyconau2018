"""Print all cluster name-spaces."""
import asyncio
import os

import utils


async def main():
    kubeconf = os.getenv('KUBECONFIG')
    config = utils.load_auto_config(kubeconf)
    assert config is not None

    #######################################################################
    #                               REQUESTS
    #######################################################################
    print('--- With requests library ---')
    client = utils.setup_requests(config)

    # Make web request.
    ret = client.get(f'{config.url}/api/v1/namespaces?watch=False')
    assert ret.status_code == 200, ret.status_code

    # List the individual name spaces.
    for item in ret.json()['items']:
        print(item['metadata']['name'])

    #######################################################################
    #                                AIOHTTP
    #######################################################################
    print('\n--- With aiohttp library ---')
    client = utils.setup_aiohttp(config)

    # Make web request.
    ret = await client.get(f'{config.url}/api/v1/namespaces?watch=False')
    assert ret.status == 200, (ret.status, ret.text)

    # List the individual name spaces.
    js = await ret.json()
    for item in js['items']:
        print(item['metadata']['name'])
    await client.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
