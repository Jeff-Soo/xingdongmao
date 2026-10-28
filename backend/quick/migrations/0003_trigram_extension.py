from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0002_quickpattern_default_mode_quickfavorite'),
    ]

    operations = [
        TrigramExtension(),
    ]
