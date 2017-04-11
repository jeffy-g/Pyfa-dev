"""
definition to be shared by gui package
NOTE:
    why cannot import utils package?(not gui.utils
    "from utils.configtools import RawConfigParserEx" statement was not worked...
    Is the gui.utils package bad?

Traceback (most recent call last):
  File "F:/ext_prg/develp/msys/1.0/home/ht/git/jeffy-g/Pyfa-dev/pyfa.py", line 290, in <module>
    from gui.mainFrame import MainFrame
  File "F:\ext_prg\develp\msys\1.0\home\ht\git\jeffy-g\Pyfa-dev\gui\__init__.py", line 7, in <module>
    from utils.configtools import RawConfigParserEx
ImportError: No module named configtools

"""
# from utils.configtools import RawConfigParserEx
#
# g_gui_config = RawConfigParserEx()
mod = __import__("utils.configtools")
g_gui_config = mod.configtools.RawConfigParserEx()
# manage gui package resource with gui.ini
with open('./gui/gui.ini') as gui_ini:
    g_gui_config.readfp(gui_ini)

del mod
# print g_gui_config.sections()
