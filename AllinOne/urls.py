"""AllinOne URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from All_in_one import views


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^login/$', views.do_login, name='login'),
    url(r'^logout/$', views.do_logout, name='logout'),
    url(r'^signup/$', views.signup, name='signup'),
    url(r'^addaccount/$', views.add_account, name='addaccount'),
    url(r'^selecttype/$', views.select_type, name='selecttype'),

    url(r'^$', views.main, name='main'),
    url(r'^modify/$', views.modify, name='modify'),

    url(r'^filecheck/$', views.file_check, name='filecheck'),
    url(r'^newfolder/$', views.new_folder, name='newfolder'),
    url(r'^download/$', views.file_download, name='download'),
    url(r'^upload/$', views.file_upload, name='fileupload'),
    url(r'^delete/$', views.file_delete, name='delete'),
    url(r'^search/$', views.search_file, name='search'),
    url(r'^detach_upload/$', views.detach_file, name='datach_upload'),

    url(r'^dropbox_auth_start/$', views.dropbox_auth_start, name='dropbox_auth_start'),
    url(r'^dropbox_auth_finish/$', views.dropbox_auth_finish, name='dropbox_auth_finish'),

    url(r'^ftp_auth/$', views.ftp_auth, name='ftp_auth'),

    url(r'^ggdrive_auth_start/$', views.ggdrive_auth_start, name='ggdrive_auth_start'),
    url(r'^ggdrive_auth_finish/$', views.ggdrive_auth_finish, name='ggdrive_auth_finish'),

    url(r'^onedrive_auth_start/$', views.onedrive_auth_start, name='onedrive_auth_start'),

    url(r'^api_unlink/$', views.api_unlink, name='api_unlink'),
]
