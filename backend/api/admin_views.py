"""后台监控看板的数据来源（Admin 首页用，渲染见 templates/admin/dashboard_panel.html）。

只做"计数 + 异常提示"，不追求图表。查询都走聚合，数据量大了也不会拖慢后台。
"""
from datetime import timedelta

from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from quick.models import QuickPattern, QuickRating, QuickUsage
from users.models import User

# 异常判定阈值：先拍几个保守值，误报多了就调这里
USAGE_SPIKE_24H = 10    # 单模板 24h 内被使用 ≥ 10 次 → 提示"可能被刷"
PATTERN_SPIKE_24H = 5   # 单用户 24h 内发布 ≥ 5 个模板 → 提示"可能恶意"
ALERT_LIMIT = 5         # 每类最多列几条，后台首页别被刷屏


def _changelist(model_label, query=''):
    return reverse(f'admin:{model_label}_changelist') + query


def dashboard_stats():
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since_24h = now - timedelta(hours=24)

    patterns = QuickPattern.objects.all()
    usages = QuickUsage.objects.all()

    users_total = User.objects.count()
    users_today = User.objects.filter(date_joined__gte=today).count()
    patterns_total = patterns.count()
    patterns_today = patterns.filter(created_at__gte=today).count()
    published_total = patterns.filter(is_listed=True, is_reported=False).count()
    usages_total = usages.count()
    usages_today = usages.filter(used_at__gte=today).count()
    reported = patterns.filter(is_reported=True).count()
    ratings_total = QuickRating.objects.count()

    patterns_url = _changelist('quick_quickpattern')
    users_url = _changelist('users_user')
    reported_url = _changelist('quick_quickpattern', '?is_reported__exact=1')

    cards = [
        {'label': '今日新增用户', 'value': users_today, 'sub': f'累计 {users_total}', 'url': users_url},
        {'label': '今日新增模板', 'value': patterns_today, 'sub': f'累计 {patterns_total}', 'url': patterns_url},
        {'label': '今日使用次数', 'value': usages_today, 'sub': f'累计 {usages_total}', 'url': ''},
        {'label': '公开可见模板', 'value': published_total, 'sub': f'草稿/已下架 {patterns_total - published_total}', 'url': patterns_url},
        {'label': '待处理举报', 'value': reported, 'sub': '需要人工判断', 'url': reported_url, 'danger': reported > 0},
        {'label': '累计评分', 'value': ratings_total, 'sub': '后端只存 1-5 星', 'url': _changelist('quick_quickrating')},
    ]

    # 评分分布（1-5 星各多少条）
    raw = dict(QuickRating.objects.values_list('stars').annotate(n=Count('stars')))
    rating_dist = [
        {
            'stars': stars,
            'count': raw.get(stars, 0),
            'percent': round(raw.get(stars, 0) * 100 / ratings_total) if ratings_total else 0,
        }
        for stars in (5, 4, 3, 2, 1)
    ]

    alerts = []
    if reported:
        alerts.append({
            'level': 'danger',
            'text': f'{reported} 条举报待处理',
            'hint': '勾选模板后选「① 下架」或「③ 忽略举报」',
            'url': reported_url,
        })

    # 24h 使用量突增：可能被刷，也可能真火了，让人工看一眼
    hot = (usages.filter(used_at__gte=since_24h)
           .values('pattern_id', 'pattern__title')
           .annotate(n=Count('id'))
           .filter(n__gte=USAGE_SPIKE_24H)
           .order_by('-n')[:ALERT_LIMIT])
    for row in hot:
        alerts.append({
            'level': 'warn',
            'text': f'「{row["pattern__title"]}」24 小时内被使用 {row["n"]} 次',
            'hint': '留意是否被刷量',
            'url': _changelist('quick_quickpattern', f'?id__exact={row["pattern_id"]}'),
        })

    # 24h 内集中发布：可能是恶意灌水
    flood = (patterns.filter(created_at__gte=since_24h)
             .values('author_id', 'author__email')
             .annotate(n=Count('id'))
             .filter(n__gte=PATTERN_SPIKE_24H)
             .order_by('-n')[:ALERT_LIMIT])
    for row in flood:
        alerts.append({
            'level': 'warn',
            'text': f'用户 {row["author__email"]} 24 小时内发布了 {row["n"]} 个模板',
            'hint': '留意是否灌水，必要时封禁',
            'url': _changelist('quick_quickpattern', f'?author__id__exact={row["author_id"]}'),
        })

    return {
        'cards': cards,
        'rating_dist': rating_dist,
        'ratings_total': ratings_total,
        'alerts': alerts,
        'reported_url': reported_url,
        'patterns_url': patterns_url,
        'users_url': users_url,
    }
