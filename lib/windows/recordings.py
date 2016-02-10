import xbmcgui
import kodigui

from lib import util

WM = None


class RecordingsWindow(kodigui.BaseWindow):
    name = 'RECORDINGS'
    xmlFile = 'script-tablo-recordings.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    types = (
        (None, 'All'),
        ('SERIES', 'TV Shows'),
        ('MOVIES', 'Movies'),
        ('SPORTS', 'Sports')
    )

    def onFirstInit(self):
        print 'RECORDINGS'

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
