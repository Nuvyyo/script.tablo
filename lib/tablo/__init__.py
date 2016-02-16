import os
import sys
import inspect

cmd_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0]))
if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

import api

API = api.API
Show = api.Show
Airing = api.Airing
Series = api.Series
Movie = api.Movie
Sport = api.Sport
Program = api.Program
GridAiring = api.GridAiring


def setUserAgent(agent):
    api.USER_AGENT = agent
