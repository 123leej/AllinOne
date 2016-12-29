from __future__ import unicode_literals

from django.db import models
from django.contrib import auth

class AllinOneUser(auth.models.User):
    class Meta:
        verbose_name = 'AllinOne User'
        verbose_name_plural = 'AllinOne Users'

    user = models.OneToOneField(auth.models.User)
    aio_user_id = models.CharField(max_length=200, blank=True, null=False, primary_key=True)

class APIInfo(models.Model):
    aio_user_id = models.ForeignKey(AllinOneUser)
    api_name = models.CharField(max_length=20, blank=False, null=False)
    api_type = models.CharField(max_length=20, blank=True, null=True)
    api_user_id = models.CharField(max_length=200, blank=True, null=True)
    api_user_access_token = models.CharField(max_length=200, blank=True, null=True)

class DetachedFileMetaData(models.Model):
    aio_user_id = models.ForeignKey(AllinOneUser)
    origin_file = models.CharField(max_length=100, blank=False, null=False)
    origin_API = models.CharField(max_length=20, blank=False, null=False)
    file_name = models.CharField(max_length=100, blank=False, null=False)
    file_id = models.CharField(max_length=40, blank=False, null=False)
    stored_API = models.CharField(max_length=20, blank=False, null=False)
