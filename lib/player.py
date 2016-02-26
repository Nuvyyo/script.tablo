import xbmc
import xbmcgui
import threading
# import os

from lib import util


class TabloPlayer(xbmc.Player):
    def init(self):
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
        li = xbmcgui.ListItem(title, title, thumbnailImage=thumb, path=watch.url)
        li.setInfo('video', {'title': title, 'tvshowtitle': title})
        # li.setInfo('video', {'duration': str(rec.duration / 60), 'title': rec.episodeTitle, 'tvshowtitle': rec.seriesTitle})
        # li.addStreamInfo('video', {'duration': rec.duration})
        li.setIconImage(thumb)
        if rec.position and resume:
            util.DEBUG_LOG('Player: Resuming at {0}'.format(rec.position))
            # pl = os.path.join(util.PROFILE, 'pl.m3u8')
            self.startPosition = rec.position
            # with open(pl, 'w') as f:
            #     f.write(watch.makeSeekPlaylist(rec.position))
            # self.play(pl, li, False, 0)
        else:
            util.DEBUG_LOG('Player: Playing from beginning')

        self.play(watch.url, li, False, 0)

        return None

    def wait(self):
        threading.Thread(target=self._wait).start()

    def _wait(self):
        self._waiting.clear()
        try:
            while self.isPlayingVideo() and not xbmc.abortRequested:
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
                # self.airing.setPosition(self.startPosition + self.position)
                self.airing.setPosition(self.position)

            if self.isPlayingVideo():
                util.DEBUG_LOG('Player: Stopping video')
                self.stop()

            util.DEBUG_LOG('Player: Played for {0} seconds'.format(self.position))
        finally:
            self._waiting.set()

    def onPlayBackStarted(self):
        if self.startPosition:
            self.seekTime(self.startPosition)
        self.wait()

    def stopAndWait(self):
        if self.isPlayingVideo():
            self.stop()
            self._waiting.wait()


PLAYER = TabloPlayer().init()
