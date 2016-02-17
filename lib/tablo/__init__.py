import _included_packages
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
