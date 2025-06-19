import math
import os
from PyQt5.QtCore import Qt


DEFAULT_DIRECTORY = os.path.dirname(os.path.realpath(__file__)) + "\\"
VERSION_FILE = DEFAULT_DIRECTORY + "version_project.txt"
DEFAULT_FILE = "New Response.fr"

#region Resources
RESOURCE_DIRECTORY = DEFAULT_DIRECTORY + "Resources\\"
FONT_DIRECTORY = RESOURCE_DIRECTORY + "Barlow/"
COLOR_FILE = RESOURCE_DIRECTORY + "Colors.css"
STYLESHEET_FILE = RESOURCE_DIRECTORY + "Stylesheet.qss"
#end region

#region Constants
PI = math.pi
FUZZ = 10**-10
MIN_FREQUENCIES = 10

DEFAULT_MIN = 9999999999
DEFAULT_MAX = -DEFAULT_MIN
QT_WILDCARD_CRITERIA = Qt.MatchWildcard
QT_EXACT_MATCH_CRITERIA = Qt.MatchExactly | Qt.MatchCaseSensitive
#end region

