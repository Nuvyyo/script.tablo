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
        self.last = None
        self.windows = {}
        self.waiting = False
        self.exit = False

    def open(self, window):
        self.last = self.current

        if self.current and self.current.name == window.name:
            return

        if self.current:
            self.current.doClose()

        if window.name in self.windows:
            self.current = self.windows[window.name]
            self.windows[window.name].show()
        else:
            self.current = window.generate() or window.create()
            self.windows[window.name] = self.current

    def windowWasLast(self, window):
        return window == self.last

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

            if not self.current:
                return

            if self.exit:
                return

    def disconnect(self):
        self.current = None
        self.showMenu()

        for key in self.windows.keys():
            self.windows[key].doClose()
            del self.windows[key]

        util.setGlobalProperty('menu.visible', '')
        self.menu.doClose()
        del self.menu

        self.menu = None

    def finish(self):
        if not xbmcgui.Dialog().yesno('Exit?', 'Close Tablo?'):
            return False

        self.saveCurrent()

        self.exit = True
        self.showMenu()
        self.current = None

        for key in self.windows.keys():
            self.windows[key].doClose()
            del self.windows[key]

        util.setGlobalProperty('menu.visible', '')
        self.menu.doClose()
        del self.menu
        self.menu = None

        return True

    def saveCurrent(self):
        if not self.current:
            return

        util.setSetting('window.last', self.current.name)


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
        self.loadFirstWindow()

    def onReInit(self):
        self.exit = True

    def onClick(self, controlID):
        if controlID == 101:
            self.openWindow(DeviceWindow)
        elif controlID == 102:
            self.openWindow(LiveTVWindow)
        elif controlID == 103:
            self.openWindow(RecordingsWindow)
        elif controlID == 104:
            self.openWindow(GuideWindow)
        elif controlID == 105:
            self.openWindow(ScheduledWindow)

    def onAction(self, action):
        try:
            if action == xbmcgui.ACTION_MOVE_RIGHT:
                self.onClick(self.getFocusId())
                return
            elif action == xbmcgui.ACTION_PREVIOUS_MENU or action == xbmcgui.ACTION_NAV_BACK:
                WM.finish()
                return
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def openWindow(self, window, hide_menu=True):
        WM.open(window)
        if hide_menu:
            WM.hideMenu()

    def loadFirstWindow(self):
        last = util.getSetting('window.last')
        if last:
            for window, ID in ((DeviceWindow, 101), (LiveTVWindow, 102), (RecordingsWindow, 103), (GuideWindow, 104), (ScheduledWindow, 105)):
                if window.name == last:
                    self.setFocusId(ID)
                    return self.openWindow(window, hide_menu=False)

        self.setFocusId(102)
        self.openWindow(LiveTVWindow, hide_menu=False)

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
