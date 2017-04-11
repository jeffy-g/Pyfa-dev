"""
definition to be shared by gui package
"""
from utils.configtools import RawConfigParserEx

g_gui_config = RawConfigParserEx()
# manage gui package resource with gui.ini
with open('./gui/gui.ini') as gui_ini:
    g_gui_config.readfp(gui_ini)

# print g_gui_config.sections()
