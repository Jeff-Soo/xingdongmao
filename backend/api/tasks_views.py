"""#079 Step 2：日常任务（UserTask）的 8 个接口。

放在单独模块而不是塞进 1600 行的 api/views.py —— 这一块是全新的领域（任务/日程），
独立文件更好 review；复用 api/views.py 里现成的响应格式、token 认证和 JSON 解析，
不重复造轮子（约定见 api/views.py 顶部）。

安全口径（AGENTS.md §2）：所有查询都带 user=request.user；
别人的任务一律 404「任务不存在」，不泄露"存在但不是你的"。

不挂 require_ugc：任务/日程是【用户私密数据】，不是对外发布的 UGC，
ENABLE_UGC=False 时也不该把"我的任务"关掉。
"""

import re
from datetime import date, datetime, time as dtime, timedelta

from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from quick.models import QuickPattern, QuickStep
from tasks.models import TIMESLOT_ORDER, TaskDay, UserTask, UserTaskStep, local_today, today_tasks

from .serializers import serialize_task, serialize_task_step
from .views import _json_body, api_response, require_token

FREQ_CHOICES = ('once', 'quota', 'habit')
QUOTA_PERIODS = ('week', 'day')
PERSIST_CHOICES = ('streak', 'cumulative')
STATUS_CHOICES = ('active', 'done', 'archived')
MAX_TITLE = 100
MAX_TIMESLOT = 20
MAX_DESC = 2000
_MAX_COUNT = 9999          # 目标/配额次数的上限，防手滑填 10 万次
_MONTH_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
PAGE_SIZE_DEFAULT = 20     # #088 分页默认页大小
PAGE_SIZE_MAX = 100        # 上限：再大就等于全量，分页没意义


def _page_url(request, page):
    """第 N 页的绝对地址（next/previous 用）。只改 page，其它筛选条件原样带上"""
    params = request.GET.copy()
    params['page'] = str(page)
    return request.build_absolute_uri(request.path) + '?' + params.urlencode()


# ===== 小工具 =====

def _s(value, limit):
    """字符串清洗：去首尾空白 + 截断（None → ''）"""
    return str(value or '').strip()[:limit]


def _to_int(value, default=None):
    """宽松整数：'' / None / 非数字 → default；负数按 0；超上限按上限"""
    if value is None or value == '':
        return default
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(_MAX_COUNT, n))


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return default


def _parse_dt(value):
    """解析 expected_at。返回 (时间, 错误信息)；空值返回 (None, None)。"""
    if value in (None, ''):
        return None, None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = parse_datetime(str(value).strip())
        except ValueError:
            # '2026-13-45T00:00:00' 这种，parse_datetime 会直接抛
            dt = None
    if dt is None:
        # 也接受纯日期，按当天 23:59 算（用户"明天做完"这种输入）
        try:
            d = parse_date(str(value).strip()[:10])
        except ValueError:
            d = None
        if d is None:
            return None, 'expected_at 格式不对（要 ISO 时间，如 2026-10-20T18:00:00）'
        dt = datetime.combine(d, dtime(23, 59))
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt, None


def _parse_plan_date(value):
    """解析 plan_date（#085）。返回 (date, 错误信息)；空值返回 (None, None)。

    - 收 'YYYY-MM-DD'（前端 <picker mode="date"> 给的就是这个）
    - 也收完整的 ISO 时间串，只取日期部分（"明天 18:00" 这种输入不至于报错）
    - 空串 = 清空排期（PATCH 时用来把任务从时间轴上撤下来）
    """
    if value in (None, ''):
        return None, None
    if isinstance(value, datetime):
        return value.date(), None
    if isinstance(value, date):
        return value, None
    raw = str(value).strip()
    try:
        d = parse_date(raw[:10])
    except ValueError:
        # '2026-13-45' 这种会让 parse_date 直接抛 ValueError，得当成格式错而不是 500
        d = None
    if d is None:
        return None, 'plan_date 格式不对（要 YYYY-MM-DD，比如 2026-10-22）'
    return d, None


def _clean_frequency(data, current=None):
    """频率/配额的统一清洗：一次建、一次改都走这里，避免两处规则漂移。

    - frequency_type 只认三选一
    - 不是 quota 就把 quota_* 清空（否则会出现"一次性任务还挂着每周 3 次"的脏数据）
    - quota 必须给 quota_period 和 quota_count（period 默认 week，count 必须 ≥1）
    """
    freq = _s(data.get('frequency_type'), 10) or (current.frequency_type if current else 'once')
    if freq not in FREQ_CHOICES:
        return None, 'frequency_type 只能是 once / quota / habit'

    if freq != 'quota':
        return {'frequency_type': freq, 'quota_period': '', 'quota_count': None}, None

    period = _s(data.get('quota_period'), 10) or (current.quota_period if current else 'week')
    if period not in QUOTA_PERIODS:
        return None, 'quota_period 只能是 week / day'
    count = _to_int(data.get('quota_count'), current.quota_count if current else None)
    if not count:
        return None, '配额制要填 quota_count（每周几次 / 每几天一次，至少 1）'
    return {'frequency_type': freq, 'quota_period': period, 'quota_count': count}, None


def _kind_for(freq, exist_kind=''):
    """kind 跟着 frequency 走：一次性 → once，配额/习惯 → routine。
    显式给了 kind 就尊重（spec 里两个字段并存），但别让它们自相矛盾。
    """
    if freq == 'once':
        return 'once'
    return 'routine' if exist_kind in ('', 'once') else exist_kind


def _task_payload(task, day=None):
    """详情/回写共用的返回体：steps + 总步数 + 今天做了几步（一次读，不重复查）

    #087：进度按【今天】的 TaskDay 算，不再看 step.is_done 这个全局布尔。
    """
    steps = list(task.steps.all())
    total = len(steps)
    if day is None:
        day = _today_day(task)
    return serialize_task(task, total=total, include_steps=True, steps=steps, day=day)


def _today_day(task, on_date=None):
    """今天的 TaskDay（没有就是 None = 今天还没动过）"""
    return TaskDay.objects.filter(task=task, date=on_date or local_today()).first()


def _apply_day(task, done_ids, on_date=None):
    """把"这一天勾了哪些步骤"写进 TaskDay，并返回写好的记录。

    completed 的判据是"现存步骤是否全在 done_ids 里"（不是 len 比较）：
    步骤后来加了一条，之前"全勾"的那天就不该还算完成。
    """
    on_date = on_date or local_today()
    # 显式走一次 COUNT：task.steps.count() 在 prefetch 过的实例上会读到旧缓存
    # （删步骤那条路径上就是"删完了还算 4 步"，导致完成态判断出错）
    total = UserTaskStep.objects.filter(task_id=task.pk).count()
    ids = sorted({int(i) for i in done_ids})
    completed = total > 0 and len(ids) >= total
    day, _ = TaskDay.objects.update_or_create(
        task=task,
        date=on_date,
        defaults={
            'user': task.user,
            'done_step_ids': ids,
            'done_count': len(ids),
            'completed': completed,
        },
    )
    return day


def _sync_step_flags(task, day):
    """把今天的勾选状态回写到 step.is_done / done_at（只是"今天"的缓存，读接口不依赖它）

    用两条批量 UPDATE，不逐条 save：删步骤那条路径上 task 是 prefetch 过的旧实例，
    里面还留着已经删掉的步骤对象，逐条 save 会撞 "did not affect any rows"（实测 500）。
    """
    ids = set(day.done_step_ids or [])
    now = timezone.now()
    task.steps.exclude(pk__in=ids).filter(is_done=True).update(is_done=False, done_at=None)
    task.steps.filter(pk__in=ids).exclude(is_done=True).update(is_done=True, done_at=now)


def _task_for_user(user, pk):
    """只取自己的任务（别人的一律当不存在）"""
    return (UserTask.objects.filter(pk=pk, user=user)
            .select_related('source_pattern').prefetch_related('steps').first())


def _target_count_for(data, freq_fields):
    """目标次数：显式给了就用；配额制没给就默认 = 本周期次数（一周 3 次 → 剩 3 次）。

    不这么兜底的话，配额制任务建出来 remaining_count 是 None，
    页面上"本周还剩 N 次"永远显示不出来，配额也就永远不会递减。
    """
    explicit = _to_int(data.get('target_count'))
    if explicit is not None:
        return explicit
    if freq_fields.get('frequency_type') == 'quota':
        return freq_fields.get('quota_count')
    # #087：一次性任务天生"还剩 1 次" —— 不给默认值的话 remaining_count 是 None，
    # 前端会显示成"不限次数"，做完之后也不会归零
    if freq_fields.get('frequency_type') == 'once':
        return 1
    return None


def _snapshot_steps(task, quick_steps):
    """把 QuickStep 复制成 UserTaskStep（快照）。

    is_timed / source_step 都照抄：前者让执行页知道"要不要倒计时"，
    后者留一条回指的线（"这条任务是从哪个模板的哪一步拆出来的"）。
    """
    rows = []
    for i, qs in enumerate(quick_steps):
        rows.append(UserTaskStep(
            task=task,
            order=qs.order if qs.order is not None else i,
            title=_s(qs.title, MAX_TITLE),
            instruction=qs.instruction or '',
            explain=qs.explain or '',
            duration_seconds=qs.duration_seconds or 0,
            is_timed=bool(qs.is_timed),
            source_step=qs,
        ))
    if rows:
        UserTaskStep.objects.bulk_create(rows)


# ===== ① 创建 + ② 列表（同一路径，按方法分发）=====

@csrf_exempt
@require_token
def task_collection(request):
    if request.method == 'GET':
        return task_list(request)
    if request.method == 'POST':
        return task_create(request)
    return api_response({'error': '方法不允许'}, 405)


@transaction.atomic
def task_create(request):
    data = _json_body(request)
    user = request.user

    pattern = None
    pattern_id = _to_int(data.get('pattern_id'))
    if pattern_id:
        pattern = QuickPattern.objects.filter(pk=pattern_id).first()
        # 可见性走模板自己的唯一判据（作者能看自己的草稿，别人只能看已上架）
        if pattern is None or not pattern.can_view(user):
            return api_response({'error': '模板不存在'}, 404)
        # #089：allow_fork=False 的意思是"作者不让整份复制走"。整模板建任务本质就是
        # 完整副本（标题+描述+全部步骤），所以同一道闸门也必须拦；作者本人不受限。
        if not pattern.allow_fork and pattern.author_id != user.pk:
            return api_response({'error': '作者不让改这份做法'}, 403)

    title = _s(data.get('title'), MAX_TITLE) or (pattern.title if pattern else '')
    if not title:
        return api_response({'error': 'title 不能为空（不给 pattern_id 时必填）'}, 400)

    freq_fields, err = _clean_frequency(data)
    if err:
        return api_response({'error': err}, 400)

    persist = _s(data.get('persist'), 12) or 'cumulative'
    if persist not in PERSIST_CHOICES:
        return api_response({'error': 'persist 只能是 streak / cumulative'}, 400)

    expected_at, err = _parse_dt(data.get('expected_at'))
    if err:
        return api_response({'error': err}, 400)

    # #085：建任务时也能直接排到某天（"插到这天做"就是一次 POST，不用建完再 PATCH 一次）
    # #089：不传 plan_date 就默认排到今天 —— 「加入任务」之后必须立刻出现在任务页"今天"，
    # 否则用户加完看不见，以为没加上。显式传 '' 才是"先不排期"，这是保留空值的唯一方式。
    if 'plan_date' in data:
        plan_date, err = _parse_plan_date(data.get('plan_date'))
        if err:
            return api_response({'error': err}, 400)
    else:
        plan_date = local_today()

    task = UserTask.objects.create(
        user=user,
        title=title,
        description=_s(data.get('description'), MAX_DESC),
        source_pattern=pattern,
        kind=_kind_for(freq_fields['frequency_type'], _s(data.get('kind'), 10)),
        persist=persist,
        target_count=_target_count_for(data, freq_fields),
        timeslot=_s(data.get('timeslot'), MAX_TIMESLOT),
        expected_at=expected_at,
        plan_date=plan_date,
        status='active',
        **freq_fields,
    )

    if pattern is not None:
        _snapshot_steps(task, list(pattern.steps.all()))

    task = _task_for_user(user, task.pk)
    return api_response(serialize_task(task, include_steps=True), 201)


def task_list(request):
    user = request.user
    # 列表页用 annotate 一次算完进度，避免每行再查两次库（N+1）
    qs = (UserTask.objects.filter(user=user)
          .select_related('source_pattern')
          .annotate(
              n_total=Count('steps', distinct=True),
              # t-box 排序：早上 → 中午 → 下午 → 晚上 → 睡前 → 自定义（99）
              slot_rank=Case(
                  *[When(timeslot=slot, then=Value(rank)) for slot, rank in TIMESLOT_ORDER.items()],
                  default=Value(99), output_field=IntegerField(),
              ),
          ))

    status = _s(request.GET.get('status'), 10)
    if status == 'all':
        pass
    elif status in STATUS_CHOICES:
        qs = qs.filter(status=status)
    else:
        # 默认不把归档的混进来（归档 = 用户自己收起来了）
        qs = qs.exclude(status='archived')

    timeslot = _s(request.GET.get('timeslot'), MAX_TIMESLOT)
    if timeslot:
        qs = qs.filter(timeslot=timeslot)

    # #085：日程用 —— plan_date 精确某天，或 from/to 取一段（日/周/月三档都是范围查询）
    plan_date = _s(request.GET.get('plan_date'), 10)
    if plan_date:
        d, err = _parse_plan_date(plan_date)
        if err:
            return api_response({'error': err}, 400)
        qs = qs.filter(plan_date=d)

    date_from = _s(request.GET.get('from'), 10)
    date_to = _s(request.GET.get('to'), 10)
    if date_from or date_to:
        if date_from:
            d1, err = _parse_plan_date(date_from)
            if err:
                return api_response({'error': err}, 400)
            qs = qs.filter(plan_date__gte=d1)
        if date_to:
            d2, err = _parse_plan_date(date_to)
            if err:
                return api_response({'error': err}, 400)
            qs = qs.filter(plan_date__lte=d2)

    # #089：「今天的任务」= status='active' 且 plan_date=今天 —— 直接用模型里的唯一定义，
    # 不在视图里再写一份条件。三处口径一旦分叉，就是"任务排到 2030 也算今天"这类老 bug。
    # 用 pk__in 子查询而不是重复 filter：保证以后改定义只改 tasks/models.py 一处。
    want_today = _to_bool(request.GET.get('today'))
    if want_today:
        qs = qs.filter(pk__in=today_tasks(user).values('pk'))

    items = list(qs.order_by('slot_rank', '-updated_at'))
    total = len(items)

    # #088：分页。只有显式带 page / page_size 才分页 —— 线上 H5 和小程序现在都按
    # "一次全量"取（items 字段），默认行为一改，老客户端会只拿到前 20 条且不报错，
    # 那是最难查的一类 bug。所以：不带参数 → 老契约不变；带了才返回 results/next/previous。
    raw_page = _s(request.GET.get('page'), 10)
    raw_size = _s(request.GET.get('page_size'), 10)
    paged = bool(raw_page or raw_size)
    next_url = previous_url = None
    if paged:
        page = max(_to_int(raw_page, 1) or 1, 1)
        size = _to_int(raw_size, PAGE_SIZE_DEFAULT) or PAGE_SIZE_DEFAULT
        size = max(1, min(size, PAGE_SIZE_MAX))   # 上限钳制：page_size=999 也只给 100 条
        start = (page - 1) * size
        if start < total:
            items = items[start:start + size]
        else:
            items = []
        if start + size < total:
            next_url = _page_url(request, page + 1)
        if page > 1:
            previous_url = _page_url(request, page - 1)

    # #087：今天的 TaskDay 一次查出（一个任务一天一条，最多和 items 一样多），避免每行再查一次
    today = local_today()
    days = {
        d.task_id: d for d in TaskDay.objects.filter(
            user=user, date=today, task_id__in=[t.pk for t in items],
        )
    }
    rows = [serialize_task(t, total=t.n_total, day=days.get(t.pk)) for t in items]
    data = {
        'count': total,
        'today': today.isoformat(),
        # items 是老字段（H5/小程序都在用），分页时保留它 = results，老页面不会突然空掉
        'items': rows,
    }
    if want_today:
        # #089：任务页只显示"今天"，没排期的老任务会从这一页消失 —— 给它一个数字，
        # 前端才能提示"还有 N 件没排日子，去日程页排一下"，而不是让用户以为任务丢了。
        data['unscheduled'] = UserTask.objects.filter(
            user=user, status='active', plan_date__isnull=True,
        ).count()
    if paged:
        data.update({'results': rows, 'next': next_url, 'previous': previous_url})
    return api_response(data)


# ===== ④ 步骤：打勾 / 改内容（PATCH）· 删除（DELETE）=====

def _clean_step_fields(data, current=None):
    """步骤字段清洗（#080 加：标题/说明/为什么/时长/要不要倒计时）。

    只返回"传了的"字段，没传的不动 —— 打勾时只带 is_done，不该把标题一起重写。
    """
    out = {}
    if 'title' in data:
        title = _s(data.get('title'), MAX_TITLE)
        if not title:
            return None, '步骤标题不能为空'
        out['title'] = title
    if 'instruction' in data:
        out['instruction'] = _s(data.get('instruction'), MAX_DESC)
    if 'explain' in data:
        out['explain'] = _s(data.get('explain'), MAX_DESC)
    if 'duration_seconds' in data:
        raw = data.get('duration_seconds')
        if raw in (None, ''):
            out['duration_seconds'] = 0
        else:
            try:
                secs = int(raw)
            except (TypeError, ValueError):
                return None, '时长要填整数秒'
            if secs < 0:
                secs = 0
            # 上限单独判：_to_int 会先夹到 9999，那样"超 24 小时"就永远报不出来
            if secs > 86400:
                return None, '时长最多 24 小时（86400 秒）'
            out['duration_seconds'] = secs
    if 'is_timed' in data:
        out['is_timed'] = _to_bool(data.get('is_timed'))
    return out, None


@csrf_exempt
@require_http_methods(['PATCH', 'POST', 'DELETE'])
@require_token
@transaction.atomic
def task_step_toggle(request, pk, sid):
    task = _task_for_user(request.user, pk)
    if task is None:
        return api_response({'error': '任务不存在'}, 404)
    # #089：归档 = 用户自己收起来了，不是"还在做"。以前这里没拦，
    # 归档任务还能被勾、还会写今天那条 TaskDay，把"今天做完了几件"算进一件没在做的事。
    if task.status == 'archived':
        return api_response({'error': '这张已经收起来了，先放回进行中'}, 403)
    step = UserTaskStep.objects.filter(pk=sid, task=task).first()
    if step is None:
        return api_response({'error': '步骤不存在'}, 404)

    if request.method == 'DELETE':
        # 删步骤：任务还在（快照是任务自己的数据，不联动模板）
        was_day = _today_day(task)
        step.delete()
        # #087：今天那条 TaskDay 里也要把它摘掉，否则 done_count 会比实际步数还大
        if was_day is not None:
            ids = [i for i in (was_day.done_step_ids or []) if int(i) != int(sid)]
            day = _apply_day(task, ids)
            if was_day.completed and not day.completed:
                task.done_count = max(task.done_count - 1, 0)
                task.save(update_fields=['done_count', 'updated_at'])
            _sync_step_flags(task, day)
        task = _task_for_user(request.user, task.pk)
        payload = _task_payload(task)
        payload['deleted_step'] = sid
        return api_response(payload)

    data = _json_body(request)

    # #080：先处理"改内容"（标题/说明/时长/倒计时），和打勾互不影响
    fields, err = _clean_step_fields(data)
    if err:
        return api_response({'error': err}, 400)
    changed = ''
    if fields:
        for k, v in fields.items():
            setattr(step, k, v)
        step.save(update_fields=list(fields.keys()))

    # #087：勾选状态存在【今天】的 TaskDay 里，step.is_done 只是今天的缓存
    today = local_today()
    day = _today_day(task, today)
    ids = {int(i) for i in (day.done_step_ids or [])} if day is not None else set()
    was_done = int(sid) in ids
    was_completed = bool(day.completed) if day is not None else False

    if data.get('is_done') is not None:
        # 明确给了 is_done：按值设置（前端勾选/取消）
        new_value = _to_bool(data.get('is_done'))
    elif fields:
        # 只改内容、没提打勾：保持原状
        new_value = was_done
    else:
        # 什么都没给：当成"切换"（App 里一个 checkbox 点一下最省事）
        new_value = not was_done

    if bool(new_value):
        ids.add(int(sid))
    else:
        ids.discard(int(sid))
    day = _apply_day(task, ids, today)
    _sync_step_flags(task, day)

    # 完成次数与状态：以"今天这条任务是否全勾"为准，进/出全勾各记一次，反复点不会虚增。
    # 只有 once 会直接结单；quota/habit 保持 active（明天照样出现，重新从 0 开始勾）。
    if day.completed and not was_completed:
        task.done_count = task.done_count + 1
        if task.frequency_type == 'once':
            task.status = 'done'
        changed = 'completed'
    elif was_completed and not day.completed:
        task.done_count = max(task.done_count - 1, 0)
        if task.frequency_type == 'once' and task.status == 'done':
            task.status = 'active'
        changed = 'reopened'
    if changed:
        task.save(update_fields=['done_count', 'status', 'updated_at'])

    task = _task_for_user(request.user, task.pk)
    data_out = _task_payload(task, day)
    data_out['step'] = serialize_task_step(step, is_done=int(sid) in set(day.done_step_ids or []))
    data_out['change'] = changed
    return api_response(data_out)


# ===== #080 新增：加步骤（POST /tasks/<id>/steps/）=====

@csrf_exempt
@require_http_methods(['POST'])
@require_token
@transaction.atomic
def task_step_create(request, pk):
    task = _task_for_user(request.user, pk)
    if task is None:
        return api_response({'error': '任务不存在'}, 404)
    # #089：归档任务同样不能加步骤（同 toggle，归档 = 只读）
    if task.status == 'archived':
        return api_response({'error': '这张已经收起来了，先放回进行中'}, 403)

    data = _json_body(request)
    title = _s(data.get('title'), MAX_TITLE)
    if not title:
        return api_response({'error': '步骤标题不能为空'}, 400)

    fields, err = _clean_step_fields(data)
    if err:
        return api_response({'error': err}, 400)

    # 追加到末尾：取当前最大 order + 1（不用 count，删过中间步骤也不会撞号）
    last = task.steps.order_by('-order').values_list('order', flat=True).first()
    step = UserTaskStep.objects.create(
        task=task,
        order=(last or 0) + 1,
        title=title,
        instruction=fields.get('instruction', ''),
        explain=fields.get('explain', ''),
        duration_seconds=fields.get('duration_seconds', 0),
        is_timed=fields.get('is_timed', False),
    )
    # 加了新步骤（初始未完成）→ 之前"全勾"的任务状态要退回进行中（once）
    if task.status == 'done' and task.frequency_type == 'once':
        task.status = 'active'
        task.save(update_fields=['status', 'updated_at'])
    # #087：新步骤今天肯定没勾 → 今天那条 TaskDay 不再是"全完成"（连带把累计次数退一次）
    day = _today_day(task)
    if day is not None and day.completed:
        ids = list(day.done_step_ids or [])
        day = _apply_day(task, ids)
        if not day.completed:
            task.done_count = max(task.done_count - 1, 0)
            task.save(update_fields=['done_count', 'updated_at'])

    task = _task_for_user(request.user, task.pk)
    payload = _task_payload(task, day)
    payload['step'] = serialize_task_step(step, is_done=False)
    return api_response(payload, 201)


# ===== ③ 详情 / ⑤ 改任务 / ⑥ 删除或归档（同一路径，按方法分发）=====

@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'POST', 'DELETE'])
@require_token
@transaction.atomic
def task_item(request, pk):
    task = _task_for_user(request.user, pk)
    if task is None:
        return api_response({'error': '任务不存在'}, 404)

    # ③ 详情
    if request.method == 'GET':
        return api_response(_task_payload(task))

    # ⑥ 删除或归档
    if request.method == 'DELETE':
        # ?archive=1 → 归档（列表默认不显示，但历史还在）；否则真删（步骤级联删）
        if _to_bool(request.GET.get('archive')):
            task.status = 'archived'
            task.save(update_fields=['status', 'updated_at'])
            return api_response({'archived': True, 'id': task.pk})
        task.delete()
        return api_response({'deleted': True, 'id': pk})

    # ⑤ 改任务（PATCH / POST）：只改传了的字段
    data = _json_body(request)
    fields = []

    if 'title' in data:
        title = _s(data.get('title'), MAX_TITLE)
        if not title:
            return api_response({'error': 'title 不能为空'}, 400)
        task.title = title
        fields.append('title')

    if 'description' in data:
        task.description = _s(data.get('description'), MAX_DESC)
        fields.append('description')

    if 'frequency_type' in data or 'quota_period' in data or 'quota_count' in data:
        freq_fields, err = _clean_frequency(data, current=task)
        if err:
            return api_response({'error': err}, 400)
        for k, v in freq_fields.items():
            setattr(task, k, v)
            fields.append(k)
        new_kind = _kind_for(task.frequency_type, _s(data.get('kind'), 10) or task.kind)
        if new_kind != task.kind:
            task.kind = new_kind
            fields.append('kind')

    if 'persist' in data:
        persist = _s(data.get('persist'), 12)
        if persist not in PERSIST_CHOICES:
            return api_response({'error': 'persist 只能是 streak / cumulative'}, 400)
        task.persist = persist
        fields.append('persist')

    if 'timeslot' in data:
        task.timeslot = _s(data.get('timeslot'), MAX_TIMESLOT)
        fields.append('timeslot')

    # #085：排到哪天（传空串 = 从时间轴上撤下来，回到"没排期"）
    if 'plan_date' in data:
        plan_date, err = _parse_plan_date(data.get('plan_date'))
        if err:
            return api_response({'error': err}, 400)
        task.plan_date = plan_date
        fields.append('plan_date')

    if 'target_count' in data:
        task.target_count = _to_int(data.get('target_count'))
        fields.append('target_count')

    if 'expected_at' in data:
        expected_at, err = _parse_dt(data.get('expected_at'))
        if err:
            return api_response({'error': err}, 400)
        task.expected_at = expected_at
        fields.append('expected_at')

    if 'status' in data:
        status = _s(data.get('status'), 10)
        if status not in STATUS_CHOICES:
            return api_response({'error': 'status 只能是 active / done / archived'}, 400)
        task.status = status
        fields.append('status')

    if not fields:
        return api_response({'error': '没有可改的字段'}, 400)

    task.save(update_fields=fields + ['updated_at'])
    task = _task_for_user(request.user, task.pk)
    return api_response(_task_payload(task))


# ===== ⑦ 日程（按月每天完成度）=====

@require_http_methods(['GET'])
@require_token
def task_calendar(request):
    """每天的口径（写清楚，避免以后各算各的）：

    - steps_done      : 这一天打勾的步数
    - task_count      : 这些步数涉及的任务数（当天"有活动"的任务）
    - tasks_completed : 其中【当天就做完了】的任务数（TaskDay.completed=True 且 date=当天）
    - rate            : tasks_completed / task_count（当天完成度）
    - created_count   : 这一天新建的任务数
    没有数据的日子也返回（补 0），前端画月历不用自己补洞。
    """
    user = request.user
    month = _s(request.GET.get('month'), 7) or timezone.localdate().strftime('%Y-%m')
    if not _MONTH_RE.match(month):
        return api_response({'error': 'month 格式要是 YYYY-MM'}, 400)

    year, mon = int(month[:4]), int(month[5:7])
    first = date(year, mon, 1)
    next_first = date(year + (mon // 12), (mon % 12) + 1, 1)   # 12 月 → 次年 1 月
    last = next_first - timedelta(days=1)

    # #087：日历改成读事件流水（TaskDay）——
    # 以前靠 step.is_done + done_at，本来就没有"哪天"的语义（今天取消勾就把昨天的记录一起抹了）。
    day_rows = TaskDay.objects.filter(user=user, date__gte=first, date__lte=last)
    per_day = {}
    task_ids_by_day = {}
    done_by_day = {}
    for d in day_rows:
        per_day[d.date] = per_day.get(d.date, 0) + (d.done_count or 0)
        task_ids_by_day.setdefault(d.date, set()).add(d.task_id)
        if d.completed:
            # #089：按【当天】计。以前用一个全局 completed_ids 集合，
            # 于是"昨天做完、今天只勾了一半"的任务会把昨天的完成算到今天头上
            # （今天 0 件做完，却报 tasks_completed=1、rate=0.5）。
            done_by_day[d.date] = done_by_day.get(d.date, 0) + 1

    created_rows = (UserTask.objects.filter(user=user, created_at__date__gte=first,
                                           created_at__date__lte=last)
                    .values_list('created_at', flat=True))
    created_by_day = {}
    for dt in created_rows:
        d = timezone.localtime(dt).date() if timezone.is_aware(dt) else dt.date()
        created_by_day[d] = created_by_day.get(d, 0) + 1

    days = []
    cursor = first
    while cursor <= last:
        ids = task_ids_by_day.get(cursor, set())
        completed = done_by_day.get(cursor, 0)
        total = len(ids)
        days.append({
            'date': cursor.isoformat(),
            'created_count': created_by_day.get(cursor, 0),
            'steps_done': per_day.get(cursor, 0),
            'task_count': total,
            'tasks_completed': completed,
            'rate': round(completed / total, 4) if total else 0.0,
        })
        cursor += timedelta(days=1)

    return api_response({
        'month': month,
        'from': first.isoformat(),
        'to': last.isoformat(),
        'days': days,
    })


# ===== ⑧ 从单个步骤建任务（模板原子化）=====

@csrf_exempt
@require_http_methods(['POST'])
@require_token
@transaction.atomic
def task_from_step(request):
    data = _json_body(request)
    user = request.user

    step_id = _to_int(data.get('quick_step_id') or data.get('step_id'))
    if not step_id:
        return api_response({'error': 'quick_step_id 必填'}, 400)
    quick_step = (QuickStep.objects.filter(pk=step_id)
                  .select_related('pattern').first())
    if quick_step is None or not quick_step.pattern.can_view(user):
        return api_response({'error': '步骤不存在'}, 404)
    # #089：允不允许"拆走这一步"，闸门必须和整份 fork 一致 ——
    # 否则作者关掉 allow_fork，用户点「拆出来做」照样把正文复制进自己的任务。
    if not quick_step.pattern.allow_fork and quick_step.pattern.author_id != user.pk:
        return api_response({'error': '作者不让改这份做法'}, 403)

    freq_fields, err = _clean_frequency(data)
    if err:
        return api_response({'error': err}, 400)

    persist = _s(data.get('persist'), 12) or 'cumulative'
    if persist not in PERSIST_CHOICES:
        return api_response({'error': 'persist 只能是 streak / cumulative'}, 400)

    expected_at, err = _parse_dt(data.get('expected_at'))
    if err:
        return api_response({'error': err}, 400)

    # #085：拆出来的小事也能直接排到某天
    # #089：不传就默认今天（和 task_create 同一口径，拆出来立刻能在"今天"看见）
    if 'plan_date' in data:
        plan_date, err = _parse_plan_date(data.get('plan_date'))
        if err:
            return api_response({'error': err}, 400)
    else:
        plan_date = local_today()

    task = UserTask.objects.create(
        user=user,
        # 标题默认沿用步骤标题；用户可改（"把这一步变成一件独立的小事"）
        title=_s(data.get('title'), MAX_TITLE) or _s(quick_step.title, MAX_TITLE) or '未命名任务',
        description=_s(data.get('description'), MAX_DESC),
        source_pattern=quick_step.pattern,
        kind=_kind_for(freq_fields['frequency_type']),
        persist=persist,
        target_count=_target_count_for(data, freq_fields),
        timeslot=_s(data.get('timeslot'), MAX_TIMESLOT),
        expected_at=expected_at,
        plan_date=plan_date,
        status='active',
        **freq_fields,
    )
    # 只拆这一条步骤（原子化）：order 归 0，独立成一件小事
    UserTaskStep.objects.create(
        task=task,
        order=quick_step.order if quick_step.order is not None else 0,
        title=_s(quick_step.title, MAX_TITLE),
        instruction=quick_step.instruction or '',
        explain=quick_step.explain or '',
        duration_seconds=quick_step.duration_seconds or 0,
        is_timed=bool(quick_step.is_timed),
        source_step=quick_step,
    )

    task = _task_for_user(user, task.pk)
    return api_response(serialize_task(task, include_steps=True), 201)
