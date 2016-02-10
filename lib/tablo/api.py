import requests
import urlparse
import compat
import pytz
import traceback
import json
import discovery

DISCOVERY_URL = 'https://api.tablotv.com/assocserver/getipinfo/'

USER_AGENT = 'Tablo-Kodi/0.1'


class APIError(Exception):
    pass


def now():
    return compat.datetime.datetime.now(API.timezone)


def requestHandler(f):
    def wrapper(*args, **kwargs):
        r = f(*args, **kwargs)
        if not r.ok:
            raise APIError('{0}: {1}'.format(r.status_code, '/' + r.url.split('://', 1)[-1].split('/', 1)[-1]))
        return r.json()

    return wrapper


def processDate(date):
        if not date:
            return None

        try:
            return API.timezone.fromutc(compat.datetime.datetime.strptime(date.rsplit('Z', 1)[0], '%Y-%m-%dT%H:%M'))
        except:
            traceback.print_exc()

        return None


class Watch(object):
    def __init__(self, path):
        data = API(path).watch.post(no_fast_startup=True)
        self.url = ''
        self.width = 0
        self.height = 0
        self.sd = data.get('bif_url_sd')
        self.hd = data.get('bif_url_hd')
        self.expires = data.get('playlist_url')
        self.token = data.get('token')
        if 'video_details' in data:
            self.width = data['video_details']['width']
            self.height = data['video_details']['height']

        self.getPlaylist(data.get('playlist_url'))

    def getPlaylist(self, url):
        p = urlparse.urlparse(url)
        fromPL = requests.get(url).text.strip().splitlines()[-1]
        self.url = '{0}://{1}{2}'.format(p.scheme, p.netloc, fromPL)


class Airing(object):
    def __init__(self, data, type_):
        self.path = data.get('path')
        self.scheduleData = data.get('schedule')
        self.data = data
        self.type = type_
        self._datetime = False
        self._datetimeEnd = None

    def __getattr__(self, name):
        return self.data[self.type].get(name)

    def watch(self):
        return Watch(self.data['airing_details']['channel']['path'])

    @property
    def scheduled(self):
        return self.scheduleData['state'] == 'scheduled'

    @property
    def datetime(self):
        if self._datetime is False:
            self._datetime = processDate(self.data['airing_details'].get('datetime'))

        return self._datetime

    @property
    def datetimeEnd(self):
        if self._datetimeEnd is None:
            if self.datetime:
                self._datetimeEnd = self.datetime + compat.datetime.timedelta(seconds=self.data['airing_details']['duration'])
            else:
                self._datetimeEnd = 0

        return self._datetimeEnd

    def displayTimeStart(self):
        if not self.datetime:
            return ''

        return self.datetime.strftime('%I:%M %p').lstrip('0')

    def displayTimeEnd(self):
        if not self.datetime:
            return ''

        return self.datetimeEnd.strftime('%I:%M %p').lstrip('0')

    def displayDay(self):
        if not self.datetime:
            return ''

        return self.datetime.strftime('%A, %B {0}').format(self.datetime.day)

    def displayChannel(self):
        return '{0}-{1}'.format(
            self.data['airing_details']['channel']['channel']['major'],
            self.data['airing_details']['channel']['channel']['minor']
        )

    def secondsToStart(self):
        return compat.timedelta_total_seconds(self.datetime - now())

    def secondsSinceEnd(self):
        return compat.timedelta_total_seconds(now() - self.datetimeEnd)

    def airingNow(self):
        return self.datetime <= now() < self.datetimeEnd

    def ended(self):
        return self.datetimeEnd < now()

    @property
    def network(self):
        return self.data['airing_details']['channel']['channel'].get('network') or ''

    def schedule(self, on=True):
        airing = API(self.path).patch(scheduled=on)
        self.scheduleData = airing.get('schedule')


class Show(object):
    type = None

    def __init__(self, data):
        self.data = None
        self._thumb = ''
        self._background = ''
        self.path = data['path']
        self.scheduleRule = data.get('schedule_rule')
        self.showCounts = data.get('show_counts')
        self.processData(data)

    def __getattr__(self, name):
        return self.data.get(name)

    @classmethod
    def newFromData(self, data):
        if 'series' in data:
            return Series(data)
        elif 'movie' in data:
            return Movie(data)
        elif 'sport' in data:
            return Sport(data)
        elif 'program' in data:
            return Program(data)

    def processData(self, data):
        pass

    @property
    def thumb(self):
        if not self._thumb:
            try:
                self._thumb = self.data.get('thumbnail_image') and API.images(self.data['thumbnail_image']['image_id']) or ''
            except:
                print self.data['thumbnail_image']
        return self._thumb

    @property
    def background(self):
        if not self._background:
            self._background = self.data.get('background_image') and API.images(self.data['background_image']['image_id']) or ''
        return self._background

    def schedule(self, rule='none'):
        data = API(self.path).patch(schedule=rule)
        self.scheduleRule = data.get('schedule_rule')


class Series(Show):
    type = 'SERIES'
    airingType = 'episode'

    def processData(self, data):
        self.data = data['series']

    def episodes(self):
        return API(self.path).episodes.get()

    def seasons(self):
        return API(self.path).seasons.get()

    def airings(self):
        return self.episodes()


class Movie(Show):
    type = 'MOVIE'
    airingType = 'schedule'

    def processData(self, data):
        self.data = data['movie']

    def airings(self):
        return API(self.path).airings.get()


class Sport(Show):
    type = 'SPORT'
    airingType = 'event'

    def processData(self, data):
        self.data = data['sport']

    def events(self):
        return API(self.path).events.get()

    def airings(self):
        return self.events()


class Program(Show):
    type = 'PROGRAM'
    airingType = 'airing'

    def processData(self, data):
        self.data = data['program']

    def airings(self):
        return API(self.path).airings.get()


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
    def post(self, *args, **kwargs):
        return requests.post(
            'http://{0}/{1}'.format(self.device.address(), '/'.join(self.segments)),
            headers={'User-Agent': USER_AGENT},
            data=json.dumps(args and args[0] or kwargs)
        )

    @requestHandler
    def patch(self, **kwargs):
        return requests.patch(
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
        self.timezone = None

    def discover(self):
        self.devices = discovery.Devices()

    def getServerInfo(self):
        info = self.server.info.get()
        timezone = info.get('timezone')
        if not timezone:
            self.timezone = pytz.UTC()

        self.timezone = pytz.timezone(timezone)

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

        self.getServerInfo()

    def deviceSelected(self):
        return bool(self.device)

    def images(self, ID):
        return 'http://{0}/images/{1}'.format(self.device.address(), ID)


API = TabloApi()
