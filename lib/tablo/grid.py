import os
import json
import threading
from peewee import peewee

from lib import tablo

from lib import backgroundthread
from lib import util

import compat

DATABASE_VERSION = 0


class DBManager(object):
    LOCK = threading.Lock()
    DB = None

    def __getattr__(self, name):
        return getattr(DBManager.DB, name)

    def __enter__(self):
        DBManager.LOCK.acquire()
        DBManager.DB.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        DBManager.DB.close()
        DBManager.LOCK.release()


class ChannelTask(backgroundthread.Task):
    def setup(self, path, channel, callback):
        self.path = path
        self.channel = channel
        self.callback = callback

    def run(self):
        data = tablo.API.views.livetv.channels(self.channel['object_id']).get(duration=86400)
        if self.isCanceled():
            return

        util.DEBUG_LOG('Retrieved channel: {0}'.format(self.channel['object_id']))

        self.callback(self.path, data)


class DateTimeFieldTablo(peewee.DateTimeField):
    def python_value(self, value):
        value = peewee.DateTimeField.python_value(self, value)
        return tablo.API.timezone.fromutc(value)


class Grid(object):
    def __init__(self, work_path, update_callback):
        self.Version = None
        self.Channel = None
        self.Airing = None
        self.updateCallback = update_callback
        self._tasks = []
        self.initializeDB(work_path)

    def initializeDB(self, path=None):
        ###########################################################################################
        # Version
        ###########################################################################################
        if not os.path.exists(path):
            os.path.makedirs(path)

        dbPath = os.path.join(path, 'grid.db')
        # dbExists = os.path.exists(dbPath)

        DBManager.DB = peewee.SqliteDatabase(dbPath, threadlocals=True)

        with DBManager() as db:
            class DBVersion(peewee.Model):
                version = peewee.IntegerField(default=0)
                updated = peewee.DateTimeField(null=True)

                class Meta:
                    database = db.DB

            DBVersion.create_table(fail_silently=True)

            self.Version = DBVersion

            # if dbExists:  # Only check version if we had a DB, otherwise we're creating it fresh
            #     checkDBVersion(DB)

            ###########################################################################################
            # Tables
            ###########################################################################################
            class Base(peewee.Model):
                class Meta:
                    database = db.DB

            class Channel(Base):
                ID = peewee.IntegerField(primary_key=True)
                path = peewee.CharField(unique=True, null=True)
                callSign = peewee.CharField(default='')
                network = peewee.CharField(default='')
                major = peewee.IntegerField(default=0)
                minor = peewee.IntegerField(default=0)

            Channel.create_table(fail_silently=True)

            class Airing(Base):
                channel = peewee.ForeignKeyField(Channel, related_name='airings')
                type = peewee.CharField()
                path = peewee.CharField(null=True)
                title = peewee.CharField(null=True)
                background = peewee.CharField(null=True)
                thumbnail = peewee.CharField(null=True)
                seriesTitle = peewee.CharField(null=True)
                episodeNumber = peewee.IntegerField(default=0)
                seasonNumber = peewee.IntegerField(default=0)
                datetime = DateTimeFieldTablo(null=True)
                datetimeEnd = DateTimeFieldTablo(null=True)
                duration = peewee.IntegerField(default=0)
                scheduleState = peewee.CharField(null=True)
                scheduleQualifier = peewee.CharField(null=True)
                scheduleSkipReason = peewee.CharField(null=True)
                _qualifiers = peewee.CharField(null=True)
                _gridAiring = peewee.CharField(null=True)

                def qualifiers(self):
                    return json.loads(self._qualifiers)

                def watch(self):
                    return tablo.api.Watch(self.channel.path)

                @property
                def scheduled(self):
                    return self.scheduleState == 'scheduled'

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
                        self.channel.major,
                        self.channel.minor
                    )

                def secondsToEnd(self, start=None):
                    start = start or tablo.api.now()
                    return compat.timedelta_total_seconds(self.datetimeEnd - start)

                def secondsToStart(self):
                    return compat.timedelta_total_seconds(self.datetime - tablo.api.now())

                def secondsSinceEnd(self):
                    return compat.timedelta_total_seconds(tablo.api.now() - self.datetimeEnd)

                def airingNow(self, ref=None):
                    ref = ref or tablo.api.now()
                    return self.datetime <= ref < self.datetimeEnd

                def ended(self):
                    return self.datetimeEnd < tablo.api.now()

                @property
                def network(self):
                    return self.channel.network

                def schedule(self, on=True):
                    airing = tablo.API(self.path).patch(scheduled=on)
                    self.update(
                        scheduleState=airing['schedule']['state'],
                        scheduleQualifier=airing['schedule']['qualifier'],
                        scheduleSkipReason=airing['schedule']['skip_reason']
                    ).execute()

                @property
                def gridAiring(self):
                    if self._gridAiring:
                        return self.getGridAiring(json.loads(self._gridAiring))
                    else:
                        return self.getGridAiring()

                def getGridAiring(self, data=None):
                    if not data:
                        data = tablo.API(self.path).get()
                        self._gridAiring = json.dumps(data)

                    if 'episode' in data:
                        return tablo.Airing(data, 'episode')
                    elif 'schedule' in data:
                        return tablo.Airing(data, 'schedule')
                    elif 'event' in data:
                        return tablo.Airing(data, 'event')
                    elif 'airing' in data:
                        return tablo.Airing(data, 'airing')

            Airing.create_table(fail_silently=True)

            self.Channel = Channel
            self.Airing = Airing

    def checkDBVersion(self):
        v = self.Version.get_or_create(id=1)[0]
        if v.version < DATABASE_VERSION:
            # if migrateDB(self.DB, v.version):
            #     v.update(version=DATABASE_VERSION).execute()
            pass

        return v.updated

    def markUpdated(self):
        v = self.Version.get_or_create(id=1)[0]
        v.update(updated=tablo.api.now()).execute()

    def getChannelData(self, path, channel):
        t = ChannelTask()
        self._tasks.append(t)
        t.setup(path, channel, self.channelDataCallback)

        backgroundthread.BGThreader.addTask(t)

    def channelDataCallback(self, path, data):
        with DBManager() as db:
            with db.transaction():
                for airing in data:
                    self.addAiring(airing, channelPath=path)

            self.updateCallback(self.Channel.get(path=path))

    def cancelTasks(self):
        if not self._tasks:
            return

        util.DEBUG_LOG('Canceling {0} tasks (GRID)'.format(len(self._tasks)))
        for t in self._tasks:
            t.cancel()
        self._tasks = []

    def addChannel(self, ID, path, call_sign, major, minor, network):
        with DBManager.DB.transaction():
            return self.Channel.get_or_create(
                ID=ID,
                path=path,
                callSign=call_sign,
                major=major,
                minor=minor,
                network=network
            )[0]

    def addAiring(self, data, channel=None, channelPath=None):
        channel = channel or self.Channel.get(path=channelPath)

        if 'series' in data:
            cat = 'series'
        elif 'movie' in data:
            cat = 'movie'
        elif 'sport' in data:
            cat = 'sport'
        elif 'program' in data:
            cat = 'program'

        catData = data[cat]

        background = catData.get('background_image') and tablo.API.images(catData['background_image']['image_id']) or ''
        thumbnail = catData.get('thumbnail_image') and tablo.API.images(catData['thumbnail_image']['image_id']) or ''

        duration = data['airing_details']['duration']
        datetime = compat.datetime.datetime.strptime(data['airing_details'].get('datetime').rsplit('Z', 1)[0], '%Y-%m-%dT%H:%M')
        datetimeEnd = datetime + tablo.api.compat.datetime.timedelta(seconds=duration)

        self.Airing.create(
            channel=channel,
            type=cat,
            path=data['path'],
            title=catData.get('title', ''),
            background=background,
            thumbnail=thumbnail,
            seriesTitle=catData.get('series_title', ''),
            episodeNumber=data.get('episode_number', 0),
            seasonNumber=data.get('season_number', 0),
            datetime=datetime,
            duration=duration,
            datetimeEnd=datetimeEnd,
            scheduleState=data['schedule']['state'],
            scheduleQualifier=data['schedule']['qualifier'],
            scheduleSkipReason=data['schedule']['skip_reason'],
            _qualifiers=data.get('qualifiers', '')
        )

    def getChannels(self, paths=None):
        with DBManager():
            updated = self.checkDBVersion()
            if updated:
                self.triggerUpdates()
                return

            self.markUpdated()

            paths = paths or tablo.API.guide.channels.get()
            channels = tablo.API.batch.post(paths)
            for path in paths:
                channelData = channels[path]['channel']
                self.addChannel(
                    ID=channels[path]['object_id'],
                    path=path,
                    call_sign=channelData.get('call_sign') or '',
                    major=channelData.get('major', 0),
                    minor=channelData.get('minor', 0),
                    network=channelData.get('network') or ''
                )
                self.getChannelData(path, channels[path])

    def triggerUpdates(self):
        for c in self.Channel.select():
            self.updateCallback(c)

    def airings(self, start, cutoff, channel_path=None, channel=None):
        channel = channel or self.Channel.get(path=channel_path)
        return channel.airings.select().where(
            (self.Airing.datetimeEnd > start.astimezone(tablo.api.pytz.utc)) &
            (self.Airing.datetime < cutoff.astimezone(tablo.api.pytz.utc))
        )

    def getAiring(self, path):
        return self.Airing.get(path=path)
