import ConfigParser
from utils.inspectors import caller_name


class RawConfigParserEx(ConfigParser.RawConfigParser):
    """extends ConfigParser.RawConfigParser class.
        Definition of setting file:
        [<Full module name> or <full class name>]
        Key: value

        NOTE:
            Because the definition of RawConfigParser is incorrect,
            super(class, self) can not be used ...
    """
    def get(self, option):
        # type: (str) -> str
        """ It is not necessary to specify section in this method.
        :param option: string, key for value.
        :return: the value
        """
        section = caller_name()
        value = ConfigParser.RawConfigParser.get(self, section, option)
        if "\\n" in value:
            value = value.replace("\\n", "\n")
        return value
