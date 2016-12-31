import io
import os
import sys
import json
import uuid
import time
import getpass
import fnmatch
import httplib2
import datetime
import subprocess
from exceptions import KeyError

from django.shortcuts import render, render_to_response
from django.http import HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from models import AllinOneUser, APIInfo, DetachedFileMetaData

from my_exception import DataNotExist, APIInfoAlreadyExist, FtpNotExist
from my_class import Path, Usage, File

from dropbox.files import FileMetadata, FolderMetadata
from dropbox.client import DropboxOAuth2Flow
import dropbox

from googleapiclient import http
from apiclient import discovery
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.client import Credentials

import onedrivesdk
from onedrivesdk.helpers import GetAuthCodeServer

import ftplib



#make possible to hangle
reload(sys)
sys.setdefaultencoding('utf-8')
#TODO upload path problem

#USER PROCESS###########################################################################################################
########################################################################################################################



#get username & password and authorization
def do_login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        return _login(request, user)
    else:
        return HttpResponseBadRequest()


#make session with authenticated user with django application
def _login(request, authenticate_user):
    if authenticate_user is not None:
        if authenticate_user.is_active:
            login(request, authenticate_user)
            url = reverse('main')+'?name=home&location='
            return HttpResponseRedirect(url)
        else:
            # Return a 'disabled account' error message
            return render(request, 'login.html', {'error': 'disabled account'})
    else:
        # Return an 'invalid login' error message.
        return render(request, 'login.html', {'error': 'unxpected exception'})


def do_logout(request):

    logout(request)
    return HttpResponseRedirect(reverse('login'))


#
def signup(request):
    if request.method == 'GET':
        return render(request, 'signup.html')
    elif request.method == 'POST':
        try:
            username = request.POST['username']
            password = request.POST['password']

            if username == '' or password == '':
                raise DataNotExist

            aio_user_id = str(uuid.uuid4())
            aio_user = AllinOneUser(aio_user_id=aio_user_id)
            aio_user.save()

            aio_user.user.username = username
            aio_user.user.set_password(password)
            aio_user.user.save()

            auth_user = authenticate(username=username, password=password)
            return _login(request, auth_user)
        except DataNotExist:
            return render(request, 'signup.html', {'error': 'ID PW must be required'})
    else:
        return HttpResponseBadRequest()


#select type of api you want to add
def select_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
        aio_user = AllinOneUser.objects.get(user=request.user)
        try:
            api_list = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id)
            account_list, total_usage, none_of_data = get_user_api_info(api_list)
        except APIInfo.DoesNotExist:
            account_list = None
            total_usage = Usage('total', None, 0, 0)

        context = {
            'user_info': request.user,
            'accountList': account_list,
            'totalUsed': total_usage
        }

        return render_to_response('selecttype.html', context)


#add new api and set nickname
def add_account(request):
    if request.method == 'GET':
        aio_user = AllinOneUser.objects.get(user=request.user)
        try:
            api_list = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id)
            account_list, total_usage, none_of_data = get_user_api_info(api_list)
        except APIInfo.DoesNotExist:
            account_list = None
            total_usage = Usage('total', None, 0, 0)

        context = {
            'user_info': request.user,
            'accountList': account_list,
            'totalUsed': total_usage
        }

        return render(request, 'addaccount.html', context)

    elif request.method == 'POST':
        if request.session['aio_user_id'] is not None:
            try:
                aio_user = AllinOneUser.objects.get(aio_user_id=request.session['aio_user_id'])
                api_info = APIInfo.objects.get(
                    aio_user_id_id=aio_user.aio_user_id,
                    api_name='unknown'
                )
                api_name = str(request.POST['api_name'])

                if api_name == '':
                    raise DataNotExist
                else:
                    api_filter = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id, api_name=api_name)
                    if api_filter.count() == 0:
                        api_info.api_name = api_name
                        api_info.save()
                        url = reverse('main') + '?name=' + api_info.api_name + '&location='
                        del request.session['dropbox-auth-csrf-token']
                        return HttpResponseRedirect(url)
                    else:
                        raise APIInfoAlreadyExist
            except APIInfoAlreadyExist:
                url = reverse('main') + '?name=home&location'
                return HttpResponseRedirect(url, {
                    'error': 'same api already exist',
                    'user_info': request.user
                })
            except DataNotExist:
                return render(request, 'addaccount.html', {
                    'error': 'nickname must be required',
                    'user_info': request.user
                })
        else:
            return HttpResponseForbidden()
    else:
        return HttpResponseBadRequest()





#MAIN PROCESS###########################################################################################################
########################################################################################################################


def main(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
#GET_DATA###############################################################################################################
        file_list = []
        try:
            api_name = str(request.GET['name'])
            location = str(request.GET['location'])
        except KeyError:
            api_name = 'home'
            location = ''

        aio_user = AllinOneUser.objects.get(user=request.user)

        try:
            api_list = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id)
            account_list, total_usage, used_info_list = get_user_api_info(api_list)

        except APIInfo.DoesNotExist:
            account_list = None
            used_info_list = None
            total_usage = Usage('total', None, 0, 0)

#LISTING################################################################################################################
        if api_name != 'home':
            api_info = APIInfo.objects.get(
                aio_user_id_id=aio_user.aio_user_id,
                api_name=api_name
            )

            if api_info.api_type == 'dropbox':
                dbx = dropbox.Dropbox(api_info.api_user_access_token)

                temp = dbx.files_list_folder(location).entries
                idx = 0
                for _file in temp:
                    idx += 1
                    if isinstance(_file, FileMetadata):
                        file_list.append(
                            File(
                                'file',
                                idx,
                                _file.name,
                                _file.size,
                                super(FileMetadata, _file).path_display,
                                _file.server_modified
                            )
                        )
                    else:
                        file_list.append(
                            File(
                                'folder',
                                idx,
                                _file.name,
                                None,
                                super(FolderMetadata, _file).path_display,
                                None
                            )
                        )


            if api_info.api_type == 'googledrive':
                drive_service = ggdrive_get_drive_service(api_info)

                temp_list = drive_service.files().list(
                    fields='files(id, name, parents, size, modifiedTime, mimeType)').execute()
                temp_list = temp_list['files']
                location_id = ggdrive_get_file_id_from_entry(temp_list, location)
                temp_file_list = ggdrive_show_files(location_id, temp_list)
                idx = 0
                for _file in temp_file_list:
                    idx += 1
                    if _file['mimeType'] != 'application/vnd.google-apps.folder':
                        file_list.append(
                            File(
                                'file',
                                idx,
                                _file['name'],
                                int(_file['size']),
                                None,
                                datetime.datetime.strptime(_file['modifiedTime'][:19], '%Y-%m-%dT%H:%M:%S')
                            )
                        )
                    else:
                        file_list.append(
                            File(
                                'folder',
                                idx,
                                _file['name'],
                                None,
                                None,
                                None
                            )
                        )

            if api_info.api_type == 'onedrive':
                client = onedrive_get_auth_flow(api_info)

                if location == '':
                    location = '/'

                temp_file_list = client.item(drive='me', path=location).children.get()

                if location == '/':
                    location = ''
                idx = 0
                for _file in temp_file_list:
                    idx += 1
                    if _file.c_tag[1] == 'Y':
                        file_list.append(
                            File(
                                'file',
                                idx,
                                _file.name,
                                _file.size,
                                _file.parent_reference.path[6:]+_file.name,
                                _file.last_modified_date_time

                            )
                        )
                    else:
                        file_list.append(
                            File(
                                'folder',
                                idx,
                                _file.name,
                                None,
                                _file.parent_reference.path[6:]+_file.name,
                                None
                            )
                        )

            if api_info.api_type == 'ftp':
                user_data = api_info.api_user_access_token.split('/')
                ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

                ftp_root_directory = ftp.pwd()
                ftp.cwd(ftp_root_directory+location)
                temp_file_list = ftp.nlst()
                idx = 0
                for _file in temp_file_list:
                    idx += 1
                    try:
                        ftp.size(_file)
                        file_list.append(
                            File(
                                'file',
                                idx,
                                _file,
                                ftp.size(_file),
                                None,
                                datetime.datetime.strptime(ftp.sendcmd('MDTM ' + _file), '%j %Y%m%d%H%M%S')
                            )
                        )
                    except ftplib.error_perm:
                        file_list.append(
                            File(
                                'folder',
                                idx,
                                _file,
                                None,
                                None,
                                None
                            )
                        )
                ftp.close()
        else:
            file_list = None

        path = location.split('/')[1:]
        path = make_full_path(path)

        context = {
            'path': path,
            'user_info': request.user,
            'fileList': file_list,
            'name': api_name,
            'location': location,
            'accountList': account_list,
            'usedList': used_info_list,
            'totalUsed': total_usage
        }

        return render(request, 'main.html', context)


#modifying file name event view for rename & new folder
@csrf_exempt
def modify(request):
    if request.method == 'GET':
        if not request.user.is_authenticated():
            return HttpResponseRedirect(reverse('login'))
        else:
            file_list = []
            target_file = str(request.GET['target_file'])
            api_name = str(request.GET['api_name'])
            location = str(request.GET['location'])

            aio_user = AllinOneUser.objects.get(user=request.user)
            try:
                api_list = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id)
                account_list, total_usage, used_info_list = get_user_api_info(api_list)
            except APIInfo.DoesNotExist:
                account_list = None
                used_info_list = None
                total_usage = Usage('total', None, 0, 0)


            api_info = APIInfo.objects.get(
                aio_user_id_id=aio_user.aio_user_id,
                api_name=api_name
            )

            if api_info.api_type == 'dropbox':
                dbx = dropbox.Dropbox(api_info.api_user_access_token)

                temp = dbx.files_list_folder(location).entries
                idx = 0
                for _file in temp:
                    idx += 1
                    if _file.name != target_file:
                        if isinstance(_file, FileMetadata):
                            file_list.append(
                                File(
                                    'file',
                                    idx,
                                    _file.name,
                                    _file.size,
                                    None,
                                    _file.server_modified
                                )
                            )
                        else:
                            file_list.append(
                                File(
                                    'folder',
                                    idx,
                                    _file.name,
                                    None,
                                    None,
                                    None
                                )
                            )
                    else:
                        file_list.append(
                            File(
                                'modifying',
                                idx,
                                _file.name,
                                None,
                                None,
                                None
                            )
                        )

            if api_info.api_type == 'googledrive':
                drive_service = ggdrive_get_drive_service(api_info)

                temp_list = drive_service.files().list(
                    fields='files(id, name, parents, size, modifiedTime, mimeType)').execute()
                temp_list = temp_list['files']
                location_id = ''
                if location == '':
                    for temp in temp_list:
                        if len(str(temp['parents'][0])) < 20:
                            location_id = str(temp['parents'][0])
                            break
                else:  # get id value of given directory
                    path_name = location.split('/')
                    for temp in temp_list:
                        if str(temp['name']) == path_name[len(path_name)-1]:
                            location_id = str(temp['id'])
                            break
                temp_file_list = ggdrive_show_files(location_id, temp_list)
                idx = 0
                for _file in temp_file_list:
                    idx += 1
                    if _file['name'] != target_file:
                        if _file['mimeType'] != 'application/vnd.google-apps.folder':
                            file_list.append(
                                File(
                                    'file',
                                    idx,
                                    _file['name'],
                                    int(_file['size']),
                                    None,
                                    datetime.datetime.strptime(_file['modifiedTime'][:19], '%Y-%m-%dT%H:%M:%S')
                                )
                            )
                        else:
                            file_list.append(
                                File(
                                    'folder',
                                    idx,
                                    _file['name'],
                                    None,
                                    None,
                                    None
                                )
                            )
                    else:
                        file_list.append(
                            File(
                                'modifying',
                                idx,
                                _file['name'],
                                None,
                                None,
                                None
                            )
                        )

            if api_info.api_type == 'onedrive':
                client = onedrive_get_auth_flow(api_info)

                if location == '':
                    location = '/'

                temp_file_list = client.item(drive='me', path=location).children.get()

                if location == '/':
                    location = ''
                idx = 0
                for _file in temp_file_list:
                    idx += 1
                    if _file.name != target_file:
                        if _file.c_tag[1] == 'Y':
                            file_list.append(
                                File(
                                    'file',
                                    idx,
                                    _file.name,
                                    _file.size,
                                    _file.parent_reference.path[6:]+_file.name,
                                    _file.last_modified_date_time

                                )
                            )
                        else:
                            file_list.append(
                                File(
                                    'folder',
                                    idx,
                                    _file.name,
                                    None,
                                    _file.parent_reference.path[6:]+_file.name,
                                    None
                                )
                            )
                    else:
                        file_list.append(
                            File(
                                'modifying',
                                idx,
                                _file.name,
                                None,
                                None,
                                None
                            )
                        )

            if api_info.api_type == 'ftp':
                user_data = api_info.api_user_access_token.split('/')
                ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

                ftp_root_directory = ftp.pwd()
                ftp.cwd(ftp_root_directory+location)
                temp_file_list = ftp.nlst()
                idx = 0
                for _file in temp_file_list:
                    idx += 1
                    if _file != target_file:
                        try:
                            ftp.size(_file)
                            file_list.append(
                                File(
                                    'file',
                                    idx,
                                    _file,
                                    ftp.size(_file),
                                    None,
                                    datetime.datetime.strptime(ftp.sendcmd('MDTM ' + _file), '%j %Y%m%d%H%M%S')
                                )
                            )
                        except ftplib.error_perm:
                            file_list.append(
                                File(
                                    'folder',
                                    idx,
                                    _file,
                                    None,
                                    None,
                                    None
                                )
                            )
                    else:
                        file_list.append(
                            File(
                                'modifying',
                                idx,
                                _file,
                                None,
                                None,
                                None
                            )
                        )

                ftp.close()

            #path dictionary for path Div
            path = location.split('/')[1:]
            path = make_full_path(path)

            context = {
                'path': path,
                'user_info': request.user,
                'fileList': file_list,
                'name': api_name,
                'location': location,
                'accountList': account_list,
                'usedList': used_info_list,
                'totalUsed': total_usage
            }

            return render(request, 'modify.html', context)
    elif request.method == 'POST':
        try:
            new_file_name = str(request.POST['modifying'])
            api_name = str(request.POST['api_name'])
            target_file = str(request.POST['target_file'])
            location = str(request.POST['location'])
        except KeyError:
            new_file_name = 'Undefined'


        return file_rename(request, target_file, location, api_name, new_file_name)





#ACCESS PROCESS#########################################################################################################
########################################################################################################################


#get context menu event
@csrf_exempt
def file_check(request):
    entry = request.GET.getlist('fileChecked')
    location = str(request.GET['location'])
    request_type = str(request.GET['type'])
    api_name = str(request.GET['name'])

    if request_type == 'download':
        for i in range(0, len(entry)):
            if str(entry[i]).endswith('.metadata'):
                return merge_file(request, entry[i], location)
            else:
                return file_download(request, [entry[i]], location, api_name)

    if request_type == 'delete':
        for i in range(0, len(entry)):
            if str(entry[i]).endswith('.metadata'):
                return delete_metadata_file(request, entry[i], location)
            else:
                return file_delete(request, entry, location, api_name)

    if request_type == 'newfolder':
        return new_folder(request, location, api_name)

    if request_type == 'rename' and len(entry) == 1:
        if str(entry[0]).endswith('.metadata'):
            url = reverse('main') + '?name=' + api_name + '&location=' + location
        else:
            url = reverse('modify')+'?target_file='+entry[0]+'&api_name='+api_name+'&location='+location
        return HttpResponseRedirect(url)



def file_rename(request, _file, location, api_name, new_file_name):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
        aio_user = AllinOneUser.objects.get(user=request.user)

        api_info = APIInfo.objects.get(
            aio_user_id_id=aio_user.aio_user_id,
            api_name=api_name
        )

        if api_info.api_type == 'dropbox':
            dbx = dropbox.Dropbox(api_info.api_user_access_token)

            dbx.files_move(location+'/'+_file, location+'/'+new_file_name)

        if api_info.api_type == 'googledrive':
            drive_service = ggdrive_get_drive_service(api_info)

            file_list = drive_service.files().list(fields='files(id, name, parents)').execute()

            target_id = ggdrive_get_file_id_from_entry(file_list['files'], location, str(_file))
            file_metadata = {
                'name': str(new_file_name),
            }
            drive_service.files().update(fileId=target_id, body=file_metadata).execute()


        if api_info.api_type == 'onedrive':
            client = onedrive_get_auth_flow(api_info)

            if location == '':
                root_folder = client.item(drive='me', id='root').children.get()

                for j in range(0, len(root_folder)):

                    if _file == root_folder[j].name:
                        renamed_item = onedrivesdk.Item()
                        renamed_itemid = root_folder[j].id
                        renamed_item.name = new_file_name
                        client.item(drive='me', id=renamed_itemid).update(renamed_item)
            else:
                folder_access = client.item(drive='me', path=location).children.get()

                for j in range(0, len(folder_access)):
                    if _file == folder_access[j].name:
                        renamed_item = onedrivesdk.Item()
                        renamed_itemid = folder_access[j].id
                        renamed_item.name = new_file_name
                        client.item(drive='me', id=renamed_itemid).update(renamed_item)

        if api_info.api_type == 'ftp':
            user_data = api_info.api_user_access_token.split('/')
            ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

            ftp_root_directory = ftp.pwd()
            ftp.cwd(ftp_root_directory + location)
            ftp.rename(_file, new_file_name)

        url = reverse('main')+'?name='+api_name+'&location='+location

        return HttpResponseRedirect(url)



def new_folder(request, location, api_name):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
        new_folder_name = 'NewTempFolder'
        aio_user = AllinOneUser.objects.get(user=request.user)

        api_info = APIInfo.objects.get(
            aio_user_id_id=aio_user.aio_user_id,
            api_name=api_name
        )

        if api_info.api_type == 'dropbox':
            dbx = dropbox.Dropbox(api_info.api_user_access_token)

            dropbox.Dropbox.files_create_folder(dbx, location+'/'+new_folder_name)

        if api_info.api_type == 'googledrive':
            drive_service = ggdrive_get_drive_service(api_info)

            file_list = drive_service.files().list(fields='files(id, name, parents)').execute()
            parent_id = ggdrive_get_file_id_from_entry(file_list['files'], location)
            file_metadata = {
                'name': new_folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            drive_service.files().create(body=file_metadata, fields='id').execute()


        if api_info.api_type == 'onedrive':
            client = onedrive_get_auth_flow(api_info)

            _folder = onedrivesdk.Folder()
            _item = onedrivesdk.Item()
            _item.name = new_folder_name
            _item.folder = _folder
            if location == '':
                location = '/'

            client.item(drive='me', path=location).children.add(_item)

            #Fucking add - onedrive new folder - pass
            if location == '/':
                location = ''

        if api_info.api_type == 'ftp':
            user_data = api_info.api_user_access_token.split('/')
            ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

            ftp_root_directory = ftp.pwd()
            ftp.cwd(ftp_root_directory+location)
            ftp.mkd(new_folder_name)
            ftp.close()

        url = reverse('modify') + '?target_file=NewTempFolder&api_name=' + api_name + '&location=' + location

        return HttpResponseRedirect(url)



def search_file(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
        result = []
        search_name = str(request.GET['search_name'])
        location = str(request.GET['location'])
        api_name = str(request.GET['name'])

        aio_user = AllinOneUser.objects.get(user=request.user)
        try:
            api_list = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id)
            account_list, total_usage, none_of_data = get_user_api_info(api_list)
        except APIInfo.DoesNotExist:
            account_list = None
            total_usage = Usage('total', None, 0, 0)


        api_info = APIInfo.objects.get(
            aio_user_id_id=aio_user.aio_user_id,
            api_name=api_name
            )

        if api_info.api_type == 'dropbox':
            dbx = dropbox.Dropbox(api_info.api_user_access_token)

            search_result = dbx.files_search("", search_name).matches
            idx = 0
            for search_match in search_result:
                idx += 1
                result.append(
                    File(
                        None,
                        idx,
                        search_match.metadata.name,
                        None,
                        search_match.metadata.path_display,
                        None
                    )
                )

        if api_info.api_type == 'googledrive':
            drive_service = ggdrive_get_drive_service(api_info)

            file_list = drive_service.files().list(fields='files(id, name, parents, ownedByMe)').execute()
            search_result = []
            for _file in file_list['files']:
                if not _file['ownedByMe']:
                    continue
                if search_name in _file['name']:
                    path = ggdrive_get_full_directory(file_list['files'], _file['id'])
                    search_result += [{'metadata': {'name': _file['name'], 'path_display': path}}]
            idx = 0
            for search_match in search_result:
                idx += 1
                try:
                    result.append(
                        File(
                            None,
                            idx,
                            search_match['metadata']['name'],
                            None,
                            search_match['metadata']['path_display'],
                            None
                        )
                    )
                except KeyError:
                    pass

        if api_info.api_type == 'onedrive':
            client = onedrive_get_auth_flow(api_info)
            search_result = client.item(drive="me", path="/").search(search_name).get()
            idx = 0
            for i in range(0, len(search_result)):
                idx += 1
                _name = search_result[i].name
                test_path = search_result[i].parent_reference.path[6:]
                _path = test_path.replace('%20', ' ') + search_result[i].name

                result.append(
                    File(
                        None,
                        idx,
                        _name,
                        None,
                        _path,
                        None
                    )
                )

        if api_info.api_type == 'ftp':
            user_data = api_info.api_user_access_token.split('/')
            ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

            ftp_root_directory = ftp.pwd()
            ftp.cwd(ftp_root_directory + location)
            search_result = ftp_file_search(ftp, search_name)
            idx = 0
            for search_match in search_result:
                idx += 1
                temp = search_match.split('/')
                _name = temp[len(temp)-1]
                temp = make_full_path(temp[1:])[len(temp)-2].full_path
                _path = temp[:len(temp)-1]
                result.append(
                    File(
                        None,
                        idx,
                        _name,
                        None,
                        _path,
                        None
                    )
                )
            ftp.close()

        context = {
            'user_info': request.user,
            'search': search_name,
            'fileList': result,
            'location': location,
            'name': api_name,
            'accountList': account_list,
            'totalUsed': total_usage
        }

        return render(request, 'search_result.html', context)


def file_upload(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
        api_name = str(request.GET['name'])
        location = str(request.GET['location'])

        #origin
        #file_entry = str(request.GET['filepath'])
        file_entry = '/Users/'+getpass.getuser()+'/Desktop/TestFolder/'+str(request.GET['filepath'])

        #origin
        #filecut = str(file_entry).split('\\')
        filecut = str(file_entry).split('/')

        aio_user = AllinOneUser.objects.get(user=request.user)
        api_info = APIInfo.objects.get(
            aio_user_id_id=aio_user.aio_user_id,
            api_name=api_name
        )

        do_upload(api_info, file_entry, location, filecut[len(filecut)-1])

        url = reverse('main') + '?name=' + api_info.api_name + '&location=' + location

        return HttpResponseRedirect(url)



def do_upload(api_info, file_path, location, file_name):
    if api_info.api_type == 'dropbox':
        dbx = dropbox.Dropbox(api_info.api_user_access_token)
        with open(file_path, 'rb') as _file:
            dbx.files_upload(_file, location + '/' + file_name)

    if api_info.api_type == 'googledrive':
        import mimetypes
        drive_service = ggdrive_get_drive_service(api_info)
        file_list = drive_service.files().list(fields='files(id, name, parents)').execute()
        parent_id = ggdrive_get_file_id_from_entry(file_list['files'], location)

        file_entry = str(file_path).replace("\\", "/").replace("[u'", "").replace("']", "")
        while "//" in str(file_entry):
            file_entry = str(file_entry).replace("//", "/")
        with open(file_entry, 'rb'):
            if file_name.endswith('.metadata'):
                file_type = 'application/vnd.google-apps.unknown'
            else:
                file_type = mimetypes.guess_type(file_entry)[0]
            file_metadata = {
                'name': file_name,
                'parents': [parent_id]
            }
            media = http.MediaFileUpload(str(file_entry), mimetype=file_type,
                                         resumable=True)
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

    if api_info.api_type == 'onedrive':
        client = onedrive_get_auth_flow(api_info)
        if location == '':
            location = '/'

        client.item(drive='me', path=location).children['/' + file_name].upload(file_path)

        if location == '/':
            location = ''

    if api_info.api_type == 'ftp':
        user_data = api_info.api_user_access_token.split('/')
        ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

        ftp_root_directory = ftp.pwd()
        ftp.cwd(ftp_root_directory + location)
        for i in range(0, len(file_path)):
            with open(file_path, 'rb') as _file:
                ftp.storbinary('STOR ' + file_name, _file, 1024)
            _file.close()
        ftp.close()

    return 0



def file_download(request, entry, location, name):

    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
        aio_user = AllinOneUser.objects.get(user=request.user)
        api_info = APIInfo.objects.get(
            aio_user_id_id=aio_user.aio_user_id,
            api_name=name
        )

        download_path = '/Users/'+getpass.getuser()+'/Downloads'

        if api_info.api_type == 'dropbox':
            dbx = dropbox.Dropbox(api_info.api_user_access_token)

            for i in range(0, len(entry)):
                with open(download_path + '/' + str(entry[i]), "wb") as _file:
                    metadata, res = dbx.files_download(path=location+'/'+str(entry[i]))
                    _file.write(res.content)

        if api_info.api_type == 'googledrive':
            drive_service = ggdrive_get_drive_service(api_info)

            file_list = drive_service.files().list(fields='files(id, name, parents)').execute()
            target_id = []
            for i in range(0, len(entry)):
                target_id += [ggdrive_get_file_id_from_entry(file_list['files'], location, str(entry[i]))]

            for i in range(0, len(target_id)):
                # download the file that has given file id
                request = drive_service.files().get_media(fileId=target_id[i])
                fh = io.BytesIO()
                downloader = http.MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                # write file in given folder
                with open(download_path + '/' + str(entry[i]), "wb") as _file:
                    _file.write(fh.getvalue())

        if api_info.api_type == 'onedrive':
            client = onedrive_get_auth_flow(api_info)

            if location == '':
                root_folder = client.item(drive='me', id='root').children.get()
                for i in range(0, len(entry)):
                    for j in range(0, len(root_folder)):
                        if entry[i] == root_folder[j].name:
                            client.item(drive='me', id=root_folder[j].id).download(download_path + '/' + entry[i])
            else:
                folder_access = client.item(drive='me', path=location).children.get()
                for i in range(0, len(entry)):
                    for j in range(0, len(folder_access)):
                        if entry[i] == folder_access[j].name:
                            client.item(drive='me', id=folder_access[j].id).download(download_path + '/' + entry[i])

        if api_info.api_type == 'ftp':
            user_data = api_info.api_user_access_token.split('/')
            ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

            ftp_root_directory = ftp.pwd()
            ftp.cwd(ftp_root_directory+location)
            for i in range(0, len(entry)):
                with open(download_path + '/' + str(entry[i]), "wb") as _file:
                    ftp.retrbinary('RETR '+str(entry[i]), _file.write, 1024)
                _file.close()
            ftp.close()


        url = reverse('main')+'?name='+name+'&location='+location

        return HttpResponseRedirect(url)



def file_delete(request, entry, location, name):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
        aio_user = AllinOneUser.objects.get(user=request.user)
        api_info = APIInfo.objects.get(
            aio_user_id_id=aio_user.aio_user_id,
            api_name=name
        )

        if api_info.api_type == 'dropbox':
            dbx = dropbox.Dropbox(api_info.api_user_access_token)

            for i in range(0, len(entry)):
                dbx.files_delete(location + '/' + str(entry[i]))

        if api_info.api_type == 'googledrive':
            drive_service = ggdrive_get_drive_service(api_info)

            file_list = drive_service.files().list(fields='files(id, name, parents)').execute()
            for i in range(0, len(entry)):
                target_id = ggdrive_get_file_id_from_entry(file_list['files'], location, str(entry[i]))
                drive_service.files().delete(fileId=target_id).execute()

        if api_info.api_type == 'onedrive':
            client = onedrive_get_auth_flow(api_info)

            if location == '':
                location = '/'

            folder_access = client.item(drive='me', path=location).children.get()

            for i in range(0, len(entry)):
                for j in range(0, len(folder_access)):
                    if entry[i] == folder_access[j].name:
                        id_of_file = folder_access[j].id
                        client.item(drive='me', id=id_of_file).delete()

            if location == '/':
                location = ''

        if api_info.api_type == 'ftp':
            user_data = api_info.api_user_access_token.split('/')
            ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

            ftp_root_directory = ftp.pwd()
            ftp.cwd(ftp_root_directory+location)

            for i in range(0, len(entry)):
                ftp_delete_all(ftp, str(entry[i]))
            ftp.close()

        url = reverse('main')+'?name='+name+'&location='+location

        return HttpResponseRedirect(url)


#get api info ( api name, user total usage, api usage info ) in api_list
def get_user_api_info(api_list):

    account_list = []
    used_info_list = []
    total_used = 0
    total_alloc = 0

    for api in api_list:
        account_list.append(api)
        if api.api_type == 'dropbox':
            dbx = dropbox.Dropbox(api.api_user_access_token)

            used_info_list.append(
                Usage(
                    api.api_name,
                    api.api_type,
                    dbx.users_get_space_usage().used,
                    dbx.users_get_space_usage().allocation.get_individual().allocated
                )
            )

            total_used += dbx.users_get_space_usage().used
            total_alloc += dbx.users_get_space_usage().allocation.get_individual().allocated

        if api.api_type == 'googledrive':
            try:
                drive_service = ggdrive_get_drive_service(api)
                metadata = drive_service.about().get(fields='storageQuota').execute()
                used_space = int(metadata['storageQuota']['usageInDrive'])
                total_space = int(metadata['storageQuota']['limit']) - int(metadata['storageQuota']['usage']) \
                              + int(used_space)

                used_info_list.append(
                    Usage(
                        api.api_name,
                        api.api_type,
                        used_space,
                        total_space
                    )
                )

                total_used += used_space
                total_alloc += total_space
            except NameError:
                pass

        if api.api_type == 'onedrive':

            client = onedrive_get_auth_flow(api)

            used_info_list.append(
                Usage(
                    api.api_name,
                    api.api_type,
                    client.drives["me"].get().quota.used,
                    client.drives["me"].get().quota.total
                )
            )

            total_used += client.drives["me"].get().quota.used
            total_alloc += client.drives["me"].get().quota.total

    total_usage = Usage('total', None, total_used, total_alloc)

    return account_list, total_usage, used_info_list



#ftp post-order search deletion
def ftp_delete_all(ftp, _file):
    try:
        ftp.size(_file)
        ftp.delete(_file)
    except ftplib.error_perm:
        ftp.cwd(_file)
        temp = ftp.nlst('-a')[2:]

        for i in range(0, len(temp)):
            ftp_delete_all(ftp, temp[i])
        ftp.cwd('..')
        ftp.rmd(_file)

    return 0


#ftp pre-order file searching
def ftp_file_search(ftp, _file):

    match_data = []

    def find_file(_ftp, __file):
        temp = _ftp.nlst()

        for i in range(0, len(temp)):
            if __file in temp[i]:
                match_data.append(_ftp.pwd()+'/'+temp[i])
            try:
                _ftp.size(temp[i])
            except ftplib.error_perm:
                try:
                    _ftp.cwd(temp[i])
                except ftplib.error_perm:
                    continue
                find_file(_ftp, __file)
                _ftp.cwd('..')

    find_file(ftp, _file)
    return match_data


#make full path for redirection to backward
def make_full_path(paths):
    temp = '/'
    result = []
    for i in range(0, len(paths)):
        temp += paths[i]+'/'
        result.append(Path(paths[i], temp))
    return result



#gdv make full directory
def ggdrive_get_full_directory(files, file_id):
        target_file = []

        for _file in files:
            if _file['id'] == file_id:
                target_file = _file
                break
        if not target_file:
            return ''
        if len(target_file['id']) < 20:
            location = '/'
            return location
        else:
            location = target_file['name']
        while True:
            if len(target_file['parents'][0]) < 20:
                return '/'+location
            for _file in files:
                if _file['id'] == str(target_file['parents'][0]):
                    location = _file['name'] + '/' + location
                    target_file = _file


# gdv
# Return filename's id if it's null return location's id
def ggdrive_get_file_id_from_entry(files, location, filename=""):
    if location == "":  # root
        if filename == "":
            for _file in files:
                if len(str(_file['parents'][0])) < 20:
                    return _file['parents'][0]
        else:
            for _file in files:
                if filename == _file['name'] and len(str(_file['parents'][0])) < 20:
                    return _file['id']
    if location.endswith('/'):
        location = location[:len(location)-1]
    _dir = location.split('/')
    if not _dir:
        return ''
    if filename != "":
        _dir += [filename]

    idx = 1
    for _file in files:
        if _dir[idx] == _file['name'] and len(str(_file['parents'][0])) < 20:
            parent_id = _file['id']
            idx += 1
            break
    else:
        return ''
    while idx < len(_dir):
        for _file in files:
            if _dir[idx] == _file['name'] and str(_file['parents'][0]) == parent_id:
                parent_id = _file['id']
                idx += 1
                break
        else:
            return ''
    return parent_id


# gdv
# Return a list of files in given directory.
# Its main purpose is modifying location information from name to id
def ggdrive_show_files(directory, files):
    file_list = []
    for _file in files:
        try:
            if str(_file['parents'][0]) == directory:
                file_list.append(_file)
        except KeyError:
            pass
    return file_list



@csrf_exempt
def detach_file(request):

    # test folder for exhibition
    file_location = '/Users/'+getpass.getuser()+'/Desktop/TestFolder/' + str(request.GET['filepath'])
    api_name = str(request.GET['name'])
    location = str(request.GET['location'])
    target_api = request.GET.getlist('target_api')

    target_api_info = []
    temp = file_location.split('/')

    _file = temp[len(temp)-1]
    _path = file_location[:(len(file_location)-len(_file))]
    os.chdir(_path)

    #split!
    file_id = str(uuid.uuid4())
    subprocess.Popen(["split -b 2000000 " + _file + " "+file_id+"-"], stdout=subprocess.PIPE, shell=True)
    temp = file_id+'*'
    time.sleep(1)   # subprocess run in asynchronously
    detached_files = fnmatch.filter(os.listdir('.'), temp)


    aio_user = AllinOneUser.objects.get(user=request.user)
    for i in range(0, len(target_api)):
        target_api_info.append(
            APIInfo.objects.get(
                aio_user_id_id=aio_user.aio_user_id,
                api_name=str(target_api[i])
            )
        )

    #save metadata
    i = 0
    for detached_file in detached_files:
        if not is_have_temp(target_api_info[i]):
            make_temp_directory(target_api_info[i])
        do_upload(target_api_info[i], _path+detached_file, '/Temp', detached_file)
        #TODO if there is no Temp folder it raise error only google

        metadata = DetachedFileMetaData(
            aio_user_id_id=aio_user.aio_user_id,
            origin_file=_file,
            origin_API=api_name,
            file_name=detached_file,
            file_id=file_id,
            stored_API=str(target_api[i])
        )
        metadata.save()

        i += 1
        if i == len(target_api):
            i = 0
    api_info = APIInfo.objects.get(
        aio_user_id_id=aio_user.aio_user_id,
        api_name=api_name
    )
    with open(_path+'/'+_file+'.metadata', 'wb'):
        do_upload(api_info, _path+_file+'.metadata', location, _file+'.metadata')

    delete_detached_file(file_id)

    url = reverse('main')+'?name='+api_name+'&location='+location

    return HttpResponseRedirect(url)


def is_have_temp(api_info):
    if api_info.api_type == 'dropbox':
        dbx = dropbox.Dropbox(api_info.api_user_access_token)

        temp = dbx.files_list_folder('').entries
        for _file in temp:
            if _file.name == 'Temp':
                return True
        return False

    if api_info.api_type == 'googledrive':
        drive_service = ggdrive_get_drive_service(api_info)

        temp_list = drive_service.files().list(
            fields='files(id, name, parents, size, modifiedTime, mimeType)').execute()
        temp_list = temp_list['files']
        location_id = ggdrive_get_file_id_from_entry(temp_list, '')
        temp_file_list = ggdrive_show_files(location_id, temp_list)
        for _file in temp_file_list:
            if _file['name'] == 'Temp':
                return True
        return False

    if api_info.api_type == 'onedrive':
        client = onedrive_get_auth_flow(api_info)

        temp_file_list = client.item(drive='me', path='/').children.get()

        for _file in temp_file_list:
            if _file.name == 'Temp':
                return True
        return False

    if api_info.api_type == 'ftp':
        user_data = api_info.api_user_access_token.split('/')
        ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

        temp_file_list = ftp.nlst()
        for _file in temp_file_list:
            if _file == 'Temp':
                return True
        return False
        ftp.close()


def make_temp_directory(api_info):
    if api_info.api_type == 'dropbox':
        dbx = dropbox.Dropbox(api_info.api_user_access_token)

        dropbox.Dropbox.files_create_folder(dbx, '/Temp')

    if api_info.api_type == 'googledrive':
        drive_service = ggdrive_get_drive_service(api_info)

        file_list = drive_service.files().list(fields='files(id, name, parents)').execute()
        parent_id = ggdrive_get_file_id_from_entry(file_list['files'], '')
        file_metadata = {
            'name': 'Temp',
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        drive_service.files().create(body=file_metadata, fields='id').execute()

    if api_info.api_type == 'onedrive':
        client = onedrive_get_auth_flow(api_info)

        _folder = onedrivesdk.Folder()
        _item = onedrivesdk.Item()
        _item.name = 'Temp'
        _item.folder = _folder

        client.item(drive='me', path='/').children.add(_item)

    if api_info.api_type == 'ftp':
        user_data = api_info.api_user_access_token.split('/')
        ftp = ftplib.FTP(api_info.api_user_id, user_data[0], user_data[1])

        ftp.mkd('Temp')
        ftp.close()


def delete_detached_file(file_id):
    temp = file_id+'*'
    time.sleep(1)
    subprocess.Popen(["rm "+temp], stdout=subprocess.PIPE, shell=True)
    subprocess.Popen(["rm *.metadata"], stdout=subprocess.PIPE, shell=True)
    return 0



def delete_metadata_file(request, file_name, location):
    aio_user = AllinOneUser.objects.get(user=request.user)
    metadata_info = DetachedFileMetaData.objects.filter(
        aio_user_id_id=aio_user.aio_user_id,
        origin_file=file_name[:len(file_name)-9]
    )
    for metadata in metadata_info:
        file_delete(request, [metadata.file_name], '/Temp', metadata.stored_API)
    file_delete(request, [file_name], location, metadata_info[0].origin_API)

    url = reverse('main')+'?name='+metadata_info[0].origin_API+'&location='+location
    metadata_info.delete()

    return HttpResponseRedirect(url)



def merge_file(request, file_name, location):

    aio_user = AllinOneUser.objects.get(user=request.user)
    metadata_info = DetachedFileMetaData.objects.filter(
        aio_user_id_id=aio_user.aio_user_id,
        origin_file=file_name[:len(file_name)-9]
    )
    for metadata in metadata_info:
        file_download(request, [metadata.file_name], '/Temp', metadata.stored_API)

    os.chdir('/Users/'+getpass.getuser()+'/Downloads')

    subprocess.Popen(
        ["cat "+metadata_info[0].file_id+"-[a-z][a-z] > "+metadata_info[0].origin_file],
        stdout=subprocess.PIPE,
        shell=True
    )
    time.sleep(1)
    delete_detached_file(metadata_info[0].file_id)

    url = reverse('main') + '?name=' + metadata_info[0].origin_API + '&location=' + location

    return HttpResponseRedirect(url)





#AUTH PROCESS###########################################################################################################
########################################################################################################################


def dropbox_auth_start(request):
    return HttpResponseRedirect(dropbox_get_auth_flow(request).start())



def dropbox_auth_finish(request):
    try:
        access_token, user_id, url_state = dropbox_get_auth_flow(request).finish(request.GET)

        aio_user = AllinOneUser.objects.get(user=request.user)
        api_filter = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id, api_user_id=user_id)
        if api_filter.count() == 0:
            api_info = APIInfo(
                aio_user_id_id=aio_user.aio_user_id,
                api_name='unknown',
                api_type='dropbox',
                api_user_id=user_id,
                api_user_access_token=access_token
            )
            api_info.save()
            request.session['aio_user_id'] = aio_user.aio_user_id

            return HttpResponseRedirect(reverse('addaccount'))
        else:
            raise APIInfoAlreadyExist
    except APIInfoAlreadyExist:
        url = reverse('main')+'?name=home&location'
        return HttpResponseRedirect(url, {'error': 'same api already exist'})
    except DropboxOAuth2Flow.BadRequestException:
        return HttpResponseBadRequest()
    except DropboxOAuth2Flow.BadStateException:
        return HttpResponseBadRequest()
    except DropboxOAuth2Flow.CsrfException:
        return HttpResponseForbidden()
    except DropboxOAuth2Flow.NotApprovedException:
        return render(request, 'main.html', {'error': 'Why not aprrove?'})
    except DropboxOAuth2Flow.ProviderException:
        return HttpResponseForbidden()



def dropbox_get_auth_flow(request):

    redirect_uri = request.build_absolute_uri(reverse('dropbox_auth_finish'))
    _keys = settings.DROPBOX_SETTINGS
    return DropboxOAuth2Flow(
        _keys['APP_KEY'], _keys['APP_SECRET'], redirect_uri, request.session, 'dropbox-auth-csrf-token')



def ftp_auth(request):
    if request.method == 'GET':
        return render(request, 'ftpform.html', {'user_info': request.user})
    elif request.method == 'POST':
        try:
            hostname = str(request.POST['hostname'])
            username = str(request.POST['username'])
            password = str(request.POST['password'])

            if username == '' or password == '' or hostname == '':
                raise DataNotExist

            if ftplib.FTP(hostname, username, password):
                aio_user = AllinOneUser.objects.get(user=request.user)
                api_filter = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id, api_user_id=hostname)
                if api_filter.count() == 0:
                    api_info = APIInfo(
                        aio_user_id_id=aio_user.aio_user_id,
                        api_name='unknown',
                        api_type='ftp',
                        api_user_id=hostname,
                        api_user_access_token=username+'/'+password
                    )
                    api_info.save()
                    request.session['aio_user_id'] = aio_user.aio_user_id
                    return HttpResponseRedirect(reverse('addaccount'))
                else:
                    raise APIInfoAlreadyExist
            else:
                raise FtpNotExist
        except APIInfoAlreadyExist:
            url = reverse('main') + '?name=home&location'
            return HttpResponseRedirect(url, {'error': 'same api already exist'})
        except DataNotExist:
            return render(request, 'ftpform.html', {'error': 'complete your ftp information'})
        except FtpNotExist:
            return render(request, 'ftpform.html', {'error': 'invalid information'})
    else:
        return HttpResponseBadRequest()



def ggdrive_auth_start(request):
    return HttpResponseRedirect(ggdrive_get_auth_flow(request).step1_get_authorize_url())



def ggdrive_get_auth_flow(request):
    flow = OAuth2WebServerFlow(
        client_id=settings.GOOGLEDRIVE_SETTINGS['client_id'],
        client_secret=settings.GOOGLEDRIVE_SETTINGS['client_secret'],
        scope=settings.GOOGLEDRIVE_SETTINGS['SCOPES'],
        redirect_uri=request.build_absolute_uri(reverse('ggdrive_auth_finish')))
    return flow



def ggdrive_auth_finish(request):
    try:
        flow = ggdrive_get_auth_flow(request)
        auth_code = request.GET.get('code')
        ggdrive_credentials = flow.step2_exchange(auth_code)
        access_token = ggdrive_credentials.get_access_token(httplib2.Http())

        http_auth = ggdrive_credentials.authorize(httplib2.Http())
        drive_service = discovery.build(
            'drive',
            'v3',
            http=http_auth,
            developerKey=settings.GOOGLEDRIVE_SETTINGS['APPLICATION_KEY'],
        )
        user = drive_service.about().get(fields='user').execute()
        aio_user = AllinOneUser.objects.get(user=request.user)

        write_credentials(
            'credentials.json',
            ggdrive_credentials,
            '{"aio_user_id": "'+aio_user.aio_user_id+'", "api_user_id": "'+user['user']['emailAddress']+'"}'
        )

        api_filter = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id, api_user_id=flow.client_id)

        if api_filter.count() == 0:
            api_info = APIInfo(
                aio_user_id_id=aio_user.aio_user_id,
                api_name='unknown',
                api_type='googledrive',
                api_user_id=user['user']['emailAddress'],
                api_user_access_token=str(access_token.access_token)
            )
            api_info.save()
            request.session['aio_user_id'] = aio_user.aio_user_id
            return HttpResponseRedirect(reverse('addaccount'))
        else:
            raise APIInfoAlreadyExist
    except APIInfoAlreadyExist:
        url = reverse('main')+'?name=home&location'
        return HttpResponseRedirect(url, {'error': 'same api already exist'})
    except DropboxOAuth2Flow.BadRequestException:
        return HttpResponseBadRequest()
    except DropboxOAuth2Flow.BadStateException:
        return HttpResponseBadRequest()
    except DropboxOAuth2Flow.CsrfException:
        return HttpResponseForbidden()
    except DropboxOAuth2Flow.NotApprovedException:
        return render(request, 'main.html', {'error': 'Why not aprrove?'})
    except DropboxOAuth2Flow.ProviderException:
        return HttpResponseForbidden()



def ggdrive_get_drive_service(api_info):
    ggdrive_credentials = read_credentials('credentials.json', api_info)
    access_token = api_info.api_user_access_token
    ggdrive_credentials.access_token = access_token
    ggdrive_credentials.refresh(httplib2.Http())
    http_auth = ggdrive_credentials.authorize(httplib2.Http())
    drive_service = discovery.build(
        'drive',
        'v3',
        http=http_auth,
        developerKey=settings.GOOGLEDRIVE_SETTINGS['APPLICATION_KEY'],
    )
    return drive_service


def read_credentials(fname, api_info):
    if os.path.isfile(fname):
        f = open(fname, "r")
        str_data_list = f.read().split('***')
        str_data_list = str_data_list[:(len(str_data_list)-1)]
        for str_data in str_data_list:
            json_data = json.loads(str_data)
            if json_data['serial']['api_user_id'] == api_info.api_user_id and json_data['serial']['aio_user_id'] == api_info.aio_user_id_id:
                credentials = Credentials.new_from_json(json.dumps(json_data['credential']))
                print 'ok'
        f.close()
    else:
        credentials = None

    return credentials

def write_credentials(fname, credentials, serial):
    f = file(fname, "a")
    str_data = '{"serial": '+serial+', "credential": '+credentials.to_json()+'}***'
    f.write(str_data)
    f.close()


def onedrive_auth_start(request):
    try:
        http_provider = onedrivesdk.HttpProvider()
        redirect_uri = 'http://localhost:8080/'
        _keys = settings.ONEDRIVE_SETTINGS
        scopes = ['wl.signin', 'wl.offline_access', 'onedrive.readwrite']
        client = onedrivesdk.get_default_client(_keys['APP_KEY'], scopes=scopes)

        auth_url = client.auth_provider.get_auth_url(redirect_uri)
        code = GetAuthCodeServer.get_auth_code(auth_url, redirect_uri)

        auth_provider = onedrivesdk.AuthProvider(http_provider, _keys['APP_KEY'], scopes=scopes)
        auth_provider.authenticate(code, redirect_uri, _keys['APP_SECRET'])
        auth_provider.save_session()

#        user_id = client.drives["me"].get().owner.user.id

        aio_user = AllinOneUser.objects.get(user=request.user)
        api_filter = APIInfo.objects.filter(aio_user_id_id=aio_user.aio_user_id, api_user_id=user_id)
        if api_filter.count() == 0:
            api_info = APIInfo(
                aio_user_id_id=aio_user.aio_user_id,
                api_name='unknown',
                api_type='onedrive',
                api_user_id=user_id,            # TODO this value must be unique
                api_user_access_token=_keys['APP_KEY']
            )
            api_info.save()
            request.session['aio_user_id'] = aio_user.aio_user_id

            return HttpResponseRedirect(reverse('addaccount'))
        else:
            raise APIInfoAlreadyExist
    except APIInfoAlreadyExist:
        url = reverse('main') + '?name=home&location'
        return HttpResponseRedirect(url, {'error': 'same api already exist'})



def onedrive_get_auth_flow(api_info):
    base_url = 'https://api.onedrive.com/v1.0/'
    http_provider = onedrivesdk.HttpProvider()
    scopes = ['wl.signin', 'wl.offline_access', 'onedrive.readwrite']
    auth_provider = onedrivesdk.AuthProvider(http_provider, api_info.api_user_access_token, scopes=scopes)
    auth_provider.load_session()
    auth_provider.refresh_token()
    client = onedrivesdk.OneDriveClient(base_url, auth_provider, http_provider)
    return client



def api_unlink(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login'))
    else:
        api_name = str(request.GET['name'])
        aio_user = AllinOneUser.objects.get(user=request.user)
        api_info = APIInfo.objects.get(
            aio_user_id_id=aio_user.aio_user_id,
            api_name=api_name
        )
        api_info.delete()
        url = reverse('main') + '?name=home&location='

        return HttpResponseRedirect(url)
