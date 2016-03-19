import threading
import xbmc
import xbmcgui
import kodigui
from lib import tablo
from lib import util


class ConnectWindow(kodigui.BaseWindow):
    xmlFile = 'script-tablo-connect.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        self.updating = kwargs.get('updating')
        self.exit = True
        self.abort = False

    def onFirstInit(self):
        if self.updating and len(tablo.API.devices.tablos) < 2:
            name = tablo.API.device and tablo.API.device.name or 'Tablo'
            self.setProperty('updating', name)
            self.setProperty('tablo.found', '1')
            self.setProperty('initialized', '1')
            self._waitForUpdate()
            self.doClose()
        else:
            if self.updating:
                name = tablo.API.device and tablo.API.device.name or 'Tablo'
                xbmcgui.Dialog().ok('Updating', '{0} is currently updating'.format(name))
            self.setProperty('updating', '')
            self.setProperty('tablo.found', '')
            self.setProperty('initialized', '')
            self.connect()

    def connect(self):
        self.deviceList = kodigui.ManagedControlList(self, 200, 1)
        self.searchButton = self.getControl(300)

        self.start()

    def waitForUpdate(self):
        threading.Thread(target=self._waitForUpdate).start()

    def _waitForUpdate(self):
        m = xbmc.Monitor()
        while not m.waitForAbort(1):
            if self.abort:
                util.DEBUG_LOG('Exited while waiting for update')
                break

            try:
                tablo.API.server.tuners.get()
                break
            except tablo.APIError, e:
                if e.code == 503:
                    continue
                break
            except tablo.ConnectionError:
                continue
            except:
                util.ERROR()
                break
        else:
            util.DEBUG_LOG('Shutdown while waiting for update')

    def onAction(self, action):
        try:
            if action == xbmcgui.ACTION_NAV_BACK or action == xbmcgui.ACTION_PREVIOUS_MENU:
                self.abort = True
                self.doClose()
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def onClick(self, controlID):
        if controlID == 300:
            self.showDevices()
        elif controlID == 200:
            mli = self.deviceList.getSelectedItem()
            if tablo.API.selectDevice(mli.dataSource.ID):
                util.saveTabloDeviceID(mli.dataSource.ID)
                self.exit = False
                self.doClose()
            else:
                xbmcgui.Dialog().ok('Connection Failure', 'Cannot connect to {0}'.format(tablo.API.device.displayName))

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
