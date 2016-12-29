import datetime

class Path:
    def __init__(self, _path, _full_path):
        self.path = _path
        self.full_path = _full_path

class Usage:
    def __init__(self, _api_name, _api_type, _used, _allocated):
        self.api_name = _api_name
        self.api_type = _api_type

        if _allocated == 0:
            self.percent = 0
        else:
            self.percent = round(_used) / round(_allocated) * 100

        i = 0
        j = 0
        while _used > 1024:
            i += 1
            _used /= 1024.0

        if i is 0:
            self.used = str(round(_used, 1))+' B'
        if i is 1:
            self.used = str(round(_used, 1))+' KB'
        if i is 2:
            self.used = str(round(_used, 1))+' MB'
        if i is 3:
            self.used = str(round(_used, 1))+' GB'
        if i is 4:
            self.used = str(round(_used, 1))+' TB'

        while _allocated > 1024:
            j += 1
            _allocated /= 1024.0

        if j is 0:
            self.allocated = str(round(_allocated, 1))+' B'
        if j is 1:
            self.allocated = str(round(_allocated, 1))+' KB'
        if j is 2:
            self.allocated = str(round(_allocated, 1))+' MB'
        if j is 3:
            self.allocated = str(round(_allocated, 1))+' GB'
        if j is 4:
            self.allocated = str(round(_allocated, 1))+' TB'



class File:
    def __init__(self, _type, _index, _name, _size, _path, _modified_date):
        self.type = _type
        self.name = _name
        self.index = chr(ord('a') + _index)

        if _size is None:
            self.size = ""
        else:
            i = 0
            while _size > 1024:
                i += 1
                _size /= 1024.0

            if i is 0:
                self.size = str(_size) + ' B'
            if i is 1:
                self.size = str(round(_size, 2)) + ' KB'
            if i is 2:
                self.size = str(round(_size, 1)) + ' MB'
            if i is 3:
                self.size = str(round(_size, 1)) + ' GB'
            if i is 4:
                self.size = str(round(_size, 1)) + ' TB'
        if _path is None:
            self.path = ""
        else:
            self.path = _path[:(len(_path)-len(_name))]


        if _modified_date is None:
            self.modified_date = ""
        else:
            if _modified_date.month in [1, 2, 8, 9, 10, 11, 12]:
                self.modified_date = _modified_date.strftime('%b. %d, %Y, %I:%M %p')
            else:
                self.modified_date = _modified_date.strftime('%B %d, %Y, %I:%M %p')
