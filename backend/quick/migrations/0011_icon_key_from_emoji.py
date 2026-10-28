# -*- coding: utf-8 -*-
"""#073：把存量模板的 emoji 图标映射成矢量图标 slug（icon_key）。

为什么用数据迁移而不是脚本：服务器上只要跑 `manage.py migrate` 就会一起生效，
不用记得额外执行什么东西；而且它是幂等的（只填 icon_key 为空的行）。

反过来（reverse）不清空：slug 是新体系的唯一来源，回滚到旧版本时前端会忽略它，
把用户的图标选择删掉才是更糟的行为。
"""
from django.db import migrations

# emoji → slug。键按"去掉变体选择符 U+FE0F"后的字符比对（DB 里 '🍽️'/'⚠️'/'🗣️' 都带 FE0F）
EMOJI_TO_SLUG = {
    '📋': 'clipboard-text',
    '✅': 'check-square',
    '🧠': 'brain',
    '🚪': 'door',
    '📦': 'package',
    '🏠': 'house',
    '🛒': 'shopping-cart',
    '🍽': 'fork-knife',
    '🥘': 'cooking-pot',
    '🔥': 'flame',
    '🔧': 'wrench',
    '🧹': 'broom',
    '💼': 'briefcase',
    '🔄': 'arrows-clockwise',
    '⚠': 'warning',
    '📝': 'note-pencil',
    '🔑': 'key',
    '🗣': 'chat-circle-dots',
    '🍃': 'plant',
    '⏰': 'clock',
    '🚗': 'car',
    '❤': 'heart',
    '📅': 'calendar',
}


def emoji_to_slug(apps, schema_editor):
    QuickPattern = apps.get_model('quick', 'QuickPattern')
    for qp in QuickPattern.objects.filter(icon_key=''):
        key = (qp.icon or '').replace('\ufe0f', '').strip()
        slug = EMOJI_TO_SLUG.get(key)
        if slug:
            qp.icon_key = slug
            qp.save(update_fields=['icon_key'])


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0010_quickpattern_icon_key_alter_quickpattern_icon'),
    ]

    operations = [
        migrations.RunPython(emoji_to_slug, migrations.RunPython.noop),
    ]
