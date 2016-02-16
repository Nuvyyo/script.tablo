import xbmc
import kodigui
from lib import util


class GuideShowWindow(kodigui.BaseDialog, util.CronReceiver):
    name = 'GUIDE'
    xmlFile = 'script-tablo-action.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    BUTTON1_ID = 400
    BUTTON2_ID = 401

    def __init__(self, *args, **kwargs):
        kodigui.BaseDialog.__init__(self, *args, **kwargs)
        self.number = kwargs.get('number')
        self.title = kwargs.get('title')
        self.info = kwargs.get('info')
        self.plot = kwargs.get('plot')
        self.start = kwargs.get('start', '')
        self.background = kwargs.get('background')
        self.button1 = kwargs.get('button1')
        self.button2 = kwargs.get('button2')
        self.titleIndicator = kwargs.get('title_indicator', '')
        self.callback = kwargs.get('callback')
        self.object = kwargs.get('object')
        self.action = None
        util.CRON.registerReceiver(self)

    def onFirstInit(self):
        self.updateDisplayProperties()
        self.setProperty('number', str(self.number or ''))
        self.setProperty('title', self.title)
        self.setProperty('info', self.info)
        self.setProperty('plot', self.plot)
        self.setProperty('start', self.start)
        self.setProperty('background', self.background)
        self.setProperty('title.indicator', self.titleIndicator)
        self.setFocusId(self.BUTTON1_ID)

    def onReInit(self):
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()

    def onClick(self, controlID):
        if controlID == self.BUTTON1_ID:
            self.action = self.button1[0]
        elif controlID == self.BUTTON2_ID:
            self.action = self.button2[0]

        if not self.doCallback():
            self.doClose()

    def tick(self):
        self.doCallback()

    def doCallback(self):
        if not self.callback:
            return False

        action = self.action
        self.action = None
        changes = self.callback(self.object, action)

        if not changes:
            return False

        self.button1 = changes.get('button1')
        self.button2 = changes.get('button2')
        self.titleIndicator = changes.get('title_indicator', '')
        self.start = changes.get('start', '')

        self.updateDisplayProperties()

        return True

    def updateDisplayProperties(self):
        self.setProperty('button2', self.button2 and self.button2[1] or '')
        self.setProperty('button1', self.button1 and self.button1[1] or '')
        self.setProperty('title.indicator', self.titleIndicator)
        self.setProperty('start', self.start)


def openDialog(
    title, info, plot, start, button1,
    number=None, button2=None, title_indicator=None, background=None, callback=None, obj=None
):

    w = GuideShowWindow.open(
        number=number,
        title=title,
        info=info,
        plot=plot,
        start=start,
        background=background,
        button1=button1,
        button2=button2,
        title_indicator=title_indicator,
        callback=callback,
        object=obj
    )

    util.CRON.cancelReceiver(w)

    action = w.action
    del w
    return action
