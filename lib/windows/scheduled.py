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
        self.fillShows()

        self.setFilter()
        self.onWindowFocus()

    def onWindowFocus(self):
        self.setProperty('hide.menu', '1')
        guide.GuideWindow.onWindowFocus(self)
