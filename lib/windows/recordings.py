import xbmc
import xbmcgui
import kodigui

from lib import util
from lib import tablo

WM = None


class RecordingsWindow(kodigui.BaseWindow):
    name = 'RECORDINGS'
    xmlFile = 'script-tablo-recordings.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    types = (
        ('all', 'All'),
        ('tvshows', 'TV Shows'),
        ('movies', 'Movies'),
        ('sports', 'Sports')
    )

    def onFirstInit(self):
        self.typeList = kodigui.ManagedControlList(self, 200, 3)
        self.recordingsList = kodigui.ManagedControlList(self, 301, 11)
        self.keysList = kodigui.ManagedControlList(self, 400, 10)
        self.keys = {}
        self.lastKey = None
        self.lastSelectedKey = None

        self.fillTypeList()
        self.fillRecordings()

    def onAction(self, action):
        try:
            self.updateKey()

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
        print controlID

    def onFocus(self, controlID):
        if controlID == 50:
            self.setFocusId(100)
            WM.showMenu()
            return

    def updateKey(self):
        if self.getFocusId() == 301:
            item = self.recordingsList.getSelectedItem()
            if not item:
                return

            key = item.getProperty('key')
            if key == self.lastKey:
                return
            self.lastKey = key

            self.keysList.selectItem(self.keys[key])
        elif self.getFocusId() == 400:
            item = self.keysList.getSelectedItem()
            if not item:
                return

            if not item.getProperty('has.contents'):
                return
            key = item.getProperty('key')
            if key == self.lastSelectedKey:
                return

            self.lastSelectedKey = key
            for i in self.recordingsList:
                if i.getProperty('key') == key:
                    self.recordingsList.selectItem(i.pos())
                    return

    def fillTypeList(self):
        items = []
        for ID, label in self.types:
            items.append(kodigui.ManagedListItem(label, data_source=ID))

        self.typeList.addItems(items)

        self.setFocusId(200)

    def fillRecordings(self):
        keys = tablo.API.views.recordings.shows.get()

        paths = []

        items = []
        for i, k in enumerate(keys):
            item = kodigui.ManagedListItem(k['key'].upper())
            item.setProperty('key', k['key'])

            if k.get('contents'):
                item.setProperty('has.contents', '1')
                for p in k['contents']:
                    paths.append(p)

            items.append(item)
            self.keys[k['key']] = i

        self.keysList.addItems(items)

        shows = tablo.API.batch.post(paths)

        items = []
        for k in keys:
            if not k.get('contents'):
                continue

            self.lastSelectedKey = self.lastSelectedKey or k['key']

            for p in k['contents']:
                show = shows[p]
                series = show['series']
                thumb = tablo.API.images(series['thumbnail_image']['image_id'])
                background = tablo.API.images(series['background_image']['image_id'])
                item = kodigui.ManagedListItem(series['title'], thumbnailImage=thumb, data_source=series)
                item.setProperty('background', background)
                item.setProperty('key', k['key'])
                item.setProperty('count', str(show['show_counts']['unwatched_count']))
                items.append(item)

        self.recordingsList.addItems(items)
