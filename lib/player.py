import xbmc
import xbmcgui
import threading
import copy
import os
import urllib

from lib import util
from lib.tablo import bif
from lib.windows import kodigui


class TrickModeWindow(kodigui.BaseWindow):
    name = 'TRICKMODE'
    xmlFile = 'script-tablo-trick-mode.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    IMAGE_LIST_ID = 100

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        self.url = kwargs.get('url')
        self.callback = kwargs.get('callback')
        self.select = None

        self.trickPath = os.path.join(util.PROFILE, 'trick')
        if not os.path.exists(self.trickPath):
            os.makedirs(self.trickPath)

        self.getBif()

    def onFirstInit(self):
        self.imageList = kodigui.ManagedControlList(self, self.IMAGE_LIST_ID, 4)
        if not self.url:
            return

        self.fillImageList()

    def onClick(self, controlID):
        if controlID != self.IMAGE_LIST_ID:
            return

        item = self.imageList.getSelectedItem()
        if not item:
            return

        frame = item.dataSource
        self.callback(frame['timestamp'])

    def onFocus(self, controlID):
        if self.select is not None:
            self.imageList.selectItem(self.select)
            self.select = None

    def setPosition(self, position):
        if not self.url:
            return

        i = -1
        print position
        for i, frame in enumerate(self.bif.frames):
            print frame['timestamp']
            if position > frame['timestamp']:
                continue
            break
        i -= 1

        print i
        if i >= 0:
            self.select = i

    def cleanTrickPath(self):
        for f in os.listdir(self.trickPath):
            os.remove(os.path.join(self.trickPath, f))

    def getBif(self):
        if not self.url:
            return

        self.cleanTrickPath()
        bifPath = os.path.join(self.trickPath, 'bif')
        urllib.urlretrieve(self.url, bifPath)
        self.bif = bif.Bif(bifPath)
        self.bif.dumpImages(self.trickPath)

    def fillImageList(self):
        items = []
        for i in range(self.bif.size):
            print os.path.join(self.trickPath, str(i) + '.jpg')
            item = kodigui.ManagedListItem(
                str(self.bif.frames[i]['timestamp']),
                thumbnailImage=os.path.join(self.trickPath, str(i) + '.jpg'),
                data_source=self.bif.frames[i]
            )
            items.append(item)

        self.imageList.addItems(items)


class TabloPlayer(xbmc.Player):
    def init(self):
        self.playListFilename = os.path.join(util.PROFILE, 'pl.m3u8')
        self.reset()
        return self

    def reset(self):
        self._waiting = threading.Event()
        self._waiting.set()
        self.airing = None
        self.watch = None
        self.startPosition = 0
        self.position = 0
        self.isPlayingRecording = False
        self.seeking = False
        self.playList = None
        self.segments = None
        self.trickWindow = None
        self.hasBif = False
        self.item = None

    @property
    def absolutePosition(self):
        return self.startPosition + self.position

    def makeSeekedPlaylist(self, position):
        print len(self.segments)
        print position
        m = self.playList
        m.segments = copy.copy(self.segments)
        if position > 0:
            duration = m.segments[0].duration
            while duration < position:
                del m.segments[0]
                if not m.segments:
                    break
                duration += m.segments[0].duration

        print len(m.segments)
        m.dump(self.playListFilename)

    def setupTrickMode(self, watch):
        if watch.bifHD:
            self.hasBif = True
        self.trickWindow = TrickModeWindow.create(url=watch.bifHD, callback=self.playAtPosition)

    def playAiringChannel(self, airing):
        self.reset()
        self.airing = airing
        watch = airing.watch()
        if watch.error:
            return watch.error

        self.watch = watch
        title = airing.title
        thumb = airing.thumb
        li = xbmcgui.ListItem(title, title, thumbnailImage=thumb, path=watch.url)
        li.setInfo('video', {'title': title, 'tvshowtitle': title})
        li.setIconImage(thumb)
        util.DEBUG_LOG('Player: Playing channel')
        self.play(watch.url, li, False, 0)

        return None

    def playRecording(self, rec, show=None, resume=True):
        self.reset()
        self.isPlayingRecording = True
        self.airing = rec
        watch = rec.watch()
        if watch.error:
            return watch.error

        self.watch = watch
        title = rec.title or (show and show.title or '')
        thumb = show and show.thumb or ''
        self.item = xbmcgui.ListItem(title, title, thumbnailImage=thumb, path=watch.url)
        self.item.setInfo('video', {'title': title, 'tvshowtitle': title})
        # li.setInfo('video', {'duration': str(rec.duration / 60), 'title': rec.episodeTitle, 'tvshowtitle': rec.seriesTitle})
        # li.addStreamInfo('video', {'duration': rec.duration})
        self.item.setIconImage(thumb)

        self.playList = watch.getSegmentedPlaylist()
        self.segments = copy.copy(self.playList.segments)

        self.setupTrickMode(watch)

        if rec.position and resume:
            util.DEBUG_LOG('Player: Resuming at {0}'.format(rec.position))
            self.playAtPosition(rec.position)
        else:
            util.DEBUG_LOG('Player: Playing from beginning')
            self.playAtPosition(0)
            # self.play(watch.url, li, False, 0)

        return None

    def playAtPosition(self, position):
        self.seeking = False
        self.startPosition = position
        self.position = 0
        self.makeSeekedPlaylist(position)
        self.play(self.playListFilename, self.item, False, 0)

    def wait(self):
        threading.Thread(target=self._wait).start()

    def _wait(self):
        self._waiting.clear()
        try:
            while self.isPlayingVideo() and not xbmc.abortRequested:
                if xbmc.getCondVisibility('Player.Seeking'):
                    self.onPlayBackSeek(self.position, 0)
                else:
                    self.position = self.getTime()
                xbmc.sleep(100)

                if xbmc.getCondVisibility('Player.Caching') and self.position < 1:
                    util.DEBUG_LOG('Player: Forcing resume at {0}'.format(self.position))
                    self.pause()

                if not xbmc.getCondVisibility('VideoPlayer.IsFullscreen'):
                    util.DEBUG_LOG('Player: Video closed')
                    break

            if self.position and self.isPlayingRecording:
                util.DEBUG_LOG('Player: Saving position')
                self.airing.setPosition(self.absolutePosition)
                # self.airing.setPosition(self.position)

            if not self.seeking:
                if self.isPlayingVideo():
                    util.DEBUG_LOG('Player: Stopping video')
                    self.stop()

                util.DEBUG_LOG('Player: Played for {0} seconds'.format(self.position))
                self.finish()
        finally:
            self._waiting.set()

    def onPlayBackStarted(self):
        self.wait()

    def onPlayBackSeek(self, time, offset):
        if self.hasBif:
            self.seeking = True
            self.trickWindow.setPosition(self.absolutePosition)
            self.stop()

    def stopAndWait(self):
        if self.isPlayingVideo():
            self.stop()
            self._waiting.wait()

    def finish(self):
        self.trickWindow.doClose()
        del self.trickWindow
        self.trickWindow = None


PLAYER = TabloPlayer().init()
