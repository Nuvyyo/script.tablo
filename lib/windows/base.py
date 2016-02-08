
def dialogFunction(f):
    def wrap(self, *args, **kwargs):
        self._showingDialog = True
        f(self, *args, **kwargs)
        self._showingDialog = False
    return wrap
