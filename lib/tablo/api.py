import requests
import json
import discovery

DISCOVERY_URL = 'https://api.tablotv.com/assocserver/getipinfo/'

USER_AGENT = 'Tablo-Kodi/0.1'


class APIError(Exception):
    pass


def requestHandler(f):
    def wrapper(*args, **kwargs):
        r = f(*args, **kwargs)
        if not r.ok:
            raise APIError('{0}: {1}'.format(r.status_code, '/' + r.url.split('://', 1)[-1].split('/', 1)[-1]))
        return r.json()

    return wrapper


class Endpoint(object):
    def __init__(self, segments=None):
        self.device = None
        self.segments = segments or []

    def __getattr__(self, name):
        e = Endpoint(self.segments + [name.strip('_')])
        e.device = self.device
        return e

    def __call__(self, __method='GET', **kwargs):
        if __method.isdigit() or __method.startswith('/'):
            return self.__getattr__(__method.lstrip('/'))

    @requestHandler
    def get(self, **kwargs):
        return requests.get(
            'http://{0}/{1}'.format(self.device.address(), '/'.join(self.segments)),
            headers={'User-Agent': USER_AGENT},
            params=kwargs
        )

    @requestHandler
    def post(self, **kwargs):
        return requests.post(
            'http://{0}/{1}'.format(self.device.address(), '/'.join(self.segments)),
            headers={'User-Agent': USER_AGENT},
            data=json.dumps(kwargs)
        )

    @requestHandler
    def patch(self, **kwargs):
        return requests.post(
            'http://{0}/{1}'.format(self.device.address(), '/'.join(self.segments)),
            headers={'User-Agent': USER_AGENT},
            data=json.dumps(kwargs)
        )

    @requestHandler
    def delete(self, **kwargs):
        return requests.delete(
            'http://{0}/{1}'.format(self.device.address(), '/'.join(self.segments)),
            headers={'User-Agent': USER_AGENT}
        )


class TabloApi(Endpoint):
    def __init__(self):
        Endpoint.__init__(self)
        self.device = None
        self.devices = None

    def discover(self):
        self.devices = discovery.Devices()

    def foundTablos(self):
        return bool(self.devices and self.devices.tablos)

    def selectDevice(self, selection):
        if isinstance(selection, int):
            self.device = self.devices.tablos[selection]
            return

        for d in self.devices.tablos:
            if selection == d.ID:
                self.device = d
                break


API = TabloApi()
