import tablo
import windows
import util
import backgroundthread


def start():
    util.LOG('[- START -----------------------]')
    util.setGlobalProperty('guide.filter', '')

    with util.Cron(interval=5):
        bw = windows.BackgroundWindow.create()
        while True:
            w = windows.ConnectWindow.open()

            if w.exit or not tablo.API.deviceSelected():
                return

            del w

            windows.WM.start()
            if windows.WM.exit:
                break

        del bw

        backgroundthread.BGThreader.shutdown()

    util.LOG('[- END -------------------------]')
