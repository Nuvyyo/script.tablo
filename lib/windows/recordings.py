import xbmc
import xbmcgui
import kodigui
import base
import actiondialog

from lib import util
from lib import backgroundthread
from lib import player
from lib import tablo

import guide


class RecordingsWindow(guide.GuideWindow):
    name = 'RECORDINGS'
    view = 'recordings'
    section = 'Recordings'

    types = (
        (None, 'All'),
        ('RECENT', 'Recent'),
        ('SERIES', 'TV Shows'),
        ('MOVIES', 'Movies'),
        ('SPORTS', 'Sports')
    )

    emptyMessage = ('No Recordings', 'You can schedule recordings from the Guide screen.')
    emptyMessageTVShows = ('No Recorded TV Shows', 'You can schedule recordings from the Guide screen.')
    emptyMessageMovies = ('No Recorded Movies', 'You can schedule recordings from the Guide screen.')
    emptyMessageSports = ('No Recorded Sports', 'You can schedule recordings from the Guide screen.')

    RECENT_LIST_ID = 500

    def onFirstInit(self):
        self.recentList = kodigui.ManagedControlList(self, self.RECENT_LIST_ID, 11)
        guide.GuideWindow.onFirstInit(self)

    def onAction(self, action):
        try:
            controlID = self.getFocusId()
            if controlID == self.RECENT_LIST_ID:
                if self.updateRecentSelection(action):
                    return
        except:
            util.ERROR()

        guide.GuideWindow.onAction(self, action)

    def onClick(self, controlID):
        if controlID == self.RECENT_LIST_ID:
            return self.showClicked()

        guide.GuideWindow.onClick(self, controlID)

    @base.dialogFunction
    def showClicked(self):
        if self.getFocusId() == self.RECENT_LIST_ID:
            item = self.recentList.getSelectedItem()
        else:
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

        w = RecordingShowWindow.open(show=show)
        if w.modified:
            self.fillShows()
        del w

    def updateRecentSelection(self, action=None):
        item = self.recentList.getSelectedItem()
        if not item:
            return False

        if item.getProperty('header'):
            pos = item.pos()
            if action == xbmcgui.ACTION_MOVE_UP or action == xbmcgui.ACTION_PAGE_UP:
                if pos < 2:
                    self.recentList.selectItem(2)
                    return True

                for i in range(pos-1, 1, -1):
                    nextItem = self.recentList.getListItem(i)
                    if not nextItem.getProperty('header'):
                        self.recentList.selectItem(nextItem.pos())
                        return True
            else:  # action == xbmcgui.ACTION_MOVE_DOWN or action == xbmcgui.ACTION_PAGE_DOWN:
                for i in range(pos+1, self.recentList.size()):
                    nextItem = self.recentList.getListItem(i)
                    if not nextItem.getProperty('header'):
                        self.recentList.selectItem(nextItem.pos())
                        return True
        else:
            return False

    def fillShows(self, reset=False):
        if self.filter == 'RECENT':
            return self.fillRecent()

        self.setProperty('show.recent', '')
        self.recentList.reset()
        guide.GuideWindow.fillShows(self, reset=reset)

    @util.busyDialog
    @base.tabloErrorHandler
    def fillRecent(self):
        self.setProperty('show.recent', '1')
        self.showList.reset()
        self.recentList.reset()
        self.showItems = {}
        airings = []

        recentDates = tablo.API.views.recordings.recent.get()

        first = True
        for date in recentDates:
            item = kodigui.ManagedListItem('', data_source={'path': None, 'airing': None})
            item.setProperty('header', '1')
            self.recentList.addItem(item)

            item = kodigui.ManagedListItem(date['key'], data_source={'path': None, 'airing': None})
            item.setProperty('header', '1')
            item.setProperty('top', '1')
            self.recentList.addItem(item)

            for airingPath in date['contents']:
                airings.append(airingPath)
                item = kodigui.ManagedListItem('', data_source={'path': airingPath, 'airing': None})
                if first:
                    first = False
                    item.setProperty('top', '1')
                self.showItems[airingPath] = item
                self.recentList.addItem(item)

        self.getAiringData(airings)

    def updateItemIndicators(self, item):
        airing = item.dataSource['airing']
        if not airing:
            return

        if airing.data['video_details']['state'] == 'failed':
            item.setProperty('indicator', 'recordings/recording_failed_small_dark_hd.png')
        elif airing.watched:
            item.setProperty('indicator', '')
        else:
            if airing.data['user_info']['position']:
                item.setProperty('indicator', 'recordings/seen_small_partial_hd.png')
            else:
                item.setProperty('indicator', 'recordings/seen_small_unwatched_hd.png')

        item.setProperty('protected', airing.protected and '1' or '')

        if airing.deleted:
            item.setProperty('disabled', '1')

    def updateIndicators(self):
        for item in self.recentList:
            self.updateItemIndicators(item)

    def updateAiringItem(self, airing):
        item = self.showItems[airing.path]
        item.dataSource['airing'] = airing

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

        self.updateItemIndicators(item)

    def getAiringData(self, paths):
        self.cancelTasks()

        while paths:
            current50 = paths[:50]
            paths = paths[50:]
            t = guide.AiringsTask()
            self._tasks.append(t)
            t.setup(current50, self.updateAiringItem, None)  # self.show.airingType)

        backgroundthread.BGThreader.addTasks(self._tasks)


class RecordingShowWindow(guide.GuideShowWindow):
    sectionAction = 'Delete...'

    def setDialogIndicators(self, airing, arg_dict):
        if airing.type == 'schedule':
            description = self.show.description or ''
        else:
            description = airing.description or ''

        failed = airing.data['video_details']['state'] == 'failed'

        if failed:
            description += u'[CR][CR][COLOR FFC81010]Recording failed due to: {0}[/COLOR]'.format(airing.data['video_details']['error']['details'])
        else:
            if airing.watched:
                arg_dict['indicator'] = ''
            else:
                if airing.data['user_info']['position']:
                    arg_dict['indicator'] = 'indicators/seen_partial_hd.png'
                else:
                    arg_dict['indicator'] = 'indicators/seen_unwatched_hd.png'

            if airing.data['user_info']['position']:
                left = airing.data['video_details']['duration'] - airing.data['user_info']['position']
                total = airing.data['video_details']['duration']
                description += '[CR][CR]Remaining: {0} of {1}'.format(util.durationToText(left), util.durationToText(total))
                arg_dict['seenratio'] = airing.data['user_info']['position'] / float(total)
                arg_dict['seen'] = airing.data['user_info']['position']
            else:
                description += '[CR][CR]Length: {0}'.format(util.durationToText(airing.data['video_details']['duration']))
                arg_dict['seenratio'] = None
                arg_dict['seen'] = None

        arg_dict['plot'] = description

    def airingsListClicked(self):
        item = self.airingsList.getSelectedItem()
        if not item:
            return

        airing = item.dataSource.get('airing')

        if airing and airing.deleted:
            return

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
            'background': self.show.background,
            'callback': self.actionDialogCallback,
            'obj': airing,
            'show': self.show
        }

        if airing.type == 'schedule':
            title = self.show.title
        else:
            title = airing.title or self.show.title

        failed = airing.data['video_details']['state'] == 'failed'

        self.setDialogIndicators(airing, kwargs)

        openDialog(
            title,
            info,
            airing.snapshot,
            failed,
            airing.watched and 'Mark Unwatched' or 'Mark Watched',
            airing.protected and 'Unprotect' or 'Protect',
            **kwargs
        )

        self.updateIndicators()

    def actionDialogCallback(self, obj, action):
        airing = obj
        changes = {}

        if action:
            if action == 'watch':
                player.PLAYER.playRecording(airing, show=self.show, resume=False)
                # xbmc.Player().play(airing.watch().url)
            elif action == 'resume':
                player.PLAYER.playRecording(airing, show=self.show)
            elif action == 'toggle':
                airing.markWatched(not airing.watched)
                self.modified = True
            elif action == 'protect':
                airing.markProtected(not airing.protected)
            elif action == 'delete':
                self.modified = True
                airing.delete()
                return None
            if action == 'toggle':
                changes['button2'] = airing.watched and 'Mark Unwatched' or 'Mark Watched'
            elif action == 'protect':
                changes['button3'] = airing.protected and 'Unprotect' or 'Protect'

            self.setDialogIndicators(airing, changes)

        return changes

    def scheduleButtonClicked(self, controlID):
        action = self.scheduleButtonActions.get(controlID)
        if not action or action != 'delete':
            return

        self.setProperty('action.busy', '1')
        try:
            for item in self.airingsList:
                airing = item.dataSource.get('airing')
                if not airing or airing.deleted:
                    continue
                airing.delete()
        except tablo.APIError:
            util.ERROR()
        finally:
            self.setProperty('action.busy', '')

        self.modified = True

        self.updateIndicators()

    def updateItemIndicators(self, item):
        airing = item.dataSource['airing']
        if not airing:
            return

        if airing.data['video_details']['state'] == 'failed':
            item.setProperty('indicator', 'recordings/recording_failed_small_dark_hd.png')
        elif airing.watched:
            item.setProperty('indicator', '')
        else:
            if airing.data['user_info']['position']:
                item.setProperty('indicator', 'recordings/seen_small_partial_hd.png')
            else:
                item.setProperty('indicator', 'recordings/seen_small_unwatched_hd.png')

        item.setProperty('protected', airing.protected and '1' or '')

        if airing.deleted:
            item.setProperty('disabled', '1')

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

        self.updateItemIndicators(item)

    def setupScheduleDialog(self):
        self.setProperty(
            'schedule.message', 'Permanently delete the following {0}?'.format(
                util.LOCALIZED_AIRING_TYPES_PLURAL[self.show.type].lower()
            )
        )

        self.scheduleButtonActions = {}

        self.scheduleButtonActions[self.SCHEDULE_BUTTON_TOP_ID] = 'delete'
        self.scheduleButtonActions[self.SCHEDULE_BUTTON_BOT_ID] = 'cancel'
        self.setProperty('schedule.top', 'Delete All {0}'.format(util.LOCALIZED_AIRING_TYPES_PLURAL[self.show.type]))
        self.setProperty('schedule.bottom', 'Cancel')
        # self.setProperty('title.indicator', 'indicators/rec_all_pill_hd.png')

    def fillAirings(self):
        guide.GuideShowWindow.fillAirings(self)
        self.setProperty('hide.menu', not self.airingsList.size() and '1' or '')


class RecordingDialog(actiondialog.ActionDialog):
    name = 'GUIDE'
    xmlFile = 'script-tablo-recording-action.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    BUTTONS_GROUP_ID = 399
    WATCH_BUTTON_ID = 400
    TOGGLE_BUTTON_ID = 401
    PROTECT_BUTTON_ID = 402
    DELETE_BUTTON_ID = 403

    DIALOG_GROUP_ID = 500
    DIALOG_TOP_BUTTON_ID = 501
    DIALOG_BOTTOM_BUTTON_ID = 502

    SEEN_PROGRESS_IMAGE_ID = 600
    SEEN_PROGRESS_WIDTH = 356

    def __init__(self, *args, **kwargs):
        actiondialog.ActionDialog.__init__(self, *args, **kwargs)
        self.title = kwargs.get('title')
        self.info = kwargs.get('info')
        self.plot = kwargs.get('plot')
        self.preview = kwargs.get('preview', '')
        self.failed = kwargs.get('failed', '')
        self.indicator = kwargs.get('indicator', '')
        self.seen = kwargs.get('seen')
        self.seenratio = kwargs.get('seenratio')
        self.background = kwargs.get('background')
        self.callback = kwargs.get('callback')
        self.object = kwargs.get('object')
        self.show = kwargs.get('show')
        self.button2 = kwargs.get('button2')
        self.button3 = kwargs.get('button3')
        self.action = None
        self.parentAction = None
        util.CRON.registerReceiver(self)

    def onFirstInit(self):
        self.updateDisplayProperties()
        self.setProperty('title', self.title)
        self.setProperty('info', self.info)
        self.setProperty('plot', self.plot)
        self.setProperty('preview', self.preview)
        self.setProperty('failed', self.failed and '1' or '')
        self.setProperty('seen', self.seen and '1' or '')
        self.setProperty('indicator', self.indicator)
        self.setProperty('background', self.background)
        self.setProperty('button2', self.button2)
        self.setProperty('button3', self.button3)

        if self.seenratio:
            self.getControl(self.SEEN_PROGRESS_IMAGE_ID).setWidth(int(self.seenratio*self.SEEN_PROGRESS_WIDTH))

        if self.failed:
            self.getControl(self.WATCH_BUTTON_ID).setEnabled(False)
            self.getControl(self.TOGGLE_BUTTON_ID).setEnabled(False)
            self.getControl(self.PROTECT_BUTTON_ID).setEnabled(False)
            self.setFocusId(self.DELETE_BUTTON_ID)
        else:
            self.setFocusId(self.WATCH_BUTTON_ID)

        self.setProperty('protected', self.object.protected and '1' or '')

        if self.object.protected:
            self.getControl(self.DELETE_BUTTON_ID).setEnabled(False)
        else:
            self.getControl(self.DELETE_BUTTON_ID).setEnabled(True)

    def onReInit(self):
        actiondialog.ActionDialog.onReInit(self)
        player.PLAYER.stopAndWait()
        self.action = 'dummy'

    def onAction(self, action):
        try:
            if action == xbmcgui.ACTION_NAV_BACK or action == xbmcgui.ACTION_PREVIOUS_MENU:
                if xbmc.getCondVisibility('ControlGroup({0}).HasFocus(0)'.format(self.DIALOG_GROUP_ID)):
                    self.setFocusId(self.BUTTONS_GROUP_ID)
                else:
                    self.doClose()
                return
        except:
            util.ERROR()

        actiondialog.ActionDialog.onAction(self, action)

    def onClick(self, controlID):
        if controlID == self.WATCH_BUTTON_ID:
            if self.seen:
                self.setProperty('dialog.message', 'Resume watching at {0}?'.format(util.durationToText(self.seen)))
                self.setProperty('dialog.top', 'Play From Start')
                self.setProperty('dialog.bottom', 'Resume')
                self.parentAction = 'watch'
                self.setFocusId(self.DIALOG_GROUP_ID)
                return
            else:
                self.action = 'watch'
        elif controlID == self.DIALOG_TOP_BUTTON_ID:
            if self.parentAction == 'watch':
                self.action = 'watch'
            elif self.parentAction == 'delete':
                self.action = 'delete'
                self.setProperty('delete.busy', '1')
                try:
                    if not self.doCallback():
                        self.doClose()
                finally:
                    self.setProperty('delete.busy', '')
                self.parentAction = ''
                return
            self.parentAction = ''
        elif controlID == self.DIALOG_BOTTOM_BUTTON_ID:
            if self.parentAction == 'watch':
                self.action = 'resume'
            else:
                self.parentAction = ''
                return
            self.parentAction = ''
        elif controlID == self.TOGGLE_BUTTON_ID:
            self.action = 'toggle'
            self.setProperty('button2.busy', '1')
            try:
                if not self.doCallback():
                    self.doClose()
            finally:
                self.setProperty('button2.busy', '')
            return
        elif controlID == self.PROTECT_BUTTON_ID:
            self.action = 'protect'
            self.setProperty('button3.busy', '1')
            try:
                if not self.doCallback():
                    self.doClose()
            finally:
                self.setProperty('button3.busy', '')
            return
        elif controlID == self.DELETE_BUTTON_ID:
            self.setProperty('dialog.message', 'Permanently delete this {0}?'.format(util.LOCALIZED_AIRING_TYPES[self.show.type].lower()))
            self.setProperty('dialog.top', 'Delete')
            self.setProperty('dialog.bottom', 'Cancel')
            self.parentAction = 'delete'
            return

        if not self.doCallback():
            self.doClose()

    def tick(self):
        self.doCallback()

    def doCallback(self):
        if not self.callback:
            return False

        action = self.action
        self.action = None
        changes = self.callback(self.object, action)

        if not changes:
            return False

        self.button2 = changes.get('button2') or self.button2
        self.button3 = changes.get('button3') or self.button3
        self.plot = changes.get('plot') or self.plot
        self.seen = changes.get('seen')
        self.seenratio = changes.get('seenratio')
        self.indicator = changes.get('indicator') or ''

        self.updateDisplayProperties()

        return True

    def updateDisplayProperties(self):
        self.setProperty('button2', self.button2)
        self.setProperty('button3', self.button3)
        self.setProperty('plot', self.plot)
        self.setProperty('indicator', self.indicator)
        self.setProperty('seen', self.seen and '1' or '')
        self.setProperty('protected', self.object.protected and '1' or '')
        if self.object.protected:
            self.getControl(self.DELETE_BUTTON_ID).setEnabled(False)
        else:
            self.getControl(self.DELETE_BUTTON_ID).setEnabled(True)

        self.getControl(self.SEEN_PROGRESS_IMAGE_ID).setWidth(int((self.seenratio or 0)*self.SEEN_PROGRESS_WIDTH))


def openDialog(
    title, info, preview, failed, button2, button3, plot=None, indicator=None,
    seen=None, seenratio=None, background=None, callback=None, obj=None, show=None
):

    w = RecordingDialog.open(
        title=title,
        info=info,
        plot=plot,
        preview=preview,
        failed=failed,
        indicator=indicator,
        button2=button2,
        button3=button3,
        seen=seen,
        seenratio=seenratio,
        background=background,
        callback=callback,
        object=obj,
        show=show
    )

    util.CRON.cancelReceiver(w)

    action = w.action
    del w
    return action
