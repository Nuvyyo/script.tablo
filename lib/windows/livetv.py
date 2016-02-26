import os
import xbmc
import xbmcgui
import kodigui
import actiondialog
import skin
import base
from lib import util

from lib import tablo
from lib.tablo import grid
from lib import player

WM = None

SKIN_PATH = skin.init()


class HalfHourData(object):
    def __init__(self):
        self.halfHour = None
        self.startHalfHour = None
        self.cutoff = None
        self.offsetHalfHours = 0
        self.update()

    def update(self):
        halfHour = self.getStartHalfHour()

        if halfHour == self.startHalfHour:
            return self

        self.decrementOffset()  # We've moved to the next half hour, but want to keep our position if we can

        self.startHalfHour = halfHour

        self.cutoff = halfHour + tablo.compat.datetime.timedelta(hours=24)

        self.updateOffsets()

        return self

    def updateOffsets(self):
        self.halfHour = self.startHalfHour + tablo.compat.datetime.timedelta(minutes=self.offsetHalfHours*30)
        self.maxHalfHour = self.halfHour + tablo.compat.datetime.timedelta(minutes=120)

    def incrementOffset(self):
        if self.offsetHalfHours == 45:
            return False

        self.offsetHalfHours += 1
        self.updateOffsets()

        return True

    def decrementOffset(self):
        if self.offsetHalfHours <= 0:
            return False

        self.offsetHalfHours -= 1
        self.updateOffsets()

        return True

    def getStartHalfHour(self):
        n = tablo.api.now()
        return n - tablo.compat.datetime.timedelta(minutes=n.minute % 30, seconds=n.second, microseconds=n.microsecond)


class LiveTVWindow(kodigui.BaseWindow, util.CronReceiver):
    name = 'LIVETV'
    xmlFile = 'script-tablo-livetv-generated.xml'
    path = SKIN_PATH
    theme = 'Main'

    GRID_GROUP_ID = 45
    TIME_INDICATOR_ID = 51

    @classmethod
    @base.tabloErrorHandler
    def generate(cls):
        paths = tablo.API.guide.channels.get()
        gen = EPGXMLGenerator(paths).create()
        new = cls.create()
        new.slotButtons = {}
        new.offButtons = {}
        new.chanLabelButtons = {}
        new.lastFocus = 100
        new.topRow = 0
        new.gen = gen
        return new

    def onFirstInit(self):
        self._showingDialog = False
        self.hhData = HalfHourData()

        self.baseY = self.getControl(45).getY()
        self.rowCount = len(self.gen.paths)
        self.rows = [[]] * len(self.gen.paths)
        self.channels = {}
        self.upDownDatetime = None

        self.gridGroup = self.getControl(self.GRID_GROUP_ID)
        self.timeIndicator = self.getControl(self.TIME_INDICATOR_ID)

        self.grid = grid.Grid(util.PROFILE, self.channelUpdatedCallback)

        self.setTimesHeader()
        self.updateTimeIndicator()

        self.getChannels()

        util.CRON.registerReceiver(self)

    def onReInit(self):
        if not self._showingDialog:
            self.grid.updatePending()

    def onAction(self, action):
        try:
            controlID = self.getFocusId()
            if action == xbmcgui.ACTION_MOVE_LEFT:
                self.setUpDownDatetime(controlID)

                if controlID in self.chanLabelButtons:
                    return self.guideLeft(True)
                elif controlID-1 in self.chanLabelButtons:
                    return self.guideLeft()
            elif action == xbmcgui.ACTION_MOVE_RIGHT:
                self.setUpDownDatetime(controlID)

                if self.selectionIsOffscreen() or 100 <= controlID <= self.gen.maxEnd:
                    return self.guideRight()
            elif action == xbmcgui.ACTION_MOVE_DOWN:
                if controlID > self.gen.maxEnd:
                    return self.guideNavDown()
            elif action == xbmcgui.ACTION_MOVE_UP:
                if controlID > self.gen.maxEnd:
                    return self.guideNavUp()
            elif action == xbmcgui.ACTION_NAV_BACK:
                WM.showMenu()
                return
            elif action == xbmcgui.ACTION_PREVIOUS_MENU:
                WM.finish()
                return
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def tick(self):
        self.updateTimeIndicator()
        self.updateSelectedDetails()

    def halfHour(self):
        self.hhData.update()
        self.fillChannels()

    def updateTimeIndicator(self):
        timePosSeconds = tablo.compat.timedelta_total_seconds(tablo.api.now() - self.hhData.halfHour)
        pos = int((timePosSeconds / 1800.0) * self.gen.HALF_HOUR_WIDTH)
        if pos >= 0:
            self.timeIndicator.setPosition(pos, 0)
            self.timeIndicator.setVisible(True)
        else:
            self.timeIndicator.setPosition(0, 0)
            self.timeIndicator.setVisible(False)

    def getAiringByControlID(self, controlID):
        return self.slotButtons.get(controlID)

    def setUpDownDatetime(self, controlID=None):
        controlID = controlID or self.getFocusId()
        selected = self.getAiringByControlID(controlID)
        self.upDownDatetime = selected and selected.datetime or None
        if not self.upDownDatetime:
            return

        if self.upDownDatetime < self.hhData.halfHour:
            self.upDownDatetime = self.hhData.halfHour

    def guideRight(self):
        if not self.hhData.incrementOffset():
            self.selectLastInRow()
            return

        airing = self.getSelectedAiring() or self.getAiringByControlID(self.lastFocus)
        row = self.getRow(self.lastFocus)
        self.fillChannels()

        if not self.selectAiring(airing, row):
            self.selectLastInRow()

    def guideLeft(self, at_edge=False, short_airing=None):
        if at_edge and self.hhData.offsetHalfHours == 0:
            self.setFocusId(self.lastFocus)
            WM.showMenu()
            return
        else:
            airing = short_airing or self.getSelectedAiring()

        if not short_airing:
            for controlID, rowAiring, short in self.rows[self.getRow()]:
                if airing == rowAiring:
                    if not short and not at_edge:
                        return
                    break
        if self.hhData.decrementOffset():
            self.fillChannels()

        # if airing:
        #     self.selectAiring(airing)
        # else:
        self.selectFirstInRow()

    def guideNavDown(self):
        row = self.getRow()
        if row == self.rowCount - 1:
            return

        if not self.upDownDatetime:
            self.setUpDownDatetime()

        row += 1

        for idx, (ID, airing, short) in enumerate(self.rows[row]):
            if not airing or airing.airingNow(self.upDownDatetime):
                if idx == 0 and short:
                    self.guideLeft(short_airing=airing)
                if not self.selectAiring(airing, row):
                    self.lastFocus = ID
                    self.setFocusId(ID)
                break
        else:
            return

        if row > self.topRow + 5:
            self.topRow += 1
            self.gridGroup.setPosition(self.gridGroup.getX(), self.baseY - self.topRow * 52)

    def guideNavUp(self):
        row = self.getRow()
        if row == 0:
            return

        if not self.upDownDatetime:
            self.setUpDownDatetime()

        row -= 1

        for idx, (ID, airing, short) in enumerate(self.rows[row]):
            if not airing or airing.airingNow(self.upDownDatetime):
                if idx == 0 and short:
                    self.guideLeft(short_airing=airing)
                if not self.selectAiring(airing, row):
                    self.lastFocus = ID
                    self.setFocusId(ID)
                break
        else:
            return

        if row < self.topRow + 1:
            if self.topRow > 0:
                control = self.getControl(45)
                self.topRow -= 1
                control.setPosition(control.getX(), self.baseY - self.topRow * 52)

    def getRow(self, controlID=None):
        controlID = controlID or self.getFocusId()
        row = ((controlID - self.gen.maxEnd+1)/8)
        return row

    def onClick(self, controlID):
        airing = self.getAiringByControlID(controlID)
        control = self.getControl(controlID)
        control.setSelected(not control.isSelected())
        if airing:
            self.airingClicked(airing)

    def onFocus(self, controlID):
        if controlID > self.gen.maxEnd:
            self.lastFocus = controlID

        self.updateSelectedDetails()

    def onWindowFocus(self):
        if not self.selectFirstInRow():
            self.setFocusId(self.gen.maxEnd + 3)  # Upper left grid button

    def updateSelectedDetails(self):
        airing = self.getSelectedAiring()
        if not airing:
            return

        self.setProperty('background', airing.background)
        self.setProperty('thumb', airing.thumb)
        self.setProperty('title', airing.title)

        self.setProperty('info', airing.data.get('title', ''))
        if airing.type == 'movie' and airing.quality_rating:
            info = []
            if airing.film_rating:
                info.append(airing.film_rating.upper())
            if airing.release_year:
                info.append(str(airing.release_year))

            self.setProperty('info', u' / '.join(info) + u' / ')
            self.setProperty('stars', str(airing.quality_rating/2))
            self.setProperty('half.star', str(airing.quality_rating % 2))
        else:
            self.setProperty('stars', '0')
            self.setProperty('half.star', '')

        if airing.type == 'series':
            info = []
            if airing.data.get('title'):
                info.append(airing.data.get('title'))
            if airing.data.get('season_number'):
                info.append('Season {0}'.format(airing.data['season_number']))
            if airing.data.get('episode_number'):
                info.append('Episode {0}'.format(airing.data['episode_number']))

            self.setProperty('info', u' / '.join(info))

        if airing.ended():
            secs = airing.secondsSinceEnd()
            start = 'Ended {0} ago'.format(util.durationToText(secs))
        else:
            secs = airing.secondsToStart()

            if secs < 1:
                start = 'Started {0} ago'.format(util.durationToText(secs*-1))
            else:
                start = 'Starts in {0}'.format(util.durationToText(secs))

        self.setProperty('start', start)

    def selectAiring(self, airing, row=None):
        row = row or self.getRow()
        if row < 0 or row >= len(self.rows):
            return False

        for controlID, rowAiring, short in self.rows[row]:
            if airing == rowAiring:
                break
        else:
            return False

        self.lastFocus = controlID
        self.setFocusId(controlID)
        return True

    def selectFirstInRow(self, row=None):
        row = row or self.getRow()
        if row < 0 or row >= len(self.rows):
            return False

        if self.rows[row][0][2]:
            controlID = self.rows[row][1][0]
        else:
            controlID = self.rows[row][0][0]

        self.lastFocus = controlID
        self.setFocusId(controlID)

        self.setFocusId(controlID)
        return True

    def selectLastInRow(self, row=None):
        row = row or self.getRow(self.lastFocus)
        if row < 0 or row >= len(self.rows):
            return False

        for i in range(len(self.rows[row])-1, -1, -1):
            controlID = self.rows[row][i][0]
            if xbmc.getCondVisibility('Control.IsVisible({0})'.format(controlID)):
                break
        else:
            controlID = self.rows[row][0][0]  # Shouldn't happen

        self.lastFocus = controlID
        self.setFocusId(controlID)

        self.setFocusId(controlID)
        return True

    def getSelectedAiring(self):
        return self.getAiringByControlID(self.getFocusId())

    def selectionIsOffscreen(self):
        return self.getFocusId() in self.offButtons

    def setTimesHeader(self, halfhour=None):
        for x in range(4):
            label = self.getControl(40 + x)
            label.setLabel((self.hhData.halfHour + tablo.compat.datetime.timedelta(minutes=x * 30)).strftime('%I:%M %p').lstrip('0'))

    def channelUpdatedCallback(self, channel):
        genData = self.gen.channels[channel.path]
        ID = genData['label']
        self.chanLabelButtons[ID] = True
        self.getControl(ID).setLabel(
            '{0} [B]{1}-{2}[/B]'.format(channel.call_sign, channel.major, channel.minor)
        )

        self.updateChannelAirings(channel.path)

    def updateGridItem(self, airing, ID):
        control = self.getControl(ID)
        if airing.scheduled:
            if airing.conflicted:
                util.setGlobalProperty('badge.color.{0}'.format(ID), 'FFD93A34')
            else:
                util.setGlobalProperty('badge.color.{0}'.format(ID), 'FFFF8000')
            control.setSelected(True)
        else:
            control.setSelected(False)

    def updateChannelAirings(self, path):
        genData = self.gen.channels[path]

        totalwidth = 0

        row = []
        slot = -1
        atEnd = False

        for slot, airing in enumerate(self.grid.airings(self.hhData.halfHour, min(self.hhData.maxHalfHour, self.hhData.cutoff), path)):
            try:
                ID = genData['slots'][slot]
            except IndexError:
                break

            self.slotButtons[ID] = airing
            control = self.getControl(ID)

            if airing.scheduled:
                if airing.conflicted:
                    util.setGlobalProperty('badge.color.{0}'.format(ID), 'FFD93A34')
                else:
                    util.setGlobalProperty('badge.color.{0}'.format(ID), 'FFFF8000')
                control.setSelected(True)
            else:
                control.setSelected(False)

            if airing.airingNow(self.hhData.halfHour):
                duration = airing.secondsToEnd(start=self.hhData.halfHour)
            else:
                duration = airing.duration

            row.append((ID, airing, duration < 1800 and True or False))

            if airing.datetimeEnd >= self.hhData.cutoff:
                atEnd = True
                if airing.datetimeEnd > self.hhData.cutoff:
                    duration -= tablo.compat.timedelta_total_seconds(airing.datetimeEnd - self.hhData.cutoff)

            if airing.qualifiers:
                new = 'new' in airing.qualifiers and u'[COLOR FF2F8EC0]NEW:[/COLOR] ' or u''
                live = 'live' in airing.qualifiers and u'[COLOR FF2F8EC0]LIVE:[/COLOR] ' or u''
                label = u'{0}{1}'.format(new or live, airing.title)
            else:
                label = airing.title

            width = int((duration/1800.0)*self.gen.HALF_HOUR_WIDTH)
            save = width
            if totalwidth > 1110:
                self.offButtons[ID] = True
                control.setVisible(False)
            else:
                if totalwidth + width > 1110:
                    width = 1110 - totalwidth
                    if width < self.gen.HALF_HOUR_WIDTH:
                        self.offButtons[ID] = True
                control.setVisible(True)

            totalwidth += save

            control.setRadioDimension(width-31, 1, 30, 30)
            control.setWidth(width)
            control.setLabel(label)

        if slot == -1 or (totalwidth < 1110 and not atEnd):
            slot += 1
            ID = genData['slots'][slot]

            util.setGlobalProperty('badge.color.{0}'.format(ID), '')

            control = self.getControl(ID)

            control.setSelected(False)
            control.setWidth(1110 - totalwidth)
            control.setLabel('Loading...')
            control.setVisible(True)
            self.slotButtons[ID] = None
            row.append((ID, None, False))

        for slot in range(slot+1, 6):
            ID = genData['slots'][slot]

            self.setProperty('badge.color.{0}'.format(ID), '')

            control = self.getControl(ID)
            control.setSelected(False)
            control.setVisible(False)
            control.setLabel('')
            self.slotButtons[ID] = None

        self.rows[self.gen.paths.index(path)] = row

    @base.tabloErrorHandler
    def getChannels(self):
        self.grid.getChannels(self.gen.paths)

    def fillChannels(self):
        self.slotButtons = {}
        self.offButtons = {}
        self.rows = [[]] * len(self.gen.paths)

        self.setTimesHeader()
        self.updateTimeIndicator()

        for path in self.gen.paths:
            self.updateChannelAirings(path)

    def setDialogButtons(self, airing, arg_dict):
        if airing.gridAiring.airingNow():
            arg_dict['button1'] = ('watch', 'Watch')
            if airing.gridAiring.scheduled:
                arg_dict['button2'] = ('unschedule', "Don't Record {0}".format(util.LOCALIZED_AIRING_TYPES[airing.type.upper()]))
                arg_dict['title_indicator'] = 'indicators/rec_pill_hd.png'
            else:
                arg_dict['button2'] = ('record', 'Record {0}'.format(util.LOCALIZED_AIRING_TYPES[airing.type.upper()]))
        else:
            if airing.gridAiring.scheduled:
                arg_dict['button1'] = ('unschedule', "Don't Record {0}".format(util.LOCALIZED_AIRING_TYPES[airing.type.upper()]))
                arg_dict['title_indicator'] = 'indicators/rec_pill_hd.png'
            else:
                arg_dict['button1'] = ('record', 'Record {0}'.format(util.LOCALIZED_AIRING_TYPES[airing.type.upper()]))

    @base.dialogFunction
    def airingClicked(self, airing):
        # while not airing and backgroundthread.BGThreader.working() and not xbmc.abortRequested:
        #     xbmc.sleep(100)
        #     airing = item.dataSource.get('airing')
        info = 'Channel {0} {1} on {2} from {3} to {4}'.format(
            airing.gridAiring.displayChannel(),
            airing.gridAiring.network,
            airing.gridAiring.displayDay(),
            airing.gridAiring.displayTimeStart(),
            airing.gridAiring.displayTimeEnd()
        )

        kwargs = {
            'number': airing.gridAiring.number,
            'background': airing.background,
            'callback': self.actionDialogCallback,
            'obj': airing
        }

        self.setDialogButtons(airing, kwargs)

        secs = airing.gridAiring.secondsToStart()

        if secs < 1:
            start = 'Started {0} ago'.format(util.durationToText(secs*-1))
        else:
            start = 'Starts in {0}'.format(util.durationToText(secs))

        actiondialog.openDialog(
            airing.title,
            info, airing.gridAiring.description,
            start,
            **kwargs
        )
        # self.updateIndicators()

    def actionDialogCallback(self, obj, action):
        airing = obj
        changes = {}

        if action:
            if action == 'watch':
                error = player.PLAYER.playAiringChannel(airing.gridAiring)
                if error:
                    xbmcgui.Dialog().ok('Failed', 'Failed to play channel:', ' ', str(error))
            elif action == 'record':
                airing.schedule()
                self.grid.updateChannelAiringData(path=airing.gridAiring.channel['path'])
            elif action == 'unschedule':
                airing.schedule(False)
                self.grid.updateChannelAiringData(path=airing.gridAiring.channel['path'])

            self.updateGridItem(airing, self.getFocusId())

        if airing.gridAiring.ended():
            secs = airing.gridAiring.secondsSinceEnd()
            changes['start'] = 'Ended {0} ago'.format(util.durationToText(secs))
        else:
            self.setDialogButtons(airing, changes)

            secs = airing.gridAiring.secondsToStart()

            if secs < 1:
                start = 'Started {0} ago'.format(util.durationToText(secs*-1))
            else:
                start = 'Starts in {0}'.format(util.durationToText(secs))

            changes['start'] = start

        return changes


class EPGXMLGenerator(object):
    BASE_ID = 100
    HALF_HOUR_WIDTH = 320

    BASE_XML_PATH = os.path.join(
        SKIN_PATH, 'resources', 'skins', 'Main', '720p', 'script-tablo-livetv.xml'
    )

    OUTPUT_PATH = os.path.join(
        SKIN_PATH, 'resources', 'skins', 'Main', '720p', 'script-tablo-livetv-generated.xml'
    )

    CHANNEL_BASE_XML = '''
                <control type="grouplist" id="{ID}">
                    <hitrect x="2000" y="2000" w="5" h="5"/>
                    <posy>{POSY}</posy>
                    <onleft>50</onleft>
                    <onright>50</onright>
                    <height>52</height>
                    <width>1300</width>
                    <orientation>horizontal</orientation>
                    <itemgap>0</itemgap>
                    <usecontrolcoords>true</usecontrolcoords>
                    {AIRINGS_XML}
                </control>
'''

    AIRING_BASE_XML = '''
                    <control type="radiobutton" id="{ID}">
                        <posx>0</posx>
                        <posy>0</posy>
                        <width>{WIDTH}</width>
                        <height>52</height>
                        <font>font16</font>
                        <textcolor>C8E8E8E8</textcolor>
                        <focusedcolor>FF000000</focusedcolor>
                        <align>left</align>
                        <aligny>center</aligny>
                        <texturefocus colordiffuse="FFE8E8E8" border="2">script-tablo-epg_slot.png</texturefocus>
                        <texturenofocus colordiffuse="FF101924" border="2">script-tablo-epg_slot.png</texturenofocus>
    <textureradioonfocus colordiffuse="$INFO[Window(10000).Property(script.tablo.badge.color.{ID})]">livetv/livetv_badge_blank_hd.png</textureradioonfocus>
    <textureradioonnofocus colordiffuse="$INFO[Window(10000).Property(script.tablo.badge.color.{ID})]">livetv/livetv_badge_blank_hd.png</textureradioonnofocus>
                        <textureradioofffocus>-</textureradioofffocus>
                        <textureradiooffnofocus>-</textureradiooffnofocus>
                        <radiowidth>30</radiowidth>
                        <radioheight>30</radioheight>
                        <textoffsetx>16</textoffsetx>
                        <textoffsety>0</textoffsety>
                        <label></label>
                        <scroll>false</scroll>
                    </control>
'''

    END_BUTTON_XML = '''
                    <control type="button" id="{0}">
                        <width>1</width>
                        <height>52</height>
                        <font>font16</font>
                        <textcolor>000000</textcolor>
                        <focusedcolor>000000</focusedcolor>
                        <texturefocus>-</texturefocus>
                        <texturenofocus>-</texturenofocus>
                        <label> </label>
                        <scroll>false</scroll>
                    </control>
'''

    CHANNEL_LABEL_BASE_XML = '''
                    <control type="button" id="{ID}">
                        <width>180</width>
                        <height>52</height>
                        <font>font13</font>
                        <textcolor>FFE8E8E8</textcolor>
                        <focusedcolor>FFE8E8E8</focusedcolor>
                        <align>right</align>
                        <aligny>center</aligny>
                        <texturefocus colordiffuse="FF000000">script-tablo-white_square.png</texturefocus>
                        <texturenofocus colordiffuse="FF000000">script-tablo-white_square.png</texturenofocus>
                        <textoffsetx>10</textoffsetx>
                        <textoffsety>0</textoffsety>
                        <label></label>
                        <scroll>false</scroll>
                    </control>
'''

    def __init__(self, paths):
        self.paths = paths
        self.currentID = self.BASE_ID - 1
        self.channels = {}
        self.maxEnd = 0

    def nextID(self):
        self.currentID += 1
        return self.currentID

    def setStartID(self, start):
        self.currentID = start - 1

    def create(self):
        self.setStartID(100 + len(self.paths))
        self.maxEnd = 99 + len(self.paths)
        xml = ''
        posy = 0
        for idx, p in enumerate(self.paths):
            chanID = self.nextID()
            chanLabelID = self.nextID()
            airingsXML = ''
            slots = []
            airingsXML += self.CHANNEL_LABEL_BASE_XML.format(ID=chanLabelID)
            for x in range(6):
                ID = self.nextID()
                slots.append(ID)
                util.setGlobalProperty('badge.color.{0}'.format(ID), '')
                airingsXML += self.AIRING_BASE_XML.format(ID=ID, WIDTH=self.HALF_HOUR_WIDTH)

            airingsXML += self.END_BUTTON_XML.format(100+idx)

            xml += self.CHANNEL_BASE_XML.format(ID=chanID, AIRINGS_XML=airingsXML, POSY=posy)
            data = {'ID': chanID, 'label': chanLabelID, 'slots': slots}

            self.channels[p] = data

            posy += 52

        with open(self.BASE_XML_PATH, 'r') as f:
            with open(self.OUTPUT_PATH, 'w') as o:
                o.write(f.read().replace('<!-- GENERATED CONTENT -->', xml))

        return self
