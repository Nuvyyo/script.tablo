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
    SHOW_GROUP_ID = 300
    SHOW_PANEL_ID = 301
    KEY_LIST_ID = 400

    view = 'guide'
    state = None
    section = 'Guide'

    def onFirstInit(self):
        self._showingDialog = False

        self.typeList = kodigui.ManagedControlList(self, self.MENU_LIST_ID, 3)
        self.showList = kodigui.ManagedControlList(self, self.SHOW_PANEL_ID, 11)
        self.keysList = kodigui.ManagedControlList(self, self.KEY_LIST_ID, 10)
        self.keys = {}
        self.lastKey = None
        self.lastSelectedKey = None
        self.showItems = {}

        self.setFilter(None)

        self._tasks = []

        self.fillTypeList()

        self.onReInit()

    def onReInit(self):
        if not self._showingDialog:
            self.fillShows()

        self.setFilter()
        self.onWindowFocus()

    def onWindowFocus(self):
        if self.getProperty('hide.menu'):
            self.setFocusId(self.SHOW_GROUP_ID)

    def onAction(self, action):
        try:
            self.updateKey(action)

            if action == xbmcgui.ACTION_NAV_BACK:
                if xbmc.getCondVisibility('ControlGroup({0}).HasFocus(0)'.format(self.MENU_GROUP_ID)) or self.getProperty('hide.menu'):
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
            self.getSingleShowData(item.dataSource['path'])
            while not show and backgroundthread.BGThreader.working() and not xbmc.abortRequested:
                xbmc.sleep(100)
                show = item.dataSource.get('show')

        if self.closing():
            return

        GuideShowWindow.open(show=show)

    def setFilter(self, filter_=False):
        if filter_ is False:
            filter_ = self.filter
        else:
            self.filter = filter_

        util.setGlobalProperty('section', self.section)
        util.setGlobalProperty('guide.filter', [t[1] for t in self.types if t[0] == filter_][0])

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

    def getSingleShowData(self, path):
        t = ShowsTask()
        t.setup([path], self.updateShowItem)
        backgroundthread.BGThreader.addTasks([t])

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

        args = {}
        if self.state:
            args = {'state': self.state}

        if self.filter == 'SERIES':
            keys = tablo.API.views(self.view).series.get(**args)
        elif self.filter == 'MOVIES':
            keys = tablo.API.views(self.view).movies.get(**args)
        elif self.filter == 'SPORTS':
            keys = tablo.API.views(self.view).sports.get(**args)
        else:
            keys = tablo.API.views(self.view).shows.get(**args)

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
        airings = tablo.API.batch.post(self.paths)
        util.DEBUG_LOG('Retrieved {0} airings'.format(len(airings)))
        for path, airing in airings.items():
            if self.isCanceled():
                return
            self.callback(tablo.Airing(airing, self.airingType))


class GuideShowWindow(kodigui.BaseWindow):
    name = 'GUIDE'
    xmlFile = 'script-tablo-show.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    SHOW_BUTTONS_GROUP_ID = 100
    AIRINGS_BUTTON_ID = 400
    SCHEDULE_BUTTON_ID = 401
    AIRINGS_LIST_ID = 300

    SCHEDULE_GROUP_ID = 500
    SCHEDULE_BUTTON_TOP_ID = 501
    SCHEDULE_BUTTON_BOT_ID = 502

    sectionAction = 'Schedule...'

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        self.show = kwargs.get('show')
        self.scheduleButtonActions = {}

    def onFirstInit(self):
        self._tasks = []
        self.airingItems = {}

        self.setProperty('thumb', self.show.thumb)
        self.setProperty('background', self.show.background)
        self.setProperty('title', self.show.title)
        self.setProperty('plot', self.show.plot or self.show.description)
        self.setProperty('airing.label', util.LOCALIZED_AIRING_TYPES_PLURAL[self.show.type])
        self.setProperty('section.action', self.sectionAction)
        self.setProperty('is.movie', self.show.type == 'MOVIE' and '1' or '')

        self.airingsList = kodigui.ManagedControlList(self, self.AIRINGS_LIST_ID, 20)

        self.setupScheduleDialog()
        self.fillAirings()

    def onClick(self, controlID):
        if controlID == self.AIRINGS_LIST_ID:
            self.airingsListClicked()
        elif self.SCHEDULE_BUTTON_TOP_ID <= controlID <= self.SCHEDULE_BUTTON_BOT_ID:
            self.scheduleButtonClicked(controlID)

    def onAction(self, action):
        controlID = self.getFocusId()

        try:
            if action == xbmcgui.ACTION_NAV_BACK or action == xbmcgui.ACTION_PREVIOUS_MENU:
                if xbmc.getCondVisibility('ControlGroup({0}).HasFocus(0)'.format(self.SCHEDULE_GROUP_ID)):
                    self.setFocusId(self.SHOW_BUTTONS_GROUP_ID)
                else:
                    self.doClose()
                return
            elif controlID == self.AIRINGS_LIST_ID:
                self.updateAiringSelection(action)
            elif action == xbmcgui.ACTION_PAGE_DOWN:
                if xbmc.getCondVisibility('ControlGroup(100).HasFocus(0)'):
                    xbmc.executebuiltin('Action(down)')
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def doClose(self):
        kodigui.BaseWindow.doClose(self)
        self.cancelTasks()

    def scheduleButtonClicked(self, controlID):
        action = self.scheduleButtonActions.get(controlID)
        if not action:
            return

        self.show.schedule(action)

        self.setupScheduleDialog()

    def airingsListClicked(self):
        item = self.airingsList.getSelectedItem()
        if not item:
            return

        airing = item.dataSource.get('airing')

        while not airing and backgroundthread.BGThreader.working() and not xbmc.abortRequested:
            xbmc.sleep(100)
            airing = item.dataSource.get('airing')

        info = 'Channel {0} {1} on {2} from {3} to {4}'.format(
            airing.displayChannel(),
            airing.network,
            airing.displayDay(),
            airing.displayTimeStart(),
            airing.displayTimeEnd()
        )

        kwargs = {
            'number': airing.number,
            'background': self.show.background,
            'callback': self.actionDialogCallback,
            'obj': airing
        }

        if airing.scheduled:
            kwargs['button1'] = ('unschedule', "Don't Record {0}".format(util.LOCALIZED_AIRING_TYPES[self.show.type]))
            kwargs['title_indicator'] = 'indicators/rec_pill_hd.png'
        elif airing.airingNow():
            kwargs['button1'] = ('watch', 'Watch')
            kwargs['button2'] = ('record', 'Record {0}'.format(util.LOCALIZED_AIRING_TYPES[self.show.type]))
        else:
            kwargs['button1'] = ('record', 'Record {0}'.format(util.LOCALIZED_AIRING_TYPES[self.show.type]))

        secs = airing.secondsToStart()

        if secs < 1:
            start = 'Started {0} ago'.format(util.durationToText(secs*-1))
        else:
            start = 'Starts in {0}'.format(util.durationToText(secs))

        actiondialog.openDialog(
            airing.title or self.show.title,
            info, airing.description,
            start,
            **kwargs
        )

        self.updateIndicators()

    def actionDialogCallback(self, obj, action):
        airing = obj
        changes = {}

        if action:
            if action == 'watch':
                xbmc.Player().play(airing.watch().url)
            elif action == 'record':
                airing.schedule()
            elif action == 'unschedule':
                airing.schedule(False)

        if airing.ended():
            secs = airing.secondsSinceEnd()
            changes['start'] = 'Ended {0} ago'.format(util.durationToText(secs))
        else:
            if airing.airingNow():
                changes['button1'] = ('watch', 'Watch')
                if airing.scheduled:
                    changes['button2'] = ('unschedule', "Don't Record {0}".format(util.LOCALIZED_AIRING_TYPES[self.show.type]))
                    changes['title_indicator'] = 'indicators/rec_pill_hd.png'
                else:
                    changes['button2'] = ('record', 'Record {0}'.format(util.LOCALIZED_AIRING_TYPES[self.show.type]))
            else:
                if airing.scheduled:
                    changes['button1'] = ('unschedule', "Don't Record {0}".format(util.LOCALIZED_AIRING_TYPES[self.show.type]))
                    changes['title_indicator'] = 'indicators/rec_pill_hd.png'
                else:
                    changes['button1'] = ('record', 'Record {0}'.format(util.LOCALIZED_AIRING_TYPES[self.show.type]))

            secs = airing.secondsToStart()

            if secs < 1:
                start = 'Started {0} ago'.format(util.durationToText(secs*-1))
            else:
                start = 'Starts in {0}'.format(util.durationToText(secs))

            changes['start'] = start

        return changes

    def updateAiringSelection(self, action=None):
        item = self.airingsList.getSelectedItem()
        if not item:
            return

        if item.getProperty('header'):
            pos = item.pos()
            if action == xbmcgui.ACTION_MOVE_UP or action == xbmcgui.ACTION_PAGE_UP:
                if pos < 2:
                    self.airingsList.selectItem(0)
                    self.setFocusId(self.AIRINGS_BUTTON_ID)
                    return

                for i in range(pos-1, 2, -1):
                    nextItem = self.airingsList.getListItem(i)
                    if not nextItem.getProperty('header'):
                        self.airingsList.selectItem(nextItem.pos())
                        return
            else:  # action == xbmcgui.ACTION_MOVE_DOWN or action == xbmcgui.ACTION_PAGE_DOWN:
                for i in range(pos+1, self.airingsList.size()):
                    nextItem = self.airingsList.getListItem(i)
                    if not nextItem.getProperty('header'):
                        self.airingsList.selectItem(nextItem.pos())
                        return

    def cancelTasks(self):
        for t in self._tasks:
            t.cancel()
        self._tasks = []

    def getAiringData(self, paths):
        self.cancelTasks()

        while paths:
            current50 = paths[:50]
            paths = paths[50:]
            t = AiringsTask()
            self._tasks.append(t)
            t.setup(current50, self.updateAiringItem, self.show.airingType)

        backgroundthread.BGThreader.addTasks(self._tasks)

    def updateItemIndicators(self, item):
        airing = item.dataSource['airing']
        if not airing:
            return
        item.setProperty('badge', airing.scheduled and 'livetv/livetv_badge_scheduled_hd.png' or '')

    def updateIndicators(self):
        for item in self.airingsList:
            self.updateItemIndicators(item)

    def updateAiringItem(self, airing):
        item = self.airingItems[airing.path]
        item.dataSource['airing'] = airing

        if airing.type == 'schedule':
            label = self.show.title
        else:
            label = airing.title

        if not label:
            label = 'Ch. {0} {1} at {2} - {3}'.format(
                airing.displayChannel(),
                airing.network,
                airing.displayTimeStart(),
                airing.displayTimeEnd()
            )

        item.setLabel(label)
        item.setLabel2(airing.displayDay())
        item.setProperty('number', str(airing.number or ''))
        item.setProperty('airing', airing.airingNow() and '1' or '')

        self.updateItemIndicators(item)

    def setupScheduleDialog(self):
        self.setProperty(
            'schedule.message', 'Automatically schedule {0} for this {1}?'.format(
                util.LOCALIZED_AIRING_TYPES_PLURAL[self.show.type].lower(),
                util.LOCALIZED_SHOW_TYPES[self.show.type].lower(),
            )
        )

        self.scheduleButtonActions = {}

        if self.show.scheduleRule == 'all':
            self.scheduleButtonActions[self.SCHEDULE_BUTTON_TOP_ID] = 'none'
            self.scheduleButtonActions[self.SCHEDULE_BUTTON_BOT_ID] = 'new'
            self.setProperty('schedule.top', 'Unschedule Show')
            self.setProperty('schedule.bottom', 'Record New')
            self.setProperty('title.indicator', 'indicators/rec_all_pill_hd.png')
        elif self.show.scheduleRule == 'new':
            self.scheduleButtonActions[self.SCHEDULE_BUTTON_TOP_ID] = 'none'
            self.scheduleButtonActions[self.SCHEDULE_BUTTON_BOT_ID] = 'all'
            self.setProperty('schedule.top', 'Unschedule Show')
            self.setProperty('schedule.bottom', 'Record All')
            self.setProperty('title.indicator', 'indicators/rec_new_pill_hd.png')
        else:
            self.scheduleButtonActions[self.SCHEDULE_BUTTON_TOP_ID] = 'all'
            self.scheduleButtonActions[self.SCHEDULE_BUTTON_BOT_ID] = 'new'
            self.setProperty('schedule.top', 'Record All')
            self.setProperty('schedule.bottom', 'Record New')
            self.setProperty('title.indicator', '')

    @util.busyDialog
    def fillAirings(self):
        self.airingItems = {}
        airings = []

        if isinstance(self.show, tablo.Series):
            seasons = self.show.seasons()
            seasonsData = tablo.API.batch.post(seasons)

            for seasonPath in seasons:
                season = seasonsData[seasonPath]

                number = season['season']['number']
                title = number and 'Season {0}'.format(number) or 'Other Seasons'

                item = kodigui.ManagedListItem('', data_source={'path': None, 'airing': None})
                item.setProperty('header', '1')
                self.airingsList.addItem(item)
                item = kodigui.ManagedListItem(title, data_source={'path': None, 'airing': None})
                item.setProperty('header', '1')
                self.airingsList.addItem(item)

                seasonEps = tablo.API(seasonPath).episodes.get()
                airings += seasonEps

                for p in seasonEps:
                    item = kodigui.ManagedListItem('', data_source={'path': p, 'airing': None})
                    self.airingItems[p] = item
                    self.airingsList.addItem(item)
        else:
            airings = self.show.airings()

            item = kodigui.ManagedListItem('', data_source={'path': None, 'airing': None})
            item.setProperty('header', '1')
            self.airingsList.addItem(item)

            for p in airings:
                item = kodigui.ManagedListItem('', data_source={'path': p, 'airing': None})
                self.airingItems[p] = item
                self.airingsList.addItem(item)

        self.getAiringData(airings)
