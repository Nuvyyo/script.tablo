import xbmc
import xbmcgui
import threading
import kodigui

from lib import util
from lib import tablo

WM = None


class Show:
    type = None

    def __init__(self, data):
        self.data = None
        self._thumb = ''
        self._background = ''
        self.path = data['path']
        self.processData(data)

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
                self._thumb = self.data.get('thumbnail_image') and tablo.API.images(self.data['thumbnail_image']['image_id']) or ''
            except:
                print self.data['thumbnail_image']
        return self._thumb

    @property
    def background(self):
        if not self._background:
            self._background = self.data.get('background_image') and tablo.API.images(self.data['background_image']['image_id']) or ''
        return self._background

    @property
    def title(self):
        return self.data['title']


class Series(Show):
    type = 'SERIES'

    def processData(self, data):
        self.data = data['series']


class Movie(Show):
    type = 'MOVIE'

    def processData(self, data):
        self.data = data['movie']


class Sport(Show):
    type = 'SPORT'

    def processData(self, data):
        self.data = data['sport']


class Program(Show):
    type = 'PROGRAM'

    def processData(self, data):
        self.data = data['program']


class GuideWindow(kodigui.BaseWindow):
    name = 'GUIDE'
    xmlFile = 'script-tablo-guide.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    types = (
        (None, 'All'),
        ('SERIES', 'TV Shows'),
        ('MOVIES', 'Movies'),
        ('SPORTS', 'Sports')
    )

    def onFirstInit(self):
        self.typeList = kodigui.ManagedControlList(self, 200, 3)
        self.showList = kodigui.ManagedControlList(self, 301, 11)
        self.keysList = kodigui.ManagedControlList(self, 400, 10)
        self.keys = {}
        self.lastKey = None
        self.lastSelectedKey = None
        self.showItems = {}

        self.setFilter()

        self._showDataThread = None
        self._showDataStopFlag = False

        self.fillTypeList()

        self.onReInit()

    def onReInit(self):
        self.fillShows()

    def onAction(self, action):
        try:
            self.updateKey(action)

            if action == xbmcgui.ACTION_NAV_BACK:
                if xbmc.getCondVisibility('ControlGroup(100).HasFocus(0)'):
                    WM.showMenu()
                    return
                else:
                    self.setFocusId(100)
                    return
            elif action == xbmcgui.ACTION_PREVIOUS_MENU:
                WM.finish()
                return
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def onClick(self, controlID):
        if controlID == 200:
            item = self.typeList.getSelectedItem()
            if item:
                self.setFilter(item.dataSource)
                self.fillShows()

    def onFocus(self, controlID):
        if controlID == 50:
            self.setFocusId(100)
            WM.showMenu()
            return

    def doClose(self):
        kodigui.BaseWindow.doClose(self)
        self.stopShowDataThread()

    def setFilter(self, filter=None):
        self.filter = filter
        util.setGlobalProperty('guide.filter', [t[1] for t in self.types if t[0] == filter][0])

    def updateKey(self, action=None):
        if self.getFocusId() == 301:
            item = self.showList.getSelectedItem()
            if not item:
                return

            key = item.getProperty('key')
            if key == self.lastKey or not key:
                return
            self.lastKey = key

            self.keysList.selectItem(self.keys[key])
        elif self.getFocusId() == 400:
            item = self.keysList.getSelectedItem()
            if not item:
                return

            if not item.getProperty('has.contents'):
                pos = item.pos()
                if action == xbmcgui.ACTION_MOVE_DOWN:
                    for i, item in enumerate(self.keysList):
                        if i > pos and item.getProperty('has.contents'):
                            self.keysList.selectItem(item.pos())
                            break
                    else:
                        self.keysList.selectItem(self.keys[self.lastSelectedKey])
                        return
                elif action == xbmcgui.ACTION_MOVE_UP:
                    for i in range(pos, -1, -1):
                        item = self.keysList[i]
                        if i < pos and item.getProperty('has.contents'):
                            self.keysList.selectItem(item.pos())
                            break
                    else:
                        self.keysList.selectItem(self.keys[self.lastSelectedKey])
                        return
                else:
                    return

            key = item.getProperty('key')
            if key == self.lastSelectedKey:
                return

            self.lastSelectedKey = key
            for i in self.showList:
                if i.getProperty('key') == key:
                    self.showList.selectItem(i.pos())
                    return

    def fillTypeList(self):
        items = []
        for ID, label in self.types:
            items.append(kodigui.ManagedListItem(label, data_source=ID))

        self.typeList.addItems(items)

        self.setFocusId(200)

    def stopShowDataThread(self):
        if not self._showDataThread or not self._showDataThread.isAlive():
            return

        util.DEBUG_LOG('Stopping data thread...')
        self._showDataStopFlag = True
        self._showDataThread.join()
        self._showDataStopFlag = False
        util.DEBUG_LOG('Data thread stopped')

    def getShowData(self, paths):
        self.stopShowDataThread()

        self._showDataThread = threading.Thread(target=self._getShowData, args=(paths,))
        self._showDataThread.start()

    def _getShowData(self, paths):
        shows = {}
        ct = 0
        while paths and not (self._showDataStopFlag or xbmc.abortRequested):
            current50 = paths[:50]
            paths = paths[50:]
            shows = tablo.API.batch.post(current50)
            ct += len(shows)
            util.DEBUG_LOG('Retrieved {0} shows'.format(ct))
            for path, show in shows.items():
                if self._showDataStopFlag or xbmc.abortRequested:
                    return
                self.updateShowItem(Show.newFromData(show))

    def updateShowItem(self, show):
        item = self.showItems[show.path]
        key = item.dataSource['key']
        item.dataSource['show'] = show
        item.setLabel(show.title)
        item.setThumbnailImage(show.thumb)
        item.setProperty('background', show.background)
        item.setProperty('key', key)

    def fillShows(self):
        self.stopShowDataThread()

        self.showList.reset()
        self.keysList.reset()

        self.showItems = {}

        if self.filter == 'SERIES':
            keys = tablo.API.views.guide.series.get()
        elif self.filter == 'MOVIES':
            keys = tablo.API.views.guide.movies.get()
        elif self.filter == 'SPORTS':
            keys = tablo.API.views.guide.sports.get()
        else:
            keys = tablo.API.views.guide.shows.get()

        paths = []

        keyitems = []
        items = []
        ct = 0
        for i, k in enumerate(keys):
            key = k['key']
            keyitem = kodigui.ManagedListItem(key.upper())
            keyitem.setProperty('key', key)
            self.lastSelectedKey = self.lastSelectedKey or key

            if k.get('contents'):
                keyitem.setProperty('has.contents', '1')
                for p in k['contents']:
                    ct += 1
                    paths.append(p)
                    item = kodigui.ManagedListItem(data_source={'path': p, 'key': key, 'show': None})
                    if ct > 6:
                        item.setProperty('after.firstrow', '1')
                    self.showItems[p] = item
                    items.append(item)

            keyitems.append(keyitem)
            self.keys[k['key']] = i

        self.keysList.addItems(keyitems)
        self.showList.addItems(items)

        self.getShowData(paths)
