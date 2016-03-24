import xbmcgui
import kodigui

from lib import tablo
from lib import util

WM = None


class DeviceWindow(kodigui.BaseWindow):
    name = 'DEVICE'
    xmlFile = 'script-tablo-device.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    DISCONNECT_BUTTON_ID = 100
    DRIVE_WIDTH = 680

    def onFirstInit(self):
        self.setProperty('device.name', tablo.API.device.displayName)
        try:
            hdinfo = tablo.API.server.harddrives.get()
        except:
            hdinfo = None
            util.ERROR()

        if hdinfo:
            controlID = 200
            for i, drive in enumerate(hdinfo):
                if not drive.get('connected'):
                    continue

                if controlID > 200:
                    break

                self.setProperty('drive.{0}'.format(i), drive['name'])
                self.setProperty('drive.{0}.used'.format(i), '{0} Used'.format(util.simpleSize(drive['usage'])))
                self.setProperty('drive.{0}.left'.format(i), '{0} Available'.format(util.simpleSize(drive['size'] - drive['usage'])))
                control = self.getControl(controlID)
                w = int((drive['usage'] / float(drive['size'])) * self.DRIVE_WIDTH)
                control.setWidth(w)
                control = self.getControl(controlID+1)
                control.setWidth(w - 10)
                controlID += 100

        if not tablo.API.serverInfo:
            tablo.API.getServerInfo()

        self.setProperty('firmware', tablo.API.serverInfo.get('version', '[COLOR FFFF8080]Failed to get device information[/COLOR]'))
        self.setProperty('ip.address', tablo.API.serverInfo.get('local_address', ''))
        si = tablo.API.serverInfo.get('server_id', '')
        if si:
            self.setProperty('mac.address', '{0}:{1}:{2}:{3}:{4}:{5}'.format(si[4:6], si[6:8], si[8:10], si[10:12], si[12:14], si[14:16]))

        self.setProperty('addon.version', util.ADDON.getAddonInfo('version'))

    def onWindowFocus(self):
        print 'tttttesdfsf'
        try:
            hdinfo = tablo.API.server.harddrives.get()
        except:
            hdinfo = None
            util.ERROR()

        if hdinfo:
            controlID = 200
            for i, drive in enumerate(hdinfo):
                if not drive.get('connected'):
                    continue

                if controlID > 200:
                    break

                self.setProperty('drive.{0}'.format(i), drive['name'])
                self.setProperty('drive.{0}.used'.format(i), '{0} Used'.format(util.simpleSize(drive['usage'])))
                self.setProperty('drive.{0}.left'.format(i), '{0} Available'.format(util.simpleSize(drive['size'] - drive['usage'])))
                control = self.getControl(controlID)
                w = int((drive['usage'] / float(drive['size'])) * self.DRIVE_WIDTH)
                control.setWidth(w)
                control = self.getControl(controlID+1)
                control.setWidth(w - 10)
                controlID += 100

    def onAction(self, action):
        try:
            if action in(xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
                WM.showMenu()
                return
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def onClick(self, controlID):
        if controlID == self.DISCONNECT_BUTTON_ID:
            util.clearTabloDeviceID()
            WM.disconnect()
