import kodigui
from lib import tablo
from lib import util


class ConnectWindow(kodigui.BaseWindow):
    xmlFile = 'script-tablo-connect.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        self.exit = True

    def onFirstInit(self):
        self.deviceList = kodigui.ManagedControlList(self, 200, 1)
        self.searchButton = self.getControl(300)

        self.start()

    def onClick(self, controlID):
        if controlID == 300:
            self.showDevices()
        elif controlID == 200:
            mli = self.deviceList.getSelectedItem()
            tablo.API.selectDevice(mli.dataSource.ID)
            util.saveTabloDeviceID(mli.dataSource.ID)
            self.exit = False
            self.doClose()

    def start(self):
        self.showDevices()

    def showDevices(self):
        self.setProperty('tablo.found', '')
        self.deviceList.reset()
        tablo.API.discover()
        for device in tablo.API.devices.tablos:
            self.deviceList.addItem(kodigui.ManagedListItem(device.displayName, data_source=device))

        self.setProperty('initialized', '1')

        if tablo.API.foundTablos():
            self.setProperty('tablo.found', '1')
            self.setFocusId(200)
        else:
            self.setFocusId(300)
