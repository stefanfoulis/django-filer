# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filer', '0007_auto_20161016_1055'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='deletion_requested',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='file',
            name='is_live',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='file',
            name='live',
            field=models.OneToOneField(related_name='draft', null=True, default=None, editable=False, to='filer.File', blank=True),
        ),
        migrations.AddField(
            model_name='file',
            name='published_at',
            field=models.DateTimeField(default=None, null=True, editable=False, blank=True),
        ),
    ]
