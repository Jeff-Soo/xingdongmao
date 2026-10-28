from django.conf import settings

from tasks.models import TaskDay, local_today

# 用来区分"没传 day"和"传了 day=None（今天没有记录）"——
# 两者语义完全不同：前者要自己查一下，后者就是"今天还没动过"，进度必须是 0。
_DAY_UNSET = object()


def user_display_name(user, fallback='行动锚用户'):
    """从一个【用户】算出对外显示名 —— #070/#071 的唯一口径（分享图、App、资料区都走它）。

    顺序：昵称（#071 新加的字段）→ 邮箱前缀 → 都不体面就用 fallback。
    「不体面」包括：空、纯数字（像 10000000 这种机器号）、`wx_` 开头的微信占位邮箱
    （#057③：前缀就是 openid，绝不能露）、长度 < 2。
    """
    if user is None:
        return fallback
    nickname = (getattr(user, 'nickname', '') or '').strip()
    if nickname and len(nickname) >= 2 and not nickname.isdigit():
        return nickname
    email = (getattr(user, 'email', '') or '').strip()
    name = email.split('@')[0].strip() if email else ''
    if not name or name.startswith('wx_') or email.endswith('@wx.local'):
        return fallback
    if name.isdigit() or len(name) < 2:
        return fallback
    return name


def author_display_name(qp, official=False):
    """模板作者的对外显示名 —— **全站唯一口径**。

    App 端（列表 / 详情 / 我的-我创建的）与分享图都调这一个函数（#070），
    所以两边永远显示同一个名字，不会再出现"分享图一个、App 一个"。

    规则（#069 定的，两边一致）：
      ① `is_official` 的模板                      → 「行动锚」（品牌名，体面）
      ② 用户模板 + 有昵称 / 可读邮箱前缀            → 该名字（#071 起昵称优先）
      ③ 用户模板 + 机器号 / 微信占位 / 太短         → 「行动锚用户」
           —— 具体判断收敛在 user_display_name()，这里只加"官方/不露名"这一层
      ④ `official=True`（小程序侧不带 ?author=1）   → 「行动锚」
           —— #029 的约定：小程序审核侧永远看不到用户昵称
           （UGC 关闭时同样走这一支，行为与 #029 一致）

    `official=True` 只在"调用方明确要求不露名"时使用（分享图的小程序侧）；
    App 端不传，靠 ①②③ 决定。
    """
    if official or getattr(qp, 'is_official', False) or not getattr(settings, 'ENABLE_UGC', False):
        return '行动锚'
    return user_display_name(getattr(qp, 'author', None))


def serialize_step(s):
    return {
        # #079 Step 3：详情页「把这一步加入任务」需要 QuickStep 主键（from-step 接口按它取），
        # 以前这里没下发 id，前端拿不到步骤身份。纯新增字段，老调用方不受影响。
        'id': s.pk,
        'order': s.order,
        'title': s.title,
        'instruction': s.instruction,
        'explain': s.explain,
        'duration_seconds': s.duration_seconds,
        'is_timed': s.is_timed,
    }


# ===== #079：日常任务（UserTask / UserTaskStep）=====

def serialize_task_step(s, is_done=None):
    """任务步骤 —— 前 7 个键跟 serialize_step 完全对齐，
    所以执行页的 toStepData（utils/adapter.js）能直接吃，不用再写一套映射。

    #087：is_done 改成"今天勾没勾"（由调用方从今天的 TaskDay 算好传进来）；
    不传才回落到旧的全局字段。
    """
    if is_done is None:
        is_done = s.is_done
    return {
        'order': s.order,
        'title': s.title,
        'instruction': s.instruction,
        'explain': s.explain,
        'duration_seconds': s.duration_seconds,
        'is_timed': s.is_timed,
        # 以下是"任务"独有的（模板步骤没有"完成"概念）
        'id': s.pk,
        'is_done': is_done,
        'done_at': s.done_at.isoformat() if s.done_at else None,
        'source_step': s.source_step_id,
    }


def serialize_task(task, total=None, done=None, include_steps=False, steps=None, day=_DAY_UNSET):
    """一条任务。total 由调用方从 annotate 里传进来，避免列表页 N+1。

    #087：进度按【今天】算 —— day 是今天的 TaskDay（今天没动过就是 None）。
    - 不传 day：这里自己查一次今天的记录（单条任务路径够用）
    - 传 day=None：今天还没动过 → 进度 0（列表接口走这条，已经批量查好了）
    done 参数只为兼容旧调用保留；进度一律以 TaskDay 为准 ——
    step.is_done 只是"今天"的缓存，昨天勾的绝不能算进今天。
    """
    if total is None:
        total = task.steps.count()
    if day is _DAY_UNSET:
        day = TaskDay.objects.filter(task=task, date=local_today()).first()
    if day is not None:
        done = min(len(day.done_step_ids or []), total)
    else:
        done = 0
    progress = round(done / total, 4) if total else 0.0
    done_today = bool(day is not None and total > 0 and done >= total and day.completed)

    data = {
        'id': task.pk,
        'title': task.title,
        'description': task.description,
        'kind': task.kind,
        'frequency_type': task.frequency_type,
        'frequency_label': task.get_frequency_type_display(),
        'quota_period': task.quota_period,
        'quota_count': task.quota_count,
        'persist': task.persist,
        'persist_label': task.get_persist_display(),
        'target_count': task.target_count,
        'done_count': task.done_count,
        # 剩余次数：target 为空（不限）时是 None，前端要显示"不限"
        'remaining_count': task.remaining_count,
        # #087：今天的完成情况（前端据此说"今天还没开始 / 今天做完了"）
        'done_today': done_today,
        'today_steps_done': done,
        'today': local_today().isoformat(),
        'timeslot': task.timeslot,
        'timeslot_label': task.get_timeslot_label(),
        # 预留字段：本轮不算，只把值带出去
        'expected_at': task.expected_at.isoformat() if task.expected_at else None,
        'deadline': task.deadline.isoformat() if task.deadline else None,
        # #085：排到哪一天（'YYYY-MM-DD'；空 = 还没排期）
        'plan_date': task.plan_date.isoformat() if task.plan_date else None,
        'status': task.status,
        'status_label': task.get_status_display(),
        'steps_total': total,
        'steps_done': done,
        'progress': progress,
        'created_at': task.created_at.isoformat(),
        'updated_at': task.updated_at.isoformat(),
    }

    # 来源模板：列表页也要能画矢量图标（#073 的 icon_key），所以带 id/title/icon_key
    pattern = task.source_pattern
    data['source_pattern'] = None if pattern is None else {
        'id': pattern.pk,
        'title': pattern.title,
        'icon_key': pattern.icon_key,
        'icon': pattern.icon,
    }

    if include_steps:
        if steps is None:
            steps = list(task.steps.all())
        # #087：某一步"今天勾没勾"= 它 id 在不在今天的 TaskDay 里；今天没记录就全是 False
        ids = set(day.done_step_ids or []) if day is not None else set()
        data['steps'] = [
            serialize_task_step(s, is_done=(s.pk in ids)) for s in steps
        ]
    return data


def serialize_quick(qp):
    steps = list(qp.steps.all())
    return {
        'id': qp.pk,
        'title': qp.title,
        'tagline': qp.tagline,
        'description': qp.description,
        'icon': qp.icon,
        # #073：矢量图标 slug（前端优先用它画图标；为空才回退到上面的 emoji）
        'icon_key': qp.icon_key,
        'category': qp.get_category_display(),
        'category_key': qp.category,
        'usage_count': qp.usage_count,
        'avg_rating': qp.avg_rating,
        'rating_count': qp.rating_count,
        'status': qp.status,
        # #057 P2-①：三个布尔一起下发（列表/详情/我创建的 用同一份），
        # 前端才能正确显示"待复核/已上架/已推荐"，不用去猜派生的 status
        'is_listed': qp.is_listed,
        'is_verified': qp.is_verified,
        'is_reported': qp.is_reported,
        'is_official': qp.is_official,
        'allow_fork': qp.allow_fork,
        'author': qp.author_id,
        'author_name': author_display_name(qp),
        'is_favorited': False,
        'favorite_count': len(qp.favorites.all()),
        'step_count': len(steps),
        'created_at': qp.created_at.isoformat(),
        'steps': [serialize_step(s) for s in steps],
    }
