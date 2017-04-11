"""
    2017/04/05: unread description tests module.
"""
# noinspection PyPackageRequirements
import pytest
# Add root folder to python paths
# This must be done on every test in order to pass in Travis
import os
import sys
import re

from time import gmtime, strftime
# from utils.strfunctions import sequential_rep, replace_ltgt
from utils.stopwatch import Stopwatch
from functools import wraps

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.realpath(os.path.join(script_dir, '..')))
sys._called_from_test = True  # need db open for tests. (see eos/config.py#17
# noinspection PyPep8
from service.port import Port, IPortUser, PortProcessing, CannotResolveShipException
from service.fit import Fit
#
# noinspection PyPackageRequirements
# from _development.helpers import DBInMemory as DB

"""
NOTE:
  description character length is restricted 4hundred by EVE client.
  these things apply to multi byte environment too.


    o read xml fit data (and encode to utf-8 if need.

    o construct xml dom object, and extract "fitting" elements.

    o apply _resolve_ship method to each "fitting" elements. (time measurement

        o extract "hardware" elements from "fitting" element.

        o apply _resolve_module method to each "hardware" elements. (time measurement

xml files:
    "jeffy_ja-en[99].xml"

NOTE of @decorator:
    o Function to receive arguments of function to be decorated
    o A function that accepts the decorate target function itself as an argument
    o A function that accepts arguments of the decorator itself

for local coverage:
    py.test --cov=./ --cov-report=html
    py.test -s --cov=tests --cov-report=html tests
    py.test -s --collectonly tests
"""


class LightWeightUser(IPortUser):
    # Lightweight user
    def on_port_processing(self, action, data=None):
        # print(data)
        return True


class MiddleWeightUser(IPortUser):
    # Middleweight user
    def __init__(self, allow_print=False):
        """
        :param allow_print: bool
            True: if action flag includes IPortUser.ID_UPDATE, IPortUser.ID_UPDATE then print is not suppressed
            False: behaves in the opposite way (print suppression
        """
        self.__allow_print = allow_print
        self.fit_count = 0
        self.progress = 0

    # noinspection PyUnusedLocal
    def on_port_processing(self, action, data):
        _message = None
        if action & IPortUser.ID_ERROR:
            _message =\
                "The following error was generated\n%s\n\Be aware that already processed fits were not saved" % data
            print(_message)
            return False

        # data is str
        if action & IPortUser.PROCESS_IMPORT:
            if action & IPortUser.ID_PULSE:
                _message = ()
            # update message
            elif action & IPortUser.ID_UPDATE:
                _message = data
            elif action & IPortUser.ID_DONE:  # data is *Fit
                assert self.fit_count is len(data)
                print("---- Succeed import process. ----")
                if self.__allow_print:
                    for name in map(lambda fit: fit.name, data):
                        print("fit name=%s" % name)
                return False

            if _message is not None:  # if (): is evaluated as False
                if self.__allow_print:
                    print(_message)
                return True

        # data is tuple(int, str)
        elif action & IPortUser.PROCESS_EXPORT:
            if action & IPortUser.ID_DONE:
                # NOTE: If you set it to "is" instead of "==" you will get an error...?
                # self.fit_count == self.progress + 1
                try:
                    assert self.fit_count == self.progress
                except AssertionError as ae:
                    print("AssertionError: %s" % ae.message)
                else:
                    print("Export done normaly, fit_count=%s, progress(0 to)=%s" % (self.fit_count, self.progress))
                return False
            else:
                self.progress = data[0] + 1
                if self.__allow_print:
                    print("progress=%s, msg=%s" % (data[0], data[1]))
                return True

    def set_assert_var(self, i):
        # should be call before on_port_processing.
        self.reset()
        self.fit_count = i
        print("entry count for assertion, value=%s" % i)

    def reset(self):
        self.fit_count = 0
        self.progress = 0


XML_FILES = (
    "jeffy_ja-en[99].xml",
    "jeffy_ja-en[99].xml",
    "jeffy_ja-en[99].xml",
    # "jeffy_ja-en[99].xml",
)
BAD_SHIP_XML = "xship_ja-en[3].xml"
WRONG_XML = "wrong_xml_ja-en[3].xml"
# test loop count
LOOP_COUNT = 1

g_stpw = Stopwatch()
usr = LightWeightUser()
# allow_print: True or False
# see MiddleWeightUser.__init__
mid_usr = MiddleWeightUser(allow_print=0)


def auto_repetition(stpw_, **kwds):
    # type: (Stopwatch, dict) -> function
    """
    :param stpw_: Stopwatch instance.
        assign function docstring to name field.
        call reset method before loop.
        print statistics when loop done.
    :param kwds: key loop default is 1
    :return: ...
    """
    def _inner(fn):
        @wraps(fn)
        def __inner(*args, **kwargs):
            set_count = kwds.get("loop")
            if not set_count:
                set_count = 1
            stpw_.name = fn.__doc__
            stpw_.reset()
            while set_count:
                fn(*args, **kwargs)
                set_count -= 1
            # print statistics
            print "%s\n" % stpw_
            # return stpw_.stat
        return __inner
    return _inner


@pytest.fixture()
def print_db_info():
    # Output debug info
    import eos
    print
    print "------------ data base connection info ------------"
    print(eos.db.saveddata_engine)
    print(eos.db.gamedata_engine)
    print


def _extract_count(xml_file):
    # xml_file must be like "anyname[#n].xml"
    return int(re.search(r"\[(\d+)\]", xml_file).group(1))


""" - - - - - - - - - - - - - - - - - - - - test methods - - - - - - - - - - - - - - - - - - -  """


# noinspection PyUnusedLocal
@pytest.mark.usefixtures('print_db_info')
@auto_repetition(g_stpw)
def test_00():
    """case parse xml"""
    for xml_file in XML_FILES:
        fit_count = _extract_count(xml_file)
        fits = None
        with open(os.path.join(script_dir, xml_file), "r") as istream:
            src_string = istream.read()

        src_string = unicode(src_string, "utf-8")
        usr.on_port_process_start()
        with g_stpw:
            # (basestring, IPortUser, basestring) -> list[eos.saveddata.fit.Fit]
            fits = Port.importXml(src_string, usr)

        assert fits is not None and len(fits) is fit_count


@auto_repetition(g_stpw, loop=LOOP_COUNT)
def test_01():
    """case import from file (commit to db"""
    # NOTE: @decorator is to be slow?
    # However, it's appreciated that the code will be succinct

    # counter = LOOP_COUNT
    # stpw.reset()
    # while counter:
    xml_file = XML_FILES[0]
    mid_usr.set_assert_var(_extract_count(xml_file))
    xml_file = os.path.join(script_dir, xml_file)
    """ NOTE: Port.importFitsThreaded on threading (sqlite3.ProgrammingError
        (sqlite3.ProgrammingError) SQLite objects created in a thread can only be used in that same thread.
        The object was created in thread id 6716 and this is thread id 6604.
    """
    # Port.importFitsThreaded((xml_file,), usr2)
    with g_stpw:
        PortProcessing.importFitsFromFile((xml_file,), mid_usr)
    #     counter -= 1
    #
    # # print statistics
    # print "%s\n" % stpw


def _error_case(file_name, except_class):
    fits = None
    with open(os.path.join(script_dir, file_name), "r") as istream:
        src_string = istream.read()

    src_string = unicode(src_string, "utf-8")
    usr.on_port_process_start()
    try:
        with g_stpw:
            fits = Port.importXml(src_string, mid_usr)
    except Exception as e:
        assert isinstance(except_class, e), \
            "failed assertion, It seems that an unexpected exception has occurred"

    assert fits is None


@auto_repetition(g_stpw)
def test_02():
    """case import bad xml(doesn't exist ship"""
    _error_case(BAD_SHIP_XML, CannotResolveShipException)


@auto_repetition(g_stpw)
def test_03():
    """case import wrong xml(syntax error"""
    import xml.parsers.expat
    _error_case(WRONG_XML, xml.parsers.expat.ExpatError)


# NOTE: auto_repetition decorator affects execution order
# @auto_repetition(g_stpw, loop=4)
def test_backup_all():
    """case backup all to xml(write to file"""
    g_stpw.name = test_backup_all.__doc__
    counter = 6
    g_stpw.reset()
    while counter:
        file_name = "tests-export-%s.xml" % strftime("%Y%m%d_%H%M%S", gmtime())
        mid_usr.set_assert_var(
            Fit.getInstance().countAllFits()
        )
        dest_path = os.path.join(script_dir, file_name)
        with g_stpw:
            PortProcessing.backupFits(dest_path, mid_usr)
        # cleanup
        # http://stackoverflow.com/questions/21257782/how-to-remove-file-when-program-exits
        os.remove(dest_path)
        counter -= 1
    # # print statistics
    print "%s\n" % g_stpw
