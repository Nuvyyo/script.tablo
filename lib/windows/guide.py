import xbmc
import xbmcgui
import kodigui
import base
import actiondialog

from lib import util
from lib import backgroundthread
from lib import tablo

WM = None


class ShowsTask(backgroundthread.Task):
    def setup(self, paths, callback):
        self.paths = paths
        self.callback = callback

    def run(self):
        shows = {}
        ct = 0

        shows = tablo.API.batch.post(self.paths)
        ct += len(shows)
        util.DEBUG_LOG('Retrieved {0} shows'.format(ct))
        for path, show in shows.items():
            if self.isCanceled():
                return
            self.callback(tablo.Show.newFromData(show))


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

    MENU_GROUP_ID = 100
    MENU_LIST_ID = 200
    SHOW_PANEL_ID = 301
    KEY_LIST_ID = 400

    def onFirstInit(self):
        self._showingDialog = False

        self.typeList = kodigui.ManagedControlList(self, self.MENU_LIST_ID, 3)
        self.showList = kodigui.ManagedControlList(self, self.SHOW_PANEL_ID, 11)
        self.keysList = kodigui.ManagedControlList(self, self.KEY_LIST_ID, 10)
        self.keys = {}
        self.lastKey = None
        self.lastSelectedKey = None
        self.showItems = {}

        self.setFilter()

        self._tasks = []

        self.fillTypeList()

        self.onReInit()

    def onReInit(self):
        if self._showingDialog:
            return

        self.fillShows()

    def onAction(self, action):
        try:
            self.updateKey(action)

            if action == xbmcgui.ACTION_NAV_BACK:
                if xbmc.getCondVisibility('ControlGroup({0}).HasFocus(0)'.format(self.MENU_GROUP_ID)):
                    WM.showMenu()
                    return
                else:
                    self.setFocusId(self.MENU_GROUP_ID)
                    return
            elif action == xbmcgui.ACTION_PREVIOUS_MENU:
                WM.finish()
                return
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def onClick(self, controlID):
        if controlID == self.MENU_LIST_ID:
            item = self.typeList.getSelectedItem()
            if item:
                self.setFilter(item.dataSource)
                self.fillShows()
        elif controlID == self.SHOW_PANEL_ID:
            self.showClicked()

    def onFocus(self, controlID):
        if controlID == 50:
            self.setFocusId(self.MENU_GROUP_ID)
            WM.showMenu()
            return

    def doClose(self):
        kodigui.BaseWindow.doClose(self)
        self.cancelTasks()

    @base.dialogFunction
    def showClicked(self):
        item = self.showList.getSelectedItem()
        if not item:
            return

        show = item.dataSource.get('show')
        if not show:
            return

        if not show:
            self.getShowData([item.dataSource['path']])
            while not show and backgroundthread.BGThreader.working() and not xbmc.abortRequested:
                xbmc.sleep(100)
                show = item.dataSource.get('show')

        GuideShowWindow.open(show=show)

    def setFilter(self, filter=None):
        self.filter = filter
        util.setGlobalProperty('guide.filter', [t[1] for t in self.types if t[0] == filter][0])

    def updateKey(self, action=None):
        if self.getFocusId() == self.SHOW_PANEL_ID:
            item = self.showList.getSelectedItem()
            if not item:
                return

            key = item.getProperty('key')
            if key == self.lastKey or not key:
                return
            self.lastKey = key

            self.keysList.selectItem(self.keys[key])
        elif self.getFocusId() == self.KEY_LIST_ID:
            if action == xbmcgui.ACTION_PAGE_DOWN or action == xbmcgui.ACTION_PAGE_UP:
                if self.lastSelectedKey:
                    self.keysList.selectItem(self.keys[self.lastSelectedKey])
                return

            item = self.keysList.getSelectedItem()

            if not item:
                return

            if not item.getProperty('has.contents'):
                pos = item.pos()

                if action == xbmcgui.ACTION_MOVE_DOWN or action == xbmcgui.ACTION_PAGE_DOWN:
                    for i in range(pos + 1, len(self.keysList)):
                        item = self.keysList[i]
                        if item.getProperty('has.contents'):
                            self.keysList.selectItem(item.pos())
                            break
                    else:
                        self.keysList.selectItem(self.keys[self.lastSelectedKey])
                        return
                elif action == xbmcgui.ACTION_MOVE_UP or action == xbmcgui.ACTION_PAGE_UP:
                    for i in range(pos - 1, -1, -1):
                        item = self.keysList[i]
                        if item.getProperty('has.contents'):
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

    def cancelTasks(self):
        for t in self._tasks:
            t.cancel()
        self._tasks = []

    def getShowData(self, paths):
        self.cancelTasks()

        while paths:
            current50 = paths[:50]
            paths = paths[50:]
            t = ShowsTask()
            self._tasks.append(t)
            t.setup(current50, self.updateShowItem)

        backgroundthread.BGThreader.addTasks(self._tasks)

    def updateShowItem(self, show):
        item = self.showItems[show.path]
        key = item.dataSource['key']
        item.dataSource['show'] = show
        item.setLabel(show.title)
        item.setThumbnailImage(show.thumb)
        item.setProperty('background', show.background)
        item.setProperty('key', key)

    def fillShows(self):
        self.cancelTasks()

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


class AiringsTask(backgroundthread.Task):
    def setup(self, paths, callback, airing_type):
        self.paths = paths
        self.callback = callback
        self.airingType = airing_type

    def run(self):
        episodes = tablo.API.batch.post(self.paths)
        util.DEBUG_LOG('Retrieved {0} episodes'.format(len(episodes)))
        for path, episode in episodes.items():
            if self.isCanceled():
                return
            self.callback(tablo.Airing(episode, self.airingType))


class GuideShowWindow(kodigui.BaseWindow):
    name = 'GUIDE'
    xmlFile = 'script-tablo-show.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    EPISODES_BUTTON_ID = 400
    SCHEDULE_BUTTON_ID = 401
    EPISODES_LIST_ID = 300

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        self.show = kwargs.get('show')

    def onFirstInit(self):
        self._tasks = []
        self.episodeItems = {}

        self.setProperty('thumb', self.show.thumb)
        self.setProperty('background', self.show.background)
        self.setProperty('title', self.show.title)
        self.setProperty('plot', self.show.plot or self.show.description)

        self.episodesList = kodigui.ManagedControlList(self, self.EPISODES_LIST_ID, 20)

        self.fillEpisodes()

    def onClick(self, controlID):
        if controlID == self.EPISODES_LIST_ID:
            self.episodesListClicked()

    def onAction(self, action):
        controlID = self.getFocusId()

        try:
            if action == xbmcgui.ACTION_NAV_BACK or action == xbmcgui.ACTION_PREVIOUS_MENU:
                self.doClose()
                return
            elif controlID == self.EPISODES_LIST_ID:
                self.updateEpisodeSelection(action)
            elif action == xbmcgui.ACTION_PAGE_DOWN:
                if xbmc.getCondVisibility('ControlGroup(100).HasFocus(0)'):
                    xbmc.executebuiltin('Action(down)')
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def doClose(self):
        kodigui.BaseWindow.doClose(self)
        self.cancelTasks()

    def episodesListClicked(self):
        item = self.episodesList.getSelectedItem()
        if not item:
            return

        episode = item.dataSource.get('episode')
        if not episode:
            return

        info = 'Channel {0} {1} on {2} from {3} to {4}'.format(
            episode.displayChannel(),
            episode.network,
            episode.displayDay(),
            episode.displayTimeStart(),
            episode.displayTimeEnd()
        )

        kwargs = {
            'number': episode.number,
            'background': self.show.background,
            'callback': self.actionDialogCallback,
            'obj': episode
        }

        if episode.scheduled:
            kwargs['button1'] = ('unschedule', "Don't Record Episode")
            kwargs['title_indicator'] = 'indicators/rec_pill_hd.png'
        elif episode.airingNow():
            kwargs['button1'] = ('watch', 'Watch')
            kwargs['button2'] = ('record', 'Record Episode')
        else:
            kwargs['button1'] = ('record', 'Record Episode')

        secs = episode.secondsToStart()

        if secs < 1:
            start = 'Started {0} ago'.format(util.durationToText(secs*-1))
        else:
            start = 'Starts in {0}'.format(util.durationToText(secs))

        actiondialog.openDialog(
            episode.title or self.show.title,
            info, episode.description,
            start,
            **kwargs
        )

        self.updateIndicators()

    def actionDialogCallback(self, obj, action):
        if not action:
            return

        episode = obj

        buttons = {}

        if action == 'watch':
            xbmc.Player().play(episode.watch().url)
        elif action == 'record':
            episode.schedule()
        elif action == 'unschedule':
            episode.schedule(False)

        if episode.scheduled:
            buttons['button1'] = ('unschedule', "Don't Record Episode")
            buttons['title_indicator'] = 'indicators/rec_pill_hd.png'
        elif episode.airingNow():
            buttons['button1'] = ('watch', 'Watch')
            buttons['button2'] = ('record', 'Record Episode')
        else:
            buttons['button1'] = ('record', 'Record Episode')

        return buttons

    def updateEpisodeSelection(self, action=None):
        item = self.episodesList.getSelectedItem()
        if not item:
            return

        if item.getProperty('header'):
            pos = item.pos()
            if action == xbmcgui.ACTION_MOVE_UP or action == xbmcgui.ACTION_PAGE_UP:
                if pos < 2:
                    self.episodesList.selectItem(0)
                    self.setFocusId(self.EPISODES_BUTTON_ID)
                    return

                for i in range(pos-1, 2, -1):
                    nextItem = self.episodesList.getListItem(i)
                    if not nextItem.getProperty('header'):
                        self.episodesList.selectItem(nextItem.pos())
                        return
            else:  # action == xbmcgui.ACTION_MOVE_DOWN or action == xbmcgui.ACTION_PAGE_DOWN:
                for i in range(pos+1, self.episodesList.size()):
                    nextItem = self.episodesList.getListItem(i)
                    if not nextItem.getProperty('header'):
                        self.episodesList.selectItem(nextItem.pos())
                        return

    def cancelTasks(self):
        for t in self._tasks:
            t.cancel()
        self._tasks = []

    def getEpisodeData(self, paths):
        self.cancelTasks()

        while paths:
            current50 = paths[:50]
            paths = paths[50:]
            t = AiringsTask()
            self._tasks.append(t)
            t.setup(current50, self.updateEpisodeItem, self.show.airingType)

        backgroundthread.BGThreader.addTasks(self._tasks)

    def updateItemIndicators(self, item):
        episode = item.dataSource['episode']
        if not episode:
            return
        item.setProperty('badge', episode.scheduled and 'livetv/livetv_badge_scheduled_hd.png' or '')

    def updateIndicators(self):
        for item in self.episodesList:
            self.updateItemIndicators(item)

    def updateEpisodeItem(self, episode):
        item = self.episodeItems[episode.path]
        item.dataSource['episode'] = episode

        if episode.type == 'schedule':
            label = self.show.title
        else:
            label = episode.title

        if not label:
            label = 'Ch. {0} {1} at {2} - {3}'.format(
                episode.displayChannel(),
                episode.network,
                episode.displayTimeStart(),
                episode.displayTimeEnd()
            )

        item.setLabel(label)
        item.setLabel2(episode.displayDay())
        item.setProperty('number', str(episode.number or ''))
        item.setProperty('airing', episode.airingNow() and '1' or '')

        self.updateItemIndicators(item)

    @util.busyDialog
    def fillEpisodes(self):
        self.episodeItems = {}
        airings = []

        if isinstance(self.show, tablo.Series):
            seasons = self.show.seasons()
            seasonsData = tablo.API.batch.post(seasons)

            for seasonPath in seasons:
                season = seasonsData[seasonPath]

                number = season['season']['number']
                title = number and 'Season {0}'.format(number) or 'Other Seasons'

                item = kodigui.ManagedListItem('', data_source={'path': None, 'episode': None})
                item.setProperty('header', '1')
                self.episodesList.addItem(item)
                item = kodigui.ManagedListItem(title, data_source={'path': None, 'episode': None})
                item.setProperty('header', '1')
                self.episodesList.addItem(item)

                seasonEps = tablo.API(seasonPath).episodes.get()
                airings += seasonEps

                for p in seasonEps:
                    item = kodigui.ManagedListItem('', data_source={'path': p, 'episode': None})
                    self.episodeItems[p] = item
                    self.episodesList.addItem(item)
        else:
            airings = self.show.airings()

            item = kodigui.ManagedListItem('', data_source={'path': None, 'episode': None})
            item.setProperty('header', '1')
            self.episodesList.addItem(item)

            for p in airings:
                item = kodigui.ManagedListItem('', data_source={'path': p, 'episode': None})
                self.episodeItems[p] = item
                self.episodesList.addItem(item)

        self.getEpisodeData(airings)
