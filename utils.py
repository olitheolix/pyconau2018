import base64
import os
import ssl
import tempfile
import warnings
from collections import namedtuple

import aiohttp
import google.auth.transport.requests
import requests
import yaml

Config = namedtuple('Config', 'url token ca_cert client_cert')
ClientCert = namedtuple('ClientCert', 'crt key')

# Location of service account tokens inside a Pod.
FNAME_TOKEN = "/var/run/secrets/kubernetes.io/serviceaccount/token"
FNAME_CERT = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


def load_incluster_config(fname_token=FNAME_TOKEN, fname_cert=FNAME_CERT):
    """Return K8s access config from Pod service account.

    Returns None if we are not running in a Pod.

    Inputs:
        kubconfig: str
            Name of kubeconfig file.
    Returns:
        Config

    """
    # Every K8s pod has this.
    server_ip = os.getenv('KUBERNETES_PORT_443_TCP_ADDR', None)

    # Sanity checks: URL and service account files must exist or we are not
    # inside a Pod.
    try:
        assert server_ip is not None
        assert os.path.exists(fname_token)
        assert os.path.exists(fname_cert)
    except AssertionError:
        return None

    # Return the compiled service account configuration.
    try:
        conf = Config(
            url=f'https://{server_ip}',
            token=open(fname_token, 'r').read(),
            ca_cert=fname_cert,
            client_cert=None,
        )
        return conf
    except FileNotFoundError:
        return None


def load_gke_config(kubeconfig, disable_warnings=False):
    """Return K8s access config for GKE cluster described in `kubeconfig`.

    Returns None if `kubeconfig` does not exist or could not be parsed.

    Inputs:
        kubconfig: str
            Name of kubeconfig file.
    Returns:
        Config

    """
    # Load `kubeconfig`. For this proof-of-concept we assume it contains
    # exactly one cluster and user.
    try:
        kubeconf = yaml.load(open(kubeconfig))
    except FileNotFoundError:
        return None
    assert len(kubeconf['clusters']) == 1
    assert len(kubeconf['users']) == 1

    # Unpack the user and cluster info.
    cluster = kubeconf['clusters'][0]['cluster']
    user = kubeconf['users'][0]

    # Return immediately if this does not look like a config file for GKE.
    try:
        assert user['user']['auth-provider']['name'] == 'gcp'
    except (AssertionError, KeyError):
        return None

    # Unpack the self signed certificate (Google does not register the K8s API
    # server certificate with a public CA).
    ssl_ca_cert_data = base64.b64decode(cluster['certificate-authority-data'])

    # Save the certificate to a temporary file. This is only necessary because
    # the requests library needs a path to the CA file - unfortunately, we
    # cannot just pass it the content.
    _, ssl_ca_cert = tempfile.mkstemp(text=False)
    with open(ssl_ca_cert, 'wb') as fd:
        fd.write(ssl_ca_cert_data)

    # Authenticate with Compute Engine using the default project.
    with warnings.catch_warnings(record=disable_warnings):
        cred, project_id = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        cred.refresh(google.auth.transport.requests.Request())

    # Return the config data.
    return Config(
        url=cluster['server'],
        token=cred.token,
        ca_cert=ssl_ca_cert,
        client_cert=None,
    )


def load_minikube_config(kubeconfig):
    # Load `kubeconfig`. For this proof-of-concept we assume it contains
    # exactly one cluster and user.
    kubeconf = yaml.load(open(kubeconfig))
    assert len(kubeconf['clusters']) == 1
    assert len(kubeconf['users']) == 1

    # Unpack the user and cluster info.
    cluster = kubeconf['clusters'][0]
    user = kubeconf['users'][0]

    # Do not proceed if this does not look like a Minikube cluster.
    # Return immediately if this does not look like a config file for GKE.
    try:
        assert cluster['name'] == 'minikube'
    except (AssertionError, KeyError):
        return None

    # Minikube uses client certificates to authenticate. We need to pass those
    # to the HTTP client of our choice when we create the session.
    client_cert = ClientCert(
        crt=user['user']['client-certificate'],
        key=user['user']['client-key'],
    )

    # Return the config data.
    return Config(
        url=cluster['cluster']['server'],
        token=None,
        ca_cert=cluster['cluster']['certificate-authority'],
        client_cert=client_cert,
    )


def load_auto_config(kubeconfig):
    # Try the POD service account (returns None if we are not in pod).
    conf = load_incluster_config()
    if conf is not None:
        return conf

    # Load minikube configuration from kubeconfig file.
    conf = load_minikube_config(kubeconfig)
    if conf is not None:
        return conf

    # Load GKE configuration from kubeconfig file. Will also get us a new
    # bearer token from GCloud. The `disable_warnings` is set to True to avoid
    # harmless warnings during the live presentation.
    conf = load_gke_config(kubeconfig, disable_warnings=True)
    if conf is not None:
        return conf

    return None


def setup_requests(config: Config):
    # Configure a 'requests' session with the correct CA and pre-load the
    # Bearer token.
    sess = requests.Session()
    sess.verify = config.ca_cert

    if config.token is not None:
        sess.headers = {'authorization': f'Bearer {config.token}'}
    if config.client_cert is not None:
        sess.cert = (config.client_cert.crt, config.client_cert.key)
    return sess


def setup_aiohttp(config: Config):
    ssl_context = ssl.create_default_context(cafile=config.ca_cert)
    if config.client_cert is not None:
        ssl_context.load_cert_chain(
            certfile=config.client_cert.crt,
            keyfile=config.client_cert.key
        )

    sess = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl_context=ssl_context),
        headers={'authorization': f'Bearer {config.token}'},
    )
    return sess


class DotDict(dict):
    def __getattr__(self, key):
        return self[key]


def make_dotdict(data):
    if not isinstance(data, (list, tuple, dict)):
        return data

    # Recursively convert all elements in lists and dicts.
    if isinstance(data, (list, tuple)):
        return [make_dotdict(_) for _ in data]
    else:
        return DotDict({k: make_dotdict(v) for k, v in data.items()})
