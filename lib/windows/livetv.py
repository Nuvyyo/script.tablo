import xbmcgui
import kodigui
from lib import util

WM = None


class LiveTVWindow(kodigui.BaseWindow):
    name = 'LIVETV'
    xmlFile = 'script-tablo-livetv.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    def onFirstInit(self):
        print 'LIVETV'

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
