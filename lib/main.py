import kodigui
import util
import tablo


class ConnectWindow(kodigui.BaseWindow):
    xmlFile = 'script-tablo-connect.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    def onFirstInit(self):
        self.deviceList = kodigui.ManagedControlList(self, 200, 1)
        self.searchButton = self.getControl(300)

        self.start()

    def onClick(self, controlID):
        if controlID == 300:
            self.showDevices()

    def start(self):
        self.showDevices()

    def showDevices(self):
        self.setProperty('tablo.found', '')
        self.deviceList.reset()
        tablo.API.discover()
        for device in tablo.API.devices.tablos:
            self.deviceList.addItem(kodigui.ManagedListItem(device.name, data_source=device))

        self.setProperty('initialized', '1')

        if tablo.API.foundTablos():
            self.setProperty('tablo.found', '1')
            self.setFocusId(200)
        else:
            self.setFocusId(300)


def start():
    ConnectWindow.open()
