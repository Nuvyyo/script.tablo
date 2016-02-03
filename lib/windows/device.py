import xbmcgui
import kodigui
from lib import util

WM = None


class DeviceWindow(kodigui.BaseWindow):
    name = 'DEVICE'
    xmlFile = 'script-tablo-device.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    def onFirstInit(self):
        print 'DEVICE'

    def onAction(self, action):
        try:
            if action == xbmcgui.ACTION_MOVE_LEFT or action == xbmcgui.ACTION_NAV_BACK:
                WM.showMenu()
                return
            elif action == xbmcgui.ACTION_PREVIOUS_MENU:
                WM.finish()
                return
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)
