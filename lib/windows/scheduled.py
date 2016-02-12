import xbmc
import base
import actiondialog

from lib import util
from lib import backgroundthread

import guide


class ScheduledWindow(guide.GuideWindow):
    name = 'SCHEDULED'
    view = 'guide'
    state = 'scheduled'
    section = 'Scheduled'

    types = (
        (None, ''),
        ('SERIES', ''),
        ('MOVIES', ''),
        ('SPORTS', '')
    )

    def onFirstInit(self):
        self.setProperty('hide.menu', '1')
        guide.GuideWindow.onFirstInit(self)

    def onWindowFocus(self):
        self.setProperty('hide.menu', '1')
        guide.GuideWindow.onWindowFocus(self)

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

        RecordingShowWindow.open(show=show)


class RecordingShowWindow(guide.GuideShowWindow):
    sectionAction = 'Delete...'

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

    def updateItemIndicators(self, item):
        # airing = item.dataSource['airing']
        # if not airing:
        #     return
        # item.setProperty('badge', airing.scheduled and 'livetv/livetv_badge_scheduled_hd.png' or '')
        pass

    def updateIndicators(self):
        for item in self.airingsList:
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
