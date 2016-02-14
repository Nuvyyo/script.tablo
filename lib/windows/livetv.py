import os
import xbmc
import xbmcgui
import kodigui
from lib import util

from lib import tablo

WM = None


class LiveTVWindow(kodigui.BaseWindow):
    name = 'LIVETV'
    xmlFile = 'script-tablo-livetv-generated.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    GRID_GROUP_ID = 45

    @classmethod
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
        self.offsetHalfHour = 0
        self.baseY = self.getControl(45).getY()
        self.rowCount = len(self.gen.paths)
        self.rows = []
        self.channels = {}
        self.upDownDatetime = None

        self.gridGroup = self.getControl(self.GRID_GROUP_ID)

        self.fillChannels()

    def onAction(self, action):
        try:
            controlID = self.getFocusId()
            if action == xbmcgui.ACTION_MOVE_LEFT:
                self.setUpDownDatetime(controlID)

                if controlID in self.chanLabelButtons:
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

    def setUpDownDatetime(self, controlID=None):
        controlID = controlID or self.getFocusId()
        selected = self.slotButtons.get(controlID)
        self.upDownDatetime = selected and selected.datetime or None
        if not self.upDownDatetime:
            return

        currentStartHalfHour = self.getStartHalfHour() + tablo.compat.datetime.timedelta(minutes=self.offsetHalfHour*30)
        if self.upDownDatetime < currentStartHalfHour:
            self.upDownDatetime = currentStartHalfHour

    def guideRight(self):
        self.offsetHalfHour += 1
        if self.offsetHalfHour > 45:
            self.offsetHalfHour = 45
            self.setFocusId(self.lastFocus)
            return

        self.fillChannels()
        controlID = self.getFocusId()
        if controlID <= self.gen.maxEnd:
            controlID = self.lastFocus
        if not xbmc.getCondVisibility('Control.IsVisible({0})'.format(controlID)) or controlID in self.offButtons:
            while not xbmc.getCondVisibility('Control.IsVisible({0})'.format(controlID)) or controlID in self.offButtons:
                controlID -= 1
        else:
            while xbmc.getCondVisibility('Control.IsVisible({0})'.format(controlID)) and controlID not in self.offButtons:
                controlID += 1
            controlID -= 1

        self.lastFocus = controlID
        self.setFocusId(controlID)
        return

    def guideLeft(self):
        if self.offsetHalfHour == 0:
            WM.showMenu()
            return

        self.offsetHalfHour -= 1
        self.fillChannels()

        controlID = self.getFocusId()+1

        self.lastFocus = controlID
        self.setFocusId(controlID)

    def guideNavDown(self):
        row = self.getRow()
        if row == self.rowCount - 1:
            return

        if not self.upDownDatetime:
            self.setUpDownDatetime()

        row += 1

        for ID, airing in self.rows[row]:
            if airing.airingNow(self.upDownDatetime):
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

        for ID, airing in self.rows[row]:
            if airing.airingNow(self.upDownDatetime):
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
        airing = self.slotButtons.get(controlID)
        if airing:
            print '{0} {1} {2}'.format(controlID, repr(airing.title), self.getControl(controlID).getWidth())

    def onFocus(self, controlID):
        if controlID > self.gen.maxEnd:
            self.lastFocus = controlID

        airing = self.getSelectedAiring()
        if airing:
            print '{0} - {1} ({2})'.format(airing.datetime, airing.datetimeEnd, self.upDownDatetime)
            self.setProperty('background', airing.background)

    def onWindowFocus(self):
        if self.getFocusId() in self.chanLabelButtons:
            self.setFocusId(self.getFocusId() + 1)  # Grid button to the left ot the last selected label
        else:
            self.setFocusId(self.gen.maxEnd + 3)  # Upper left grid button

    def getSelectedAiring(self):
        return self.slotButtons.get(self.getFocusId())

    def selectionIsOffscreen(self):
        return self.getFocusId() in self.offButtons

    def getStartHalfHour(self):
        n = tablo.api.now()
        return n - tablo.compat.datetime.timedelta(minutes=n.minute % 30, seconds=n.second, microseconds=n.microsecond)

    def fillChannels(self):
        self.slotButtons = {}
        self.offButtons = {}
        self.rows = []

        if not self.channels:
            self.chanLabelButtons = {}

            channels = tablo.API.batch.post(self.gen.paths)
            for path in self.gen.paths:
                channel = channels[path]['channel']
                genData = self.gen.channels[path]
                ID = genData['label']
                self.chanLabelButtons[ID] = True
                self.getControl(ID).setLabel(
                    '{0} [B]{1}-{2}[/B]'.format(channel.get('call_sign', ''), channel.get('major', ''), channel.get('minor', ''))
                )

        halfhour = self.getStartHalfHour()
        cutoff = halfhour + tablo.compat.datetime.timedelta(hours=24)

        halfhour += tablo.compat.datetime.timedelta(minutes=self.offsetHalfHour*30)

        for x in range(4):
            label = self.getControl(40 + x)
            label.setLabel((halfhour + tablo.compat.datetime.timedelta(minutes=x * 30)).strftime('%I:%M %p').lstrip('0'))

        for path in self.gen.paths:
            genData = self.gen.channels[path]

            if path in self.channels:
                data = self.channels[path]
            else:
                data = tablo.API.views.livetv.channels(channels[path]['object_id']).get(duration=86400)
                self.channels[path] = data

            totalwidth = 0
            start = 0
            while True:
                airing = tablo.Airing(data[start])
                if airing.airingNow(halfhour):
                    break
                start += 1
            else:
                continue

            row = []

            for slot, i in enumerate(range(start, start+6)):
                try:
                    airing = tablo.Airing(data[i])
                except IndexError:
                    airing = None

                ID = genData['slots'][slot]

                if not airing or airing.datetime >= cutoff:
                    control = self.getControl(ID)
                    control.setVisible(False)
                    control.setLabel('')
                    self.slotButtons[ID] = None
                    continue

                row.append((ID, airing))

                self.slotButtons[ID] = airing
                control = self.getControl(ID)
                if airing.airingNow(halfhour):
                    duration = airing.secondsToEnd(start=halfhour)
                else:
                    duration = airing.duration

                if airing.datetimeEnd > cutoff:
                    duration -= tablo.compat.timedelta_total_seconds(airing.datetimeEnd - cutoff)

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
                control.setWidth(width)
                control.setLabel(airing.title)

            self.rows.append(row)


class EPGXMLGenerator(object):
    BASE_ID = 100
    HALF_HOUR_WIDTH = 320

    BASE_XML_PATH = os.path.join(
        xbmc.translatePath(util.ADDON.getAddonInfo('path')).decode('utf-8'), 'resources', 'skins', 'Main', '720p', 'script-tablo-livetv.xml'
    )

    OUTPUT_PATH = os.path.join(
        xbmc.translatePath(util.ADDON.getAddonInfo('path')).decode('utf-8'), 'resources', 'skins', 'Main', '720p', 'script-tablo-livetv-generated.xml'
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
                    <control type="button" id="{ID}">
                        <width>{WIDTH}</width>
                        <height>52</height>
                        <font>font16</font>
                        <textcolor>FFE8E8E8</textcolor>
                        <focusedcolor>FF000000</focusedcolor>
                        <align>left</align>
                        <aligny>center</aligny>
                        <texturefocus colordiffuse="FFE8E8E8" border="2">script-tablo-epg_slot.png</texturefocus>
                        <texturenofocus colordiffuse="FF101924" border="2">script-tablo-epg_slot.png</texturenofocus>
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
