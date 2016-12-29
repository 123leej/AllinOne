
class DataNotExist(Exception):
    def __init__(self):
        Exception.__init__(self)

    def __str__(self):
        return repr(self)


class APIInfoAlreadyExist(Exception):
    def __init__(self):
        Exception.__init__(self)

    def __str__(self):
        return repr(self)


class FtpNotExist(Exception):
    def __init__(self):
        Exception.__init__(self)

    def __str__(self):
        return repr(self)
