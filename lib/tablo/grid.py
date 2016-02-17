import os
import json
from peewee import peewee

from lib import tablo

from lib import backgroundthread
from lib import util


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


class Grid(object):
    DB = None

    def __init__(self, work_path):
        self.DB = None
        self.Channel = None
        self.Airing = None
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

        self.DB = peewee.SqliteDatabase(dbPath)

        self.DB.connect()

        class DBVersion(peewee.Model):
            version = peewee.IntegerField(default=0)
            updated = peewee.DateTimeField(null=True)

            class Meta:
                database = self.DB

        DBVersion.create_table(fail_silently=True)

        # if dbExists:  # Only check version if we had a DB, otherwise we're creating it fresh
        #     checkDBVersion(DB)

        ###########################################################################################
        # Tables
        ###########################################################################################
        class Base(peewee.Model):
            class Meta:
                database = self.DB

        class Channel(Base):
            CID = peewee.IntegerField(unique=True)
            path = peewee.CharField(unique=True, null=True)
            callSign = peewee.CharField(default='')
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
            datetime = peewee.DateTimeField(null=True)
            duration = peewee.IntegerField(default=0)
            _qualifiers = peewee.CharField(null=True)

            def qualifiers(self):
                return json.loads(self._qualifiers)

        Airing.create_table(fail_silently=True)

        self.Channel = Channel
        self.Airing = Airing

        self.DB.close()

    def getChannelData(self, path, channel):
        t = ChannelTask()
        self._tasks.append(t)
        t.setup(path, channel, self.channelDataCallback)

        backgroundthread.BGThreader.addTask(t)

    def channelDataCallback(self, path, data):
        for airing in data:
            self.addAiring(airing, channelPath=path)

    def cancelTasks(self):
        if not self._tasks:
            return

        util.DEBUG_LOG('Canceling {0} tasks (GRID)'.format(len(self._tasks)))
        for t in self._tasks:
            t.cancel()
        self._tasks = []

    def addChannel(self, ID, path, call_sign, major, minor):
        with self.DB.transaction():
            return self.Channel.get_or_create(
                CID=ID,
                path=path,
                callSign=call_sign,
                major=major,
                minor=minor
            )

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

        with self.DB.transaction():
            self.Airing.create(
                channel=channel,
                type=cat,
                path=data['path'],
                title=data.get('title', ''),
                background=background,
                thumbnail=thumbnail,
                seriesTitle=catData.get('series_title', ''),
                episodeNumber=data.get('episode_number', 0),
                seasonNumber=data.get('season_number', 0),
                datetime=data['airing_details']['datetime'],
                duration=data['airing_details']['duration'],
                _qualifiers=data.get('qualifiers', '')
            )

    def getChannels(self, paths=None):
        print paths
        paths = paths or tablo.API.guide.channels.get()
        channels = tablo.API.batch.post(paths)
        for path in paths:
            channelData = channels[path]['channel']
            self.addChannel(
                ID=channels[path]['object_id'],
                path=path,
                call_sign=channelData.get('call_sign', ''),
                major=channelData.get('major', 0),
                minor=channelData.get('minor', 0)
            )
            self.getChannelData(path, channels[path])
