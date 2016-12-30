# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-12-30 18:52
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.auth.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0008_alter_user_username_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AllinOneUser',
            fields=[
                ('aio_user_id', models.CharField(blank=True, max_length=200, primary_key=True, serialize=False)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'AllinOne User',
                'verbose_name_plural': 'AllinOne Users',
            },
            bases=('auth.user',),
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='APIInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_name', models.CharField(max_length=20)),
                ('api_type', models.CharField(blank=True, max_length=20, null=True)),
                ('api_user_id', models.CharField(blank=True, max_length=200, null=True)),
                ('api_user_access_token', models.CharField(blank=True, max_length=200, null=True)),
                ('aio_user_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='All_in_one.AllinOneUser')),
            ],
        ),
        migrations.CreateModel(
            name='DetachedFileMetaData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origin_file', models.CharField(max_length=100)),
                ('origin_API', models.CharField(max_length=20)),
                ('file_name', models.CharField(max_length=100)),
                ('file_id', models.CharField(max_length=40)),
                ('stored_API', models.CharField(max_length=20)),
                ('aio_user_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='All_in_one.AllinOneUser')),
            ],
        ),
    ]
