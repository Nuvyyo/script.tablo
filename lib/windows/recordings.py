import xbmc
import xbmcgui
import base
import actiondialog

from lib import util
from lib import backgroundthread
from lib import player

import guide


class RecordingsWindow(guide.GuideWindow):
    name = 'RECORDINGS'
    view = 'recordings'
    section = 'Recordings'

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

        w = RecordingShowWindow.open(show=show)
        if w.modified:
            self.fillShows()
        del w


class RecordingShowWindow(guide.GuideShowWindow):
    sectionAction = 'Delete...'

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
            'obj': airing
        }

        failed = airing.data['video_details']['state'] == 'failed'
        if airing.type == 'schedule':
            description = self.show.description or ''
            title = self.show.title
        else:
            description = airing.description or ''
            title = airing.title or self.show.title

        indicator = ''

        if failed:
            description += u'[CR][CR][COLOR FFC81010]Recording failed due to: {0}[/COLOR]'.format(airing.data['video_details']['error']['details'])
        else:
            if airing.data['user_info']['position']:
                left = airing.data['video_details']['duration'] - airing.data['user_info']['position']
                total = airing.data['video_details']['duration']
                kwargs['seen'] = airing.data['user_info']['position'] / float(total)
                description += '[CR][CR]Remaining: {0} of {1}'.format(util.durationToText(left), util.durationToText(total))
                indicator = 'indicators/seen_partial_hd.png'
            else:
                description += '[CR][CR]Length: {0}'.format(util.durationToText(airing.data['video_details']['duration']))
                indicator = 'indicators/seen_unwatched_hd.png'

        openDialog(
            title,
            info,
            description,
            airing.snapshot,
            failed,
            airing.watched and 'Mark Unwatched' or 'Mark Watched',
            airing.protected and 'Unprotect' or 'Protect',
            indicator,
            **kwargs
        )

        self.updateIndicators()

    def actionDialogCallback(self, obj, action):
        airing = obj
        changes = {}

        if action:
            if action == 'watch':
                player.PLAYER.playRecording(airing, show=self.show)
                # xbmc.Player().play(airing.watch().url)
                return None
            elif action == 'toggle':
                airing.markWatched(not airing.watched)
                self.modified = True
            elif action == 'protect':
                airing.markProtected(not airing.protected)
            elif action == 'delete':
                if xbmcgui.Dialog().yesno(
                    'Confirm', 'Permanently delete this {0}?'.format(util.LOCALIZED_AIRING_TYPES[self.show.type]), nolabel='Cancel', yeslabel='Delete'
                ):
                    self.modified = True
                    airing.delete()
                    return None

            if action == 'toggle':
                changes['button2'] = airing.watched and 'Mark Unwatched' or 'Mark Watched'
                changes['indicator'] = not airing.watched and 'indicators/seen_unwatched_hd.png' or ''
            elif action == 'protect':
                changes['button3'] = airing.protected and 'Unprotect' or 'Protect'

            changes['indicator'] = not airing.watched and 'indicators/seen_unwatched_hd.png' or ''

        return changes

    def scheduleButtonClicked(self, controlID):
        action = self.scheduleButtonActions.get(controlID)
        if not action or action != 'delete':
            return

        for item in self.airingsList:
            airing = item.dataSource.get('airing')
            if not airing:
                continue
            airing.delete()

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

        if airing.deleted:
            item.setProperty('disabled', '1')

    def updateIndicators(self):
        for item in self.airingsList:
            self.updateItemIndicators(item)

    def updateAiringItem(self, airing):
        print airing.data
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

    WATCH_BUTTON_ID = 400
    TOGGLE_BUTTON_ID = 401
    PROTECT_BUTTON_ID = 402
    DELETE_BUTTON_ID = 403

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
        self.background = kwargs.get('background')
        self.callback = kwargs.get('callback')
        self.object = kwargs.get('object')
        self.button2 = kwargs.get('button2')
        self.button3 = kwargs.get('button3')
        self.action = None
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

        if self.seen:
            self.getControl(self.SEEN_PROGRESS_IMAGE_ID).setWidth(int(self.seen*self.SEEN_PROGRESS_WIDTH))

        if self.failed:
            self.getControl(self.WATCH_BUTTON_ID).setEnabled(False)
            self.getControl(self.TOGGLE_BUTTON_ID).setEnabled(False)
            self.getControl(self.PROTECT_BUTTON_ID).setEnabled(False)
            self.setFocusId(self.DELETE_BUTTON_ID)
        else:
            self.setFocusId(self.WATCH_BUTTON_ID)

    def onClick(self, controlID):
        if controlID == self.WATCH_BUTTON_ID:
            self.action = 'watch'
        elif controlID == self.TOGGLE_BUTTON_ID:
            self.action = 'toggle'
        elif controlID == self.PROTECT_BUTTON_ID:
            self.action = 'protect'
        elif controlID == self.DELETE_BUTTON_ID:
            self.action = 'delete'

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
        self.indicator = changes.get('indicator') or ''

        self.updateDisplayProperties()

        return True

    def updateDisplayProperties(self):
        self.setProperty('button2', self.button2)
        self.setProperty('button3', self.button3)
        self.setProperty('indicator', self.indicator)


def openDialog(
    title, info, plot, preview, failed, button2, button3, indicator,
    seen=None, background=None, callback=None, obj=None
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
        background=background,
        callback=callback,
        object=obj
    )

    util.CRON.cancelReceiver(w)

    action = w.action
    del w
    return action
