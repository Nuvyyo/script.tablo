import guide


class ScheduledWindow(guide.GuideWindow):
    name = 'SCHEDULED'
    view = 'guide'
    state = 'scheduled'
    section = 'Scheduled'

    types = (
        (None, ''),
        ('SERIES', ''),
        ('MOVIES', ''),
        ('SPORTS', '')
    )

    def onFirstInit(self):
        self.setProperty('hide.menu', '1')
        guide.GuideWindow.onFirstInit(self)

    def onReInit(self):
        self.setFilter()
        self.setProperty('hide.menu', '1')

        if not guide.WM.windowWasLast(self):
            self.fillShows()

        self.setFocusId(self.SHOW_GROUP_ID)

    def onFocus(self, controlID):
        if controlID == 50:
            self.setFocusId(self.SHOW_GROUP_ID)
            guide.WM.showMenu()
            return

    def onWindowFocus(self):
        guide.GuideWindow.onWindowFocus(self)
