import xbmc
import kodigui
from lib import util


class GuideShowWindow(kodigui.BaseDialog):
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
        self.start = kwargs.get('start')
        self.background = kwargs.get('background')
        self.button1 = kwargs.get('button1')
        self.button2 = kwargs.get('button2')
        self.titleIndicator = kwargs.get('title_indicator')
        self.callback = kwargs.get('callback')
        self.object = kwargs.get('object')
        self.action = None

    def onFirstInit(self):
        self.updateButtons()
        self.setProperty('number', str(self.number or ''))
        self.setProperty('title', self.title)
        self.setProperty('info', self.info)
        self.setProperty('plot', self.plot)
        self.setProperty('start', self.start)
        self.setProperty('background', self.background)
        self.setProperty('title.indicator', self.titleIndicator)

    def onReInit(self):
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()

    def onClick(self, controlID):
        if controlID == self.BUTTON1_ID:
            self.action = self.button1[0]
        elif controlID == self.BUTTON2_ID:
            self.action = self.button1[0]

        if self.callback:
            buttons = self.callback(self.object, self.action)
            if buttons:
                self.button1 = buttons.get('button1')
                self.button2 = buttons.get('button2')
                self.titleIndicator = buttons.get('title_indicator')
                self.updateButtons()
            else:
                self.doClose()
        else:
            self.doClose()

    def updateButtons(self):
        self.setProperty('button2', self.button2 and self.button2[1] or '')
        self.setProperty('button1', self.button1[1])
        self.setProperty('title.indicator', self.titleIndicator)


def openDialog(title, info, plot, start, button1, number=None, button2=None, title_indicator=None, background=None, callback=None, obj=None):
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

    action = w.action
    del w
    return action
