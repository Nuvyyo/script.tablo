import guide


class ScheduledWindow(guide.GuideWindow):
    name = 'SCHEDULED'
    view = 'guide'
    state = 'scheduled'
    section = 'Scheduled'
    emptyMessage = ('No Shows to Display',)

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
            self.setShowFocus()
            guide.WM.showMenu()
            return
