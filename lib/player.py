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

    PROGRESS_IMAGE_ID = 200
    PROGRESS_SELECT_IMAGE_ID = 201
    PROGRESS_WIDTH = 880
    PROGRESS_SELECT_IMAGE_X = 199
    PROGRESS_SELECT_IMAGE_Y = -50

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        self.url = kwargs.get('url')
        self.callback = kwargs.get('callback')
        self.playlist = kwargs.get('playlist')
        self.select = None
        self.maxTimestamp = 0

        self.trickPath = os.path.join(util.PROFILE, 'trick')
        if not os.path.exists(self.trickPath):
            os.makedirs(self.trickPath)

        self.getBif()

    def onFirstInit(self):
        self.imageList = kodigui.ManagedControlList(self, self.IMAGE_LIST_ID, 4)
        self.progressImage = self.getControl(self.PROGRESS_IMAGE_ID)
        self.progressSelectImage = self.getControl(self.PROGRESS_SELECT_IMAGE_ID)

        self.fillImageList()

        self.setProperty('end', util.durationToShortText(self.maxTimestamp))

    def onAction(self, action):
        try:
            self.updateProgressSelection()

            if action == xbmcgui.ACTION_STOP:
                self.doClose()
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def onClick(self, controlID):
        if controlID != self.IMAGE_LIST_ID:
            return

        item = self.imageList.getSelectedItem()
        if not item:
            return

        if self.bif:
            timestamp = item.dataSource['timestamp']
        else:
            timestamp = float(item.getProperty('timestamp'))

        self.setProgress(timestamp)
        self.callback(timestamp)

    def onFocus(self, controlID):
        if self.select is not None:
            self.imageList.selectItem(self.select)
            self.select = None

    def blank(self):
        self.setProperty('show', '')

    def unBlank(self):
        self.setProperty('show', '1')

    def setPosition(self, position):
        position = min(position, self.maxTimestamp)

        self.setProperty('current', util.durationToShortText(position))

        util.DEBUG_LOG('TrickMode: Setting position at {0} of {1}'.format(position, self.maxTimestamp))

        if not (self.maxTimestamp):
            return

        self.setProgress(position)
        self.setProgressSelect(position)

        if self.bif:
            i = -1
            for i, frame in enumerate(self.bif.frames):
                if position > frame['timestamp']:
                    continue
                break
            i -= 1

            if i >= 0:
                self.select = i
        else:
            timestamp = 0
            for i, segment in enumerate(self.playlist.segments):
                timestamp += segment.duration
                if timestamp > position:
                    self.select = i
                    break
            else:
                self.select = 0

    def setProgress(self, position):
        if not self.started:
            return
        w = int((position / float(self.maxTimestamp)) * self.PROGRESS_WIDTH) or 1
        self.progressImage.setWidth(w)

    def setProgressSelect(self, position):
        if not self.started:
            return

        x = self.PROGRESS_SELECT_IMAGE_X + int((position / float(self.maxTimestamp)) * self.PROGRESS_WIDTH)
        self.progressSelectImage.setPosition(x, self.PROGRESS_SELECT_IMAGE_Y)

        self.setProperty('select', util.durationToShortText(position))

    def updateProgressSelection(self):
        item = self.imageList.getSelectedItem()
        if not item:
            return

        self.setProgressSelect(float(item.getProperty('timestamp')))

    def cleanTrickPath(self):
        for f in os.listdir(self.trickPath):
            os.remove(os.path.join(self.trickPath, f))

    def getBif(self):
        self.bif = None
        if not self.url:
            return

        self.cleanTrickPath()
        bifPath = os.path.join(self.trickPath, 'bif')
        urllib.urlretrieve(self.url, bifPath)
        self.bif = bif.Bif(bifPath)
        self.bif.dumpImages(self.trickPath)
        self.maxTimestamp = self.bif.maxTimestamp
        util.DEBUG_LOG('TrickMode: Bif frames ({0}) - max timestamp ({1})'.format(self.bif.size, self.bif.maxTimestamp))

    def fillImageList(self):
        items = []

        if self.bif:
            for i in range(self.bif.size):
                timestamp = self.bif.frames[i]['timestamp']
                item = kodigui.ManagedListItem(
                    str(timestamp),
                    thumbnailImage=os.path.join(self.trickPath, str(i) + '.jpg'),
                    data_source=self.bif.frames[i]
                )
                item.setProperty('timestamp', str(timestamp))
                items.append(item)
        else:
            timestamp = 0
            for segment in self.playlist.segments:
                item = kodigui.ManagedListItem(
                    str(timestamp),
                    thumbnailImage='',
                    data_source=segment
                )
                item.setProperty('timestamp', str(timestamp))
                self.maxTimestamp = timestamp
                timestamp += segment.duration
                items.append(item)

        self.imageList.addItems(items)


class ThreadedWatch(object):
    def __init__(self, airing, dialog):
        self.dialog = dialog
        self.airing = airing
        self.watch = None
        self.thread = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def start(self):
        self.thread = threading.Thread(target=self.watchThread)
        self.thread.start()
        return self

    def watchThread(self):
        util.DEBUG_LOG('ThreadedWatch: Started')
        self.watch = self.airing.watch()
        util.DEBUG_LOG('ThreadedWatch: Finished')

    def getWatch(self):
        util.DEBUG_LOG('ThreadedWatch: getWatch - Started')
        while self.thread.isAlive() and not self.dialog.canceled:
            self.thread.join(0.1)
        util.DEBUG_LOG('ThreadedWatch: getWatch - Finished')
        return self.watch


class TabloPlayer(xbmc.Player):
    def init(self):
        self.playlistFilename = os.path.join(util.PROFILE, 'pl.m3u8')
        self.loadingDialog = None
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
        self.playlist = None
        self.segments = None
        self.trickWindow = None
        self.item = None
        self.hasFullScreened = False

        self.closeLoadingDialog()

    @property
    def absolutePosition(self):
        return self.startPosition + self.position

    def makeSeekedPlaylist(self, position):
        m = self.playlist
        m.segments = copy.copy(self.segments)
        if position > 0:
            duration = m.segments[0].duration
            while duration < position:
                del m.segments[0]
                if not m.segments:
                    break
                duration += m.segments[0].duration

        m.dump(self.playlistFilename)

    def setupTrickMode(self, watch):
        self.trickWindow = TrickModeWindow.create(url=watch.bifHD, callback=self.playAtPosition, playlist=self.playlist)

    def playAiringChannel(self, airing):
        self.reset()
        self.airing = airing

        self.loadingDialog = util.LoadingDialog().show()

        threading.Thread(target=self._playAiringChannel).start()

    def _playAiringChannel(self):
        airing = self.airing

        with ThreadedWatch(airing, self.loadingDialog) as tw:
            watch = tw.getWatch()
            if watch:
                if watch.error:
                    util.DEBUG_LOG('Player (LiveTV): Watch error: {0}'.format(watch.error))
                    xbmcgui.Dialog().ok('Failed', 'Failed to play channel:', ' ', str(watch.error))
                    self.closeLoadingDialog()
                    return watch.error
                util.DEBUG_LOG('Player (LiveTV): Watch URL: {0}'.format(watch.url))
            else:
                util.DEBUG_LOG('Player (LiveTV): Canceled before start')
                self.closeLoadingDialog()
                return

        self.watch = watch
        title = '{0} {1}'.format(airing.displayChannel(), airing.network)
        thumb = airing.thumb
        li = xbmcgui.ListItem(title, title, thumbnailImage=thumb, path=watch.url)
        li.setInfo('video', {'title': title, 'tvshowtitle': title})
        li.setIconImage(thumb)

        util.DEBUG_LOG('Player (LiveTV): Playing channel')

        self.play(watch.url, li, False, 0)
        self.loadingDialog.wait()

        return None

    def playRecording(self, rec, show=None, resume=True):
        self.reset()
        self.isPlayingRecording = True
        self.airing = rec
        watch = rec.watch()
        if watch.error:
            return watch.error

        self.watch = watch
        title = rec.title or (show and show.title or '{0} {1}'.format(rec.displayChannel(), rec.network))
        thumb = show and show.thumb or ''
        self.item = xbmcgui.ListItem(title, title, thumbnailImage=thumb, path=watch.url)
        self.item.setInfo('video', {'title': title, 'tvshowtitle': title})
        # li.setInfo('video', {'duration': str(rec.duration / 60), 'title': rec.episodeTitle, 'tvshowtitle': rec.seriesTitle})
        # li.addStreamInfo('video', {'duration': rec.duration})
        self.item.setIconImage(thumb)

        self.playlist = watch.getSegmentedPlaylist()
        self.segments = copy.copy(self.playlist.segments)

        self.setupTrickMode(watch)

        if rec.position and resume:
            util.DEBUG_LOG('Player (Recording): Resuming at {0}'.format(rec.position))
            self.playAtPosition(rec.position)
        else:
            util.DEBUG_LOG('Player (Recording): Playing from beginning')
            self.playAtPosition(0)
            # self.play(watch.url, li, False, 0)

        return None

    def closeLoadingDialog(self):
        if self.loadingDialog:
            self.loadingDialog.close()
        self.loadingDialog = None

    def playAtPosition(self, position):
        self.seeking = False
        self.startPosition = position
        self.position = 0
        self.makeSeekedPlaylist(position)
        self.trickWindow.setPosition(self.absolutePosition)
        self.play(self.playlistFilename, self.item, False, 0)

    def wait(self):
        if self.isPlayingRecording:
            threading.Thread(target=self._waitRecording).start()
        else:
            threading.Thread(target=self._waitLiveTV).start()

    def _waitRecording(self):
        self._waiting.clear()
        try:
            while self.isPlayingVideo() and not xbmc.abortRequested:
                if xbmc.getCondVisibility('Player.Seeking'):
                    self.onPlayBackSeek(self.position, 0)
                else:
                    self.position = self.getTime()
                xbmc.sleep(100)

                if xbmc.getCondVisibility('Player.Caching') and self.position - self.startPosition < 10:
                    if not xbmc.getCondVisibility('IntegerGreaterThan(Player.CacheLevel,10)'):
                        xbmc.sleep(100)
                        if xbmc.getCondVisibility('Player.Caching'):
                            util.DEBUG_LOG(
                                'Player (Recording): Forcing resume at {0} - cache level: {1}'.format(self.position, xbmc.getInfoLabel('Player.CacheLevel'))
                            )
                            self.pause()

                if xbmc.getCondVisibility('VideoPlayer.IsFullscreen'):
                    self.hasFullScreened = True
                elif self.hasFullScreened:
                    util.DEBUG_LOG('Player (LiveTV): Video closed')
                    break

            if self.position and self.isPlayingRecording:
                util.DEBUG_LOG('Player (Recording): Saving position')
                self.airing.setPosition(self.absolutePosition)
                # self.airing.setPosition(self.position)

            if not self.seeking:
                if self.isPlayingVideo():
                    util.DEBUG_LOG('Player (Recording): Stopping video')
                    self.stop()

                util.DEBUG_LOG('Player (Recording): Played for {0} seconds'.format(self.position))
                self.finish()
        finally:
            self._waiting.set()

    def _waitLiveTV(self):
        self._waiting.clear()
        try:
            while self.isPlayingVideo() and not xbmc.abortRequested:
                xbmc.sleep(100)

                if xbmc.getCondVisibility('VideoPlayer.IsFullscreen'):
                    self.hasFullScreened = True
                elif self.hasFullScreened:
                    util.DEBUG_LOG('Player (LiveTV): Video closed')
                    break

            if self.isPlayingVideo():
                util.DEBUG_LOG('Player (LiveTV): Stopping video')
                self.stop()

            util.DEBUG_LOG('Player (LiveTV): Played for {0} seconds'.format(self.position))
        finally:
            self._waiting.set()

    def onPlayBackStarted(self):
        self.closeLoadingDialog()

        if self.isPlayingRecording:
            self.trickWindow.setPosition(self.absolutePosition)
            self.trickWindow.blank()

        self.wait()

    def onPlayBackStopped(self):
        self.closeLoadingDialog()

    def onPlayBackEnded(self):
        self.closeLoadingDialog()

    def onPlayBackSeek(self, time, offset):
        if not self.isPlayingRecording:
            return

        self.seeking = True
        self.trickWindow.setPosition(self.absolutePosition)
        self.trickWindow.unBlank()
        self.stop()
        util.DEBUG_LOG('Player (Recording): Seek started at {0} (absolute: {1})'.format(self.position, self.absolutePosition))

    def stopAndWait(self):
        if self.isPlayingVideo():
            self.stop()
            self._waiting.wait()

    def finish(self):
        if not self.isPlayingRecording:
            return

        self.trickWindow.doClose()
        del self.trickWindow
        self.trickWindow = None


PLAYER = TabloPlayer().init()
