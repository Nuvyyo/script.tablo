import xbmc
import xbmcgui
import kodigui
from lib import util

import device
import livetv
import recordings
import guide
import scheduled

from background import BackgroundWindow
from connect import ConnectWindow


class WindowManager(xbmc.Monitor):
    def __init__(self):
        util.setGlobalProperty('menu.visible', '1')
        self.menu = None
        self.current = None
        self.windows = {}
        self.waiting = False
        self.exit = False

    def open(self, window):
        if self.current:
            self.current.doClose()

        if window.name in self.windows:
            self.windows[window.name].show()
        else:
            self.current = window.generate() or window.create()
            self.windows[window.name] = self.current

    def showMenu(self):
        self.waiting = False

    def hideMenu(self):
        if not self.current:
            return
        util.setGlobalProperty('menu.visible', '')
        self.menu.doClose()
        self.current.onWindowFocus()

    def waitOnWindow(self):
        self.waiting = True
        while self.waiting and not self.waitForAbort(0.1):
            pass

    def start(self):
        self.menu = MenuDialog.create()
        while True:
            util.setGlobalProperty('menu.visible', '1')
            self.menu.modal()

            if not self.current:
                return

            self.waitOnWindow()

            if self.exit:
                return

    def finish(self):
        if not xbmcgui.Dialog().yesno('Exit?', 'Close Tablo?'):
            return False

        self.exit = True
        self.showMenu()
        self.current = None

        for w in self.windows.values():
            w.doClose()

        self.windows = {}

        util.setGlobalProperty('menu.visible', '')
        self.menu.doClose()

        return True

WM = WindowManager()


class MenuDialog(kodigui.BaseDialog):
    name = 'MENU'
    xmlFile = 'script-tablo-menu.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    def onFirstInit(self):
        self.deviceButton = self.getControl(101)
        self.liveTVButton = self.getControl(102)
        self.recordingsButton = self.getControl(103)
        self.guideButton = self.getControl(104)
        self.scheduledButton = self.getControl(105)

    def onReInit(self):
        self.exit = True

    def onClick(self, controlID):
        if controlID == 101:
            WM.open(DeviceWindow)
        elif controlID == 102:
            WM.open(LiveTVWindow)
        elif controlID == 103:
            WM.open(RecordingsWindow)
            WM.hideMenu()
        elif controlID == 104:
            WM.open(GuideWindow)
            WM.hideMenu()
        elif controlID == 105:
            WM.open(ScheduledWindow)
            WM.hideMenu()

    def onAction(self, action):
        try:
            if action == xbmcgui.ACTION_MOVE_RIGHT:
                WM.hideMenu()
                return
            elif action == xbmcgui.ACTION_PREVIOUS_MENU or action == xbmcgui.ACTION_NAV_BACK:
                WM.finish()
                return
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

device.WM = WM
livetv.WM = WM
recordings.WM = WM
guide.WM = WM
scheduled.WM = WM

DeviceWindow = device.DeviceWindow
LiveTVWindow = livetv.LiveTVWindow
RecordingsWindow = recordings.RecordingsWindow
GuideWindow = guide.GuideWindow
ScheduledWindow = scheduled.ScheduledWindow

ConnectWindow  # Hides IDE warnings
BackgroundWindow  # Hides IDE warnings
