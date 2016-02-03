import kodigui
from lib import util


class BackgroundWindow(kodigui.BaseWindow):
    xmlFile = 'script-tablo-background.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        self.exit = True
