import io
import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from functools import wraps

from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.db.models.functions import Greatest
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from patterns.views import FONT_REGULAR, FONT_BOLD, FONTS_DIR
from quick.models import (QuickPattern, QuickStep, QuickRating, QuickNote, QuickUsage, QuickFavorite,
                        QuickView)
from users.models import User
from .serializers import serialize_quick, author_display_name, user_display_name
# #071：头像校验直接复用网页资料页那套（#057⑤ 加的类型/大小/真图片三重校验）
from users.views import _clean_avatar
# #046 批量导入的校验/落库核心（管理端页面共用同一份逻辑，避免两边规则跑偏）
# #057⑥：三个创建入口（/quick/、/quick/import/、batch-import）的字段口径也统一从这里取
from quick.batch_import import (
    MAX_LONG_TEXT, MAX_MAX_ORDER, MAX_TITLE, clean_duration, clean_pattern_fields,
    import_templates, parse_templates,
)


def api_response(data, status=200):
    """统一响应格式：{'ok': bool, 'data': ...}"""
    return JsonResponse({'ok': status < 400, 'data': data}, status=status)


def _resolve_user(request):
    """从 Authorization: Token <token> 解析用户，无 token/无效/已停用则返回 None

    #057①：带 is_active=True —— 后台"封禁"只是把 is_active 置 False，
    以前 token 照样能用，封禁等于没封。
    """
    token = request.headers.get('Authorization', '').replace('Token ', '').strip()
    return User.objects.filter(api_token=token, is_active=True).first() if token else None


def require_token(view):
    """token 认证装饰器：校验失败返回 401"""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = _resolve_user(request)
        if not user:
            return JsonResponse({'ok': False, 'data': {'error': '未认证'}}, status=401)
        request.user = user
        return view(request, *args, **kwargs)
    return wrapper


def require_ugc(view):
    """UGC 写接口开关：settings.ENABLE_UGC=False 时统一返回 403「该功能暂未开放」。

    小程序侧已经没有创建/导入/编辑入口（xingdongmao/utils/config.js），但接口还开着，
    留一个能写内容的"后门"既不划算、也不好向审核解释，所以在服务端一并关掉。
    挂在 require_token 之后：未登录仍是 401（前端要按 401 清 token），登录后才拿到 403。
    ENABLE_UGC=True 时本装饰器完全不做事，原行为不变。
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'ENABLE_UGC', False):
            return api_response({'error': '该功能暂未开放'}, 403)
        return view(request, *args, **kwargs)
    return wrapper


def require_staff(view):
    """内部接口守卫：必须 is_staff（#046）。

    挂在 require_token 之后：没登录仍是 401（前端要按 401 清 token），
    登录但不是管理员才 403 —— 普通用户既拿不到入口也调不动接口。
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not getattr(request.user, 'is_staff', False):
            return api_response({'error': '仅内部使用'}, 403)
        return view(request, *args, **kwargs)
    return wrapper


def _s(value, limit=None):
    """#056：把任意 JSON 值安全地当字符串用。

    请求体字段传数字/对象/数组/None 时，原来 `.strip()` 会抛 AttributeError → 500。
    """
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value[:limit] if limit else value


def require_visible(view):
    """#056：把"这个 pk 对外可见吗（或你是作者吗）"收敛成一处装饰器。

    未上架/被下架的模板，对非作者一律当成不存在；执行/评分/笔记/收藏都挂它，
    避免以后再加端点又漏一个（#054 详情页就是这么漏的）。
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        qp = QuickPattern.objects.filter(pk=kwargs.get('pk')).first()
        if qp is None or not qp.can_view(getattr(request, 'user', None)):
            return api_response({'error': '模板不存在'}, 404)
        return view(request, *args, **kwargs)
    return wrapper


def _json_body(request):
    try:
        data = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    # #056：只接受 JSON 对象；以前数组/数字/字符串会一路传到 .get() → AttributeError → 500
    return data if isinstance(data, dict) else {}


def _to_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _page_params(request):
    try:
        page = int(request.GET.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get('page_size', 10))
    except (TypeError, ValueError):
        page_size = 10
    return max(page, 1), max(page_size, 1)


# 只删真正的 emoji/符号区块，绝不跨 CJK（修正 patterns/views.py wrap_text 里
# \u24C2-\U0001F251 区间误删全部汉字的历史 bug，隔离在本 app 内不动 patterns/）
_EMOJI_PAT = re.compile(
    r'[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\u2B00-\u2BFF'
    r'\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
    r'\u200d\uFE0F\u24C2\U0001F200-\U0001F251]'
)


def _wrap_text(draw, text, font, max_width):
    """按像素宽度换行，返回行列表；只过滤 true emoji，保留中文"""
    text = _EMOJI_PAT.sub('', text)
    lines = []
    current = ''
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines if lines else [text]


def _attach_favorite_flag(data_list, user):
    """批量标记 is_favorited，避免 N+1"""
    if not user:
        for d in data_list:
            d['is_favorited'] = False
        return data_list
    ids = [d['id'] for d in data_list]
    fav_ids = set(QuickFavorite.objects.filter(user=user, pattern_id__in=ids).values_list('pattern_id', flat=True))
    for d in data_list:
        d['is_favorited'] = d['id'] in fav_ids
    return data_list


# ===== 端点 1 & 8：/quick/ GET 列表 / POST 创建（共享路径，按方法分发） =====

@csrf_exempt
def quick_collection(request):
    if request.method == 'GET':
        return quick_list(request)
    if request.method == 'POST':
        return quick_create(request)
    return api_response({'error': '方法不允许'}, 405)


def quick_list(request):
    qs = QuickPattern.objects.filter(
        is_listed=True, is_reported=False
    ).select_related('author').prefetch_related('steps', 'favorites')

    q = request.GET.get('q', '').strip()
    # #072：category 提到外面 —— 搜索页点"标签行"里的分类时是 q + category 一起发，
    # 以前 category 只在无 q 的分支里读，等于点了没反应
    category = request.GET.get('category', '').strip()

    if q:
        # 模糊搜索：优先精确/包含匹配(icontains) + 模糊(pg_trgm 相关度)
        qs = qs.annotate(
            sim=Greatest(
                TrigramSimilarity('title', q),
                TrigramSimilarity('tagline', q),
                TrigramSimilarity('description', q),
            )
        ).filter(
            Q(sim__gt=0.15) | Q(title__icontains=q) | Q(tagline__icontains=q) | Q(description__icontains=q)
        )
        if category:
            qs = qs.filter(category=category)
        items = list(qs.order_by('-sim'))
        # 中文错别字兜底：pg_trgm 的 3 字 trigram 对无空格中文短词的错别字不敏感，
        # 主搜索无结果时按字符重叠率补一刀（数据量小，Python 侧算即可）
        if not items and any('\u4e00' <= ch <= '\u9fff' for ch in q):
            qset = set(q)
            extras = []
            pool = QuickPattern.objects.filter(is_listed=True, is_reported=False)
            if category:
                pool = pool.filter(category=category)
            for p in pool.select_related('author').prefetch_related('steps', 'favorites'):
                text = f'{p.title}{p.tagline}{p.description}'
                overlap = len(qset & set(text)) / len(qset)
                if overlap >= 0.5:
                    extras.append((overlap, p))
            extras.sort(key=lambda x: -x[0])
            items = [p for _, p in extras]
    else:
        if category:
            qs = qs.filter(category=category)
        items = list(qs)
        sort = request.GET.get('sort', 'hot')
        if sort == 'latest':
            items.sort(key=lambda p: p.created_at, reverse=True)
        else:
            # 热度 = usage_count × (avg_rating or 3) × 0.95^天数
            # #057⑤：date.today() 取的是服务器本地日期，容器/服务器时区不是 Asia/Shanghai 时
            # 会比"今天"差一天，热度衰减算错。统一用 Django 的项目时区。
            today = timezone.localdate()
            items.sort(key=lambda p: p.usage_count * (p.avg_rating or 3) * (0.95 ** (today - p.created_at.date()).days), reverse=True)

    page, page_size = _page_params(request)
    total = len(items)
    start = (page - 1) * page_size
    results = [serialize_quick(p) for p in items[start:start + page_size]]
    _attach_favorite_flag(results, _resolve_user(request))
    payload = {'results': results, 'total': total}
    if q:
        # #072③：搜索页的"标签行"。只在带 q 时多下发，首页/小程序原响应形状不变
        payload['tags'] = _search_tags(q, items)
    return api_response(payload)


def _search_tags(q, items, limit=6):
    """#072③ 搜索页标签行：命中的分类 + 结果里的关键词，点一下能继续收窄。

    · 有结果：分类按命中数排（最多 3 个）+ 结果标题/一句话里的高频 2-4 字词；
    · 没结果：退回"全站热门分类"当建议（spec ②：搜不到时给标签建议）。
    返回 [{kind: 'category'|'term', key, label, count}]，前端按 kind 决定点击行为
    （分类 = 加 category 过滤；词 = 换关键词重搜）。
    """
    labels = dict(QuickPattern.CATEGORY_CHOICES)
    label_set = set(labels.values())

    if not items:
        counter = Counter(QuickPattern.objects.filter(
            is_listed=True, is_reported=False).values_list('category', flat=True))
        return [{'kind': 'category', 'key': k, 'label': labels.get(k, k), 'count': n}
                for k, n in counter.most_common(limit) if k in labels]

    cat_counter = Counter(p.category for p in items)
    tags = [{'kind': 'category', 'key': k, 'label': labels.get(k, k), 'count': n}
            for k, n in cat_counter.most_common(3) if k in labels]

    word = Counter()
    for p in items[:40]:
        word.update(re.findall(r'[\u4e00-\u9fff]{2,4}', f'{p.title} {p.tagline}'))
    qset = set(q)
    words = [w for w, _ in word.most_common(30)]
    # 优先给"跟搜索词有共同字"的词，没有共同字时才退回高频词（避免给出完全无关的标签）
    for w in ([x for x in words if qset & set(x)] or words):
        if len(tags) >= limit:
            break
        if w in label_set or any(t['label'] == w for t in tags):
            continue
        tags.append({'kind': 'term', 'label': w, 'count': word[w]})
    return tags


@require_token
@require_ugc
@transaction.atomic
def quick_create(request):
    data = _json_body(request)
    # #057⑥：顶层字段口径统一走 quick.batch_import.clean_pattern_fields
    # （strict=False：App 里创建超长就截断，不让用户因为多打几个字保存失败）
    fields, err = clean_pattern_fields(data)
    if err:
        return api_response({'error': err}, 400)

    steps = data.get('steps') or []
    if not isinstance(steps, list):
        return api_response({'error': 'steps 必须是数组'}, 400)

    qp = QuickPattern.objects.create(
        author=request.user,
        allow_fork=bool(data.get('allow_fork', True)),
        status='draft',
        **fields,
    )

    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        step_title = _s(s.get('title'), MAX_TITLE)
        if not step_title:
            continue
        # #057②：is_timed 只由时长派生（别再单独读请求里的 is_timed，两处各写必然漂）
        duration = clean_duration(s.get('duration_seconds'))
        QuickStep.objects.create(
            pattern=qp,
            order=max(0, min(MAX_MAX_ORDER, _to_int(s.get('order'), i))),
            title=step_title,
            instruction=_s(s.get('instruction'), MAX_LONG_TEXT),
            explain=_s(s.get('explain'), MAX_LONG_TEXT),
            duration_seconds=duration,
            is_timed=duration > 0,
        )

    return api_response(serialize_quick(qp), 201)


# ===== 端点 2：详情（作者可看任意状态，非作者只看 published+verified） =====

@require_GET
def quick_detail(request, pk):
    qp = QuickPattern.objects.select_related('author').prefetch_related('steps', 'favorites').filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)

    user = _resolve_user(request)
    is_author = user is not None and user.pk == qp.author_id
    # #054：可见性统一走 model 的唯一判据（以前这里看旧 status，
    # 于是"已上架但 status 还是 draft"的模板列表能看见、详情却 404）
    if not qp.can_view(user):
        return api_response({'error': '模板不存在'}, 404)

    # #071 浏览记录：登录用户看【公开可见】的模板时记一条（草稿/被下架的不记，
    # 所以这个列表里永远不会出现"只有作者能看的东西"）。同一模板只留一行，重看刷新时间。
    if user is not None and qp.is_listed and not qp.is_reported:
        QuickView.objects.update_or_create(user=user, pattern=qp)

    data = serialize_quick(qp)
    data['is_author'] = is_author
    data['is_favorited'] = user is not None and QuickFavorite.objects.filter(user=user, pattern=qp).exists()
    # 前端要显示"你已评 X 星"，并且评过之后不允许重复评分（/rate/ 也会挡，这里先给状态）
    my_rating = 0
    if user is not None:
        my_rating = QuickRating.objects.filter(user=user, pattern=qp).values_list('stars', flat=True).first() or 0
    data['my_rating'] = my_rating
    return api_response(data)


# ===== 端点 3：执行（usage_count + 1，记 QuickUsage） =====

@csrf_exempt
@require_token
@require_visible
def quick_execute(request, pk):
    qp = QuickPattern.objects.filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)

    # #057②：F() 原子自增 —— 以前"读出来 +1 再写回"，两个人同时点执行会丢一次计数
    QuickPattern.objects.filter(pk=qp.pk).update(usage_count=F('usage_count') + 1)
    QuickUsage.objects.create(user=request.user, pattern=qp)
    qp.refresh_from_db(fields=['usage_count'])
    qp.check_verify()
    return api_response({'usage_count': qp.usage_count})


# ===== 端点 4：评分（校验执行过 + 防重复 + 更新均分） =====

@csrf_exempt
@require_token
@require_visible
def quick_rate(request, pk):
    qp = QuickPattern.objects.filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)

    if not QuickUsage.objects.filter(user=request.user, pattern=qp).exists():
        return api_response({'error': '请先完成一次引导再评分'}, 403)

    data = _json_body(request)
    stars = _to_int(data.get('stars'), 0)
    if stars < 1 or stars > 5:
        return api_response({'error': 'stars 必须是 1-5 的整数'}, 400)

    # #057③：别在"先 exists 再 create"之间留缝 —— 双击提交会两条评分一起落库，
    # 均分被算两次。改成靠唯一约束兜底：抢不到的那次拿到 IntegrityError，按"已评过分"回。
    # 必须用内层 atomic（savepoint）包住：捕获 IntegrityError 后当前事务仍处于"已损坏"状态，
    # 没有 savepoint 的话后续查询会报 TransactionManagementError（外层有 atomic 时就会中招）。
    try:
        with transaction.atomic():
            QuickRating.objects.create(user=request.user, pattern=qp, stars=stars)
    except IntegrityError:
        return api_response({'error': '已评过分'}, 400)
    qp.avg_stars()
    qp.check_verify()
    return api_response({'avg_rating': qp.avg_rating, 'rating_count': qp.rating_count})


# ===== 端点 5 & 6：笔记 =====

@csrf_exempt
@require_token
@require_visible
def quick_note(request, pk):
    qp = QuickPattern.objects.filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)

    data = _json_body(request)
    content = _s(data.get('content'), 2000)
    if not content:
        return api_response({'error': 'content 不能为空'}, 400)

    note = QuickNote.objects.create(user=request.user, pattern=qp, content=content)
    return api_response({'id': note.pk})


@require_GET
@require_token
def quick_notes(request, pk):
    notes = QuickNote.objects.filter(user=request.user, pattern_id=pk)
    return api_response([
        {'id': n.pk, 'content': n.content, 'created_at': n.created_at.isoformat()}
        for n in notes
    ])


# ===== 端点 7：我的（author=me，标注 is_fork） =====

@require_GET
@require_token
def quick_me(request):
    qs = QuickPattern.objects.filter(author=request.user).select_related('author').prefetch_related('steps', 'favorites')
    data = []
    for qp in qs:
        d = serialize_quick(qp)
        d['is_fork'] = qp.fork_from_id is not None
        data.append(d)
    _attach_favorite_flag(data, request.user)
    return api_response(data)


# ===== 端点 9：Fork（复制字段 + steps，计数清零，事务包裹） =====
# Fork 会以当前用户身份建一份 status=draft 的模板副本，本质也是 UGC 创建，所以同样挂 UGC 守卫

@csrf_exempt
@require_token
@require_ugc
@transaction.atomic
def quick_fork(request, pk):
    qp = QuickPattern.objects.prefetch_related('steps').filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)
    # #056：未上架/被下架的模板不许被他人 fork（否则草稿正文能被整份复制走）
    if not qp.can_view(request.user):
        return api_response({'error': '模板不存在'}, 404)
    if not qp.allow_fork:
        return api_response({'error': '该模板不允许 Fork'}, 400)

    new_qp = QuickPattern.objects.create(
        title=qp.title,
        tagline=qp.tagline,
        description=qp.description,
        category=qp.category,
        icon=qp.icon,
        icon_key=qp.icon_key,   # #073：Fork 时把矢量图标一起带走
        author=request.user,
        is_official=False,
        allow_fork=qp.allow_fork,
        usage_count=0,
        avg_rating=0,
        rating_count=0,
        status='draft',
        is_reported=False,
        fork_from=qp,
    )
    for s in qp.steps.all():
        QuickStep.objects.create(
            pattern=new_qp,
            order=s.order,
            title=s.title,
            instruction=s.instruction,
            explain=s.explain,
            duration_seconds=s.duration_seconds,
            is_timed=s.is_timed,
        )

    return api_response(serialize_quick(new_qp), 201)


# ===== #072⑦：多选合并（把几个公开模板的步骤拼成一个新草稿，前端再进编辑页）=====

MAX_MERGE = 5


def _merge_title(titles, limit=100):
    """合并后的标题：'A＋B＋C'，超长按整段截断（title 上限 100，别写超）。"""
    joined = '＋'.join(titles)
    if len(joined) <= limit:
        return joined
    out = ''
    for i, t in enumerate(titles):
        piece = ('＋' if i else '') + t
        if len(out) + len(piece) > limit - 1:
            break
        out += piece
    return (out or titles[0][:limit - 1]) + '…'


@csrf_exempt
@require_token
@require_ugc
@transaction.atomic
def quick_merge(request):
    """#072⑦ 多选合并：把 2-5 个【公开】模板的步骤按选择顺序拼成一份新草稿。

    只建草稿、不自动上架：合并出来的东西是"素材"，要用户自己在编辑页改完再发。
    步骤原样搬（不改标题/时长），来源写在 tagline/description 里，方便在编辑页认出来。
    """
    data = _json_body(request)
    ids = data.get('ids')
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return api_response({'error': 'ids 必须是整数数组'}, 400)

    # 去重但保留选择顺序（同一个模板选两次没有意义）
    ordered = []
    for i in ids:
        if i not in ordered:
            ordered.append(i)
    if len(ordered) < 2:
        return api_response({'error': '至少选 2 个模板才能合并'}, 400)
    if len(ordered) > MAX_MERGE:
        return api_response({'error': f'一次最多合并 {MAX_MERGE} 个模板'}, 400)

    # 只允许合并"当前公开"的：草稿/被下架的不许被整份搬走（同 #056 fork 的口径）
    found = {p.pk: p for p in QuickPattern.objects.filter(
        pk__in=ordered, is_listed=True, is_reported=False).prefetch_related('steps')}
    if len(found) != len(ordered):
        return api_response({'error': '有模板不存在或已下架，刷新后再试'}, 404)
    sources = [found[i] for i in ordered]

    titles = [p.title for p in sources]
    new_qp = QuickPattern.objects.create(
        title=_merge_title(titles),
        tagline=(f'合并自 {len(titles)} 个模板：' + '、'.join(titles))[:200],
        description='\n'.join('· ' + t for t in titles),
        category=sources[0].category,
        icon=sources[0].icon,
        icon_key=sources[0].icon_key,   # #073：合并出来的草稿沿用第一个来源的图标
        author=request.user,
        is_official=False,
        allow_fork=True,
        status='draft',
        is_listed=False,
        fork_from=sources[0],
    )
    order = 0
    for p in sources:
        for s in p.steps.all():
            QuickStep.objects.create(
                pattern=new_qp,
                order=order,
                title=s.title,
                instruction=s.instruction,
                explain=s.explain,
                duration_seconds=s.duration_seconds,
                is_timed=s.is_timed,
            )
            order += 1

    return api_response(serialize_quick(new_qp), 201)


# ===== 端点 10：热门标签（朴素分词统计前 20） =====

@require_GET
def quick_tags(request):
    qs = QuickPattern.objects.filter(is_listed=True, is_reported=False)
    counter = Counter()
    for qp in qs.iterator():
        text = f'{qp.title} {qp.tagline} {qp.description}'
        # 朴素实现：提取 2-4 个连续汉字的片段作为词
        counter.update(re.findall(r'[\u4e00-\u9fff]{2,4}', text))
    return api_response([w for w, _ in counter.most_common(20)])


# ===== #A 收藏 / 取消收藏（幂等） =====

@csrf_exempt
@require_token
@require_visible
def quick_favorite(request, pk):
    qp = QuickPattern.objects.filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)
    QuickFavorite.objects.get_or_create(user=request.user, pattern=qp)
    return api_response({'favorited': True})


@csrf_exempt
@require_token
def quick_unfavorite(request, pk):
    qp = QuickPattern.objects.filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)
    QuickFavorite.objects.filter(user=request.user, pattern=qp).delete()
    return api_response({'favorited': False})


# ===== #B 我的收藏列表 =====

@require_GET
@require_token
def quick_my_favorites(request):
    favs = QuickFavorite.objects.filter(user=request.user).select_related(
        'pattern__author'
    ).prefetch_related('pattern__steps', 'pattern__favorites')
    data = [serialize_quick(f.pattern) for f in favs]
    for d in data:
        d['is_favorited'] = True
    return api_response(data)


# ===== #C 快速导入（D5 三段式：动作 | 时长 | 画面文字） =====

# 时长写法：60秒 / 60 / 60s / 1分钟 / 1.5min。
# 看不懂的必须报错，不能像以前那样静默当 0——别的端直接调接口会踩坑。
_DUR_SECONDS_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*(?:秒|s)?$', re.IGNORECASE)
_DUR_MINUTES_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*(?:分钟|分|min|m)$', re.IGNORECASE)


def _parse_duration(text):
    """把导入行的时长换算成秒；返回 None 表示看不懂（调用方负责进 skipped_lines）"""
    t = (text or '').strip()
    if not t:
        return 0
    m = _DUR_SECONDS_RE.match(t)
    if m:
        return int(round(float(m.group(1))))
    m = _DUR_MINUTES_RE.match(t)
    if m:
        return int(round(float(m.group(1)) * 60))
    return None


@csrf_exempt
@require_token
@require_ugc
@transaction.atomic
def quick_import(request):
    data = _json_body(request)
    # #057⑥：与 /quick/ 同一份字段口径
    fields, err = clean_pattern_fields(data)
    if err:
        return api_response({'error': err}, 400)

    qp = QuickPattern.objects.create(
        author=request.user,
        status='draft',
        **fields,
    )

    lines = data.get('lines') or []
    if not isinstance(lines, list):
        lines = []

    skipped = []
    for idx, line in enumerate(lines, start=1):
        if not isinstance(line, str) or '|' not in line:
            skipped.append({'line': idx, 'reason': '缺少|分隔符'})
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 2:
            skipped.append({'line': idx, 'reason': '缺少|分隔符'})
            continue
        action = parts[0]
        instruction = parts[2] if len(parts) >= 3 else ''
        # 第 4 段是「为什么」（#032 起 AI 提示词生成的格式就是 4 段）。
        # 多于 4 段（用户/AI 在文字里打了竖线）就并进 explain，宁可多留也不要丢内容。
        explain = ' | '.join(parts[3:]).strip() if len(parts) >= 4 else ''
        if not action:
            skipped.append({'line': idx, 'reason': '动作为空'})
            continue
        duration = _parse_duration(parts[1])
        if duration is None:
            skipped.append({'line': idx, 'reason': '时长看不懂，请用秒或 X 分钟'})
            continue
        # 时长的上限/取整口径统一走 clean_duration（#057⑥）
        duration = clean_duration(duration)
        # #057⑦：单行坏数据用 savepoint 隔离 —— 以前一行炸了整批一起回滚，
        # 用户看到"全部没导进去"，也拿不到是哪一行。
        try:
            with transaction.atomic():
                QuickStep.objects.create(
                    pattern=qp,
                    order=idx,
                    title=action[:MAX_TITLE],
                    instruction=instruction[:MAX_LONG_TEXT],
                    explain=explain[:MAX_LONG_TEXT],
                    duration_seconds=duration,
                    is_timed=duration > 0,
                )
        except Exception as exc:
            skipped.append({'line': idx, 'reason': f'写入失败：{exc}'})
            continue

    payload = {'pattern': serialize_quick(qp)}
    if skipped:
        payload['skipped_lines'] = skipped
    return api_response(payload, 201)


# ===== #046 多模板批量导入（仅内部 staff）=====
# 输入 {"templates": [...]}；逐条校验、一律建草稿、失败只跳过该条。
# 后端结构：POST /api/v1/quick/batch-import/  → {ok, data:{created, skipped, errors, total}}
# 校验/落库细节都在 quick/batch_import.py（管理端页面 /admin/quick/batch-import/ 共用同一份）

@csrf_exempt
@require_token
@require_staff
def quick_batch_import(request):
    templates = None
    try:
        templates = parse_templates(_json_body(request))
    except ValueError as exc:
        return api_response({'error': str(exc)}, 400)

    result = import_templates(templates, author=request.user, is_official=True)
    result['total'] = len(templates)
    return api_response(result, 201 if result['created'] else 200)


# ===== #D 发布（draft → published；非作者 403；已发布幂等） =====

@csrf_exempt
@require_token
@require_ugc
def quick_publish(request, pk):
    qp = QuickPattern.objects.filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)
    if qp.author_id != request.user.pk:
        return api_response({'error': '无权限'}, 403)
    # #056：被管理员处置(is_reported)的模板不允许作者自行重新上架。
    # 必须放在 is_listed 早返回之前：否则"仍在架但已被举报"的模板会走到早返回，
    # 回一个 published 的假状态，作者以为还活着、管理处置等于没生效。
    if qp.is_reported:
        return api_response({'error': '该模板已被下架，不能自行重新上架'}, 403)
    if qp.is_listed:
        return api_response({'status': qp.status})
    # 0 步模板发出去没意义（前端也会拦），这里兜底
    if not qp.steps.exists():
        return api_response({'error': '至少需要一个步骤'}, 400)
    qp.is_listed = True
    qp.sync_legacy_status()
    qp.save(update_fields=['is_listed', 'status'])
    return api_response({'status': qp.status})


# ===== #E 编辑（PUT，全量替换 steps；verified 拒绝编辑） =====

@csrf_exempt
@require_token
@require_ugc
@require_http_methods(['PUT'])
@transaction.atomic
def quick_edit(request, pk):
    qp = QuickPattern.objects.prefetch_related('steps').filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)
    if qp.author_id != request.user.pk:
        return api_response({'error': '无权限'}, 403)
    if qp.status == 'verified':
        return api_response({'error': '推荐模板不可直接修改，请创建新版本'}, 400)

    data = _json_body(request)
    # #057⑥：编辑也用同一份字段口径。category 不传时保持原值（编辑表单不一定会带分类）
    raw = dict(data)
    if not raw.get('category'):
        raw['category'] = qp.category
    fields, err = clean_pattern_fields(raw)
    if err:
        return api_response({'error': err}, 400)
    title = fields['title']
    category = fields['category']

    # 已发布的模板不能编辑成 0 步，否则列表里会留下"已发布但没有步骤"的脏数据；草稿允许 0 步（还在写）。
    # 必须在 qp.save() 之前判断：视图是 @transaction.atomic，但返回 400 并不会回滚已写入的字段。
    steps = data.get('steps')
    if isinstance(steps, list) and qp.status in ('published', 'verified'):
        kept = [s for s in steps if isinstance(s, dict) and _s(s.get('title'), MAX_TITLE)]
        if not kept:
            return api_response({'error': '至少需要一个步骤'}, 400)

    qp.title = title
    qp.tagline = fields['tagline']
    qp.description = fields['description']
    qp.category = category
    # icon 没传就保留原值（编辑表单不一定会带图标）
    icon = _s(data.get('icon'), 5)
    qp.icon = icon or qp.icon
    # #073：矢量图标 slug 同样"没传就保留" —— 老客户端不带 icon_key，
    # 不能因为它不带就把用户已经选好的图标洗掉
    if 'icon_key' in data:
        qp.icon_key = fields['icon_key']
    qp.save()

    if isinstance(steps, list):
        qp.steps.all().delete()
        for i, s in enumerate(steps):
            if not isinstance(s, dict):
                continue
            step_title = _s(s.get('title'), MAX_TITLE)
            if not step_title:
                continue
            # #057②：is_timed 由时长派生，不再读请求里的 is_timed
            duration = clean_duration(s.get('duration_seconds'))
            QuickStep.objects.create(
                pattern=qp,
                order=max(0, min(MAX_MAX_ORDER, _to_int(s.get('order'), i))),
                title=step_title,
                instruction=_s(s.get('instruction'), MAX_LONG_TEXT),
                explain=_s(s.get('explain'), MAX_LONG_TEXT),
                duration_seconds=duration,
                is_timed=duration > 0,
            )

    return api_response(serialize_quick(qp))


# ===== #F 删除（DELETE，级联删除关联） =====

@csrf_exempt
@require_token
@require_ugc
@require_http_methods(['DELETE'])
def quick_delete(request, pk):
    qp = QuickPattern.objects.filter(pk=pk).first()
    if not qp:
        return api_response({'error': '模板不存在'}, 404)
    if qp.author_id != request.user.pk:
        return api_response({'error': '无权限'}, 403)
    qp.delete()
    return api_response({'deleted': True})


# ===== #066：分享图（暖棕金主题，Pillow 重画）=====
# 为什么不用 HTML/CSS+无头 Chromium：生产是 gunicorn+nginx，机器上没有浏览器，
# 为一张 1080×1440 的海报引入 Chromium = 新依赖 + 内存/沙箱风险 + 每次 1~2s；
# Pillow 走本地字体、单次几十毫秒、且这套版式全是圆角矩形+文字，PIL 完全够用。
SHARE_W, SHARE_H = 1080, 1440
SHARE_BG_TOP = (14, 14, 16)        # 深色底（非纯黑，跟网页端 --bg 一致）
SHARE_BG_BOTTOM = (23, 20, 17)     # 底部偏暖，避免整张死黑
SHARE_CARD = (23, 23, 26)          # 卡片面 --surface
SHARE_BORDER = (42, 39, 35)        # 暖一点的分隔线
SHARE_TEXT = (242, 240, 237)       # 暖白 --text
SHARE_TEXT2 = (184, 181, 176)
SHARE_MUTED = (138, 135, 131)
SHARE_ACCENT = (184, 149, 106)     # 暖棕金 --accent
SHARE_ACCENT_ON = (20, 17, 12)     # 金色块上的字（深棕）
SHARE_TAGLINE = (207, 191, 164)
STEP_TITLE_GAP = 28               # #068：步骤标题与右侧时长胶囊之间固定留出的呼吸位(px)    # tagline：金色往暖白靠一档


def _blend(c1, c2, a):
    """把 c2 按 a 混到 c1 上（用来算"金色 16% 铺在卡片上"这类扁平色，免去 alpha 合成）。"""
    return tuple(int(round(c1[i] * (1 - a) + c2[i] * a)) for i in range(3))


SHARE_ACCENT_SOFT = _blend(SHARE_CARD, SHARE_ACCENT, 0.16)
SHARE_GLOW = _blend(SHARE_BG_BOTTOM, SHARE_ACCENT, 0.10)

_SHARE_FONT_CACHE = {}
_SHARE_FONT_WARNED = False
_SHARE_FONT_CANDIDATES = {
    'bold': ['NotoSansSC-Bold.otf', 'NotoSansSC-Black.otf', 'NotoSansSC-Medium.otf'],
    'medium': ['NotoSansSC-Medium.otf', 'NotoSansSC-Bold.otf', 'NotoSansSC-Regular.otf'],
    'regular': ['NotoSansSC-Regular.otf', 'NotoSansSC-DemiLight.otf', 'NotoSansSC-Medium.otf'],
}
_SHARE_SYSTEM_FONTS = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    'C:/Windows/Fonts/msyhbd.ttc',
    'C:/Windows/Fonts/msyh.ttc',
]


def _share_font(weight, size):
    """#066④ 字体解析链：项目自带 Noto Sans SC → 系统 CJK → Pillow 内置。

    任何一环失败都不抛异常（最后一个兜底），只在第一次降级时记一条 warning，
    保证"缺字体也不会让分享图接口 500"。
    """
    global _SHARE_FONT_WARNED
    key = (weight, size)
    if key in _SHARE_FONT_CACHE:
        return _SHARE_FONT_CACHE[key]
    paths = [os.path.join(FONTS_DIR, n)
             for n in _SHARE_FONT_CANDIDATES.get(weight, _SHARE_FONT_CANDIDATES['regular'])]
    paths += _SHARE_SYSTEM_FONTS
    font = None
    for p in paths:
        try:
            if os.path.exists(p):
                font = ImageFont.truetype(p, size)
                break
        except Exception:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size=size)
        except Exception:
            font = ImageFont.load_default()
        if not _SHARE_FONT_WARNED:
            _SHARE_FONT_WARNED = True
            logging.getLogger(__name__).warning(
                '分享图：没找到任何可用字体，已退回 Pillow 内置字体（中文可能显示为方块，但不影响生成）')
    _SHARE_FONT_CACHE[key] = font
    return font


def _text_w(draw, text, font):
    """水平排版一律用【推进宽度 textlength】。

    #068：以前用 textbbox 的墨迹宽度 —— 墨迹比推进窄，而 draw.text 是按推进逐字排的，
    于是"按墨迹刚好放下"的文字画出来会往右多探几个像素（省略号 … 的墨迹远窄于它的推进宽，
    这个差最明显）→ 预留的间距被悄悄吃掉，标题就贴到右边的时长胶囊上了（实测只剩 2~11px）。
    """
    try:
        return draw.textlength(text, font=font)
    except Exception:                      # 极老版本 Pillow 没有 textlength
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]


def _fit_text(draw, text, font, max_w):
    """单行用：超宽就截断加省略号（步骤标题这种只给一行的地方）"""
    if _text_w(draw, text, font) <= max_w:
        return text
    out = text
    while out and _text_w(draw, out + '…', font) > max_w:
        out = out[:-1]
    return (out + '…') if out else ''


def _draw_clipped(img, x, y, text, font, fill, max_w):
    """#068：把单行文字画进一个 max_w 宽的透明层再贴回去 —— 超出的部分被层裁掉。

    这是"永不重叠"的硬保证：不依赖字体度量算得准不准，换字体/缺字体回退（内置位图字体）
    也绝不会越界撞到右边的胶囊。先用 _fit_text 截断只是省得画多余的字。
    """
    draw = ImageDraw.Draw(img)
    text = _fit_text(draw, text, font, max_w)
    if not text:
        return
    layer = Image.new('RGBA', (max(1, int(max_w)), max(2, int(font.size * 2))), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((0, 0), text, font=font, fill=fill)
    img.paste(layer, (int(x), int(y)), layer)


def _pill(draw, x, y, text, font, fg, bg, pad_x=22, h=44):
    """圆角胶囊（分类 / 时长 / 官方标签都用它），返回宽度。文字按 bbox 真正垂直居中。"""
    w = _text_w(draw, text, font) + pad_x * 2
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg)
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((x + pad_x, y + (h - (box[3] - box[1])) / 2 - box[1]), text, font=font, fill=fg)
    return w


def _vertical_gradient(size, top, bottom):
    w, h = size
    strip = Image.new('RGB', (1, h))
    for y in range(h):
        strip.putpixel((0, y), _blend(top, bottom, y / max(1, h - 1)))
    return strip.resize((w, h))


def _render_share_poster(qp, show_author=True):
    """把模板画成一张 1080×1440 的分享图，返回 PNG bytes。

    版式（自上而下）：品牌行 → 分隔线 → 「执行引导」眉标 → 标题 → tagline →
    评分/使用次数 → 步骤列表（最多 6 步 + 还有 N 步）→ 底部作者/站名 + 金色 CTA。
    配色只用暖棕金 + 深灰 + 暖白，全部取自网页端那套变量。
    """
    img = _vertical_gradient((SHARE_W, SHARE_H), SHARE_BG_TOP, SHARE_BG_BOTTOM)
    # 标题后面一团很淡的暖金光晕：低饱和、只在中间偏上，避免整张"发光"
    glow = Image.new('L', (SHARE_W, SHARE_H), 0)
    ImageDraw.Draw(glow).ellipse([SHARE_W // 2 - 470, 60, SHARE_W // 2 + 470, 880], fill=44)
    img.paste(Image.new('RGB', (SHARE_W, SHARE_H), SHARE_GLOW), (0, 0), glow.filter(ImageFilter.GaussianBlur(150)))

    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([56, 56, SHARE_W - 56, SHARE_H - 56],
                           radius=32, fill=SHARE_CARD, outline=SHARE_BORDER, width=2)
    L, R = 120, SHARE_W - 120

    # ---- 品牌行：金色方块里的「锚」+ 站名 + 副标；右上角分类胶囊 ----
    draw.rounded_rectangle([L, 116, L + 56, 172], radius=16, fill=SHARE_ACCENT)
    f_mark = _share_font('bold', 32)
    draw.text((L + 28 - _text_w(draw, '锚', f_mark) / 2, 130), '锚', font=f_mark, fill=SHARE_ACCENT_ON)
    draw.text((L + 76, 116), '行动锚', font=_share_font('bold', 34), fill=SHARE_TEXT)
    draw.text((L + 76, 158), '现在就能做的一件小事', font=_share_font('regular', 24), fill=SHARE_MUTED)
    f_cat = _share_font('medium', 24)
    cat = qp.get_category_display()
    _pill(draw, R - (_text_w(draw, cat, f_cat) + 44), 124, cat, f_cat, SHARE_ACCENT, SHARE_ACCENT_SOFT)

    draw.line([L, 212, R, 212], fill=SHARE_BORDER, width=1)

    # ---- 眉标 + 标题 + tagline ----
    y = 250
    draw.text((L, y), '执行引导', font=_share_font('medium', 24), fill=SHARE_ACCENT)
    y += 48
    f_title = _share_font('bold', 62)
    for ln in _wrap_text(draw, qp.title, f_title, R - L)[:2]:
        draw.text((L, y), ln, font=f_title, fill=SHARE_TEXT)
        y += 82
    if qp.tagline:
        y += 8
        f_tag = _share_font('medium', 34)
        for ln in _wrap_text(draw, qp.tagline[:90], f_tag, R - L)[:2]:
            draw.text((L, y), ln, font=f_tag, fill=SHARE_TAGLINE)
            y += 50

    # ---- 评分（星用字形画，金色） / 使用次数 ----
    y += 22
    f_meta = _share_font('regular', 26)
    x = L
    if qp.rating_count:
        f_star = _share_font('regular', 30)
        stars = max(0, min(5, int(round(qp.avg_rating or 0))))
        draw.text((x, y - 6), '★' * stars + '☆' * (5 - stars), font=f_star, fill=SHARE_ACCENT)
        x += _text_w(draw, '★' * 5, f_star) + 16
        rating_text = f'{qp.avg_rating:.1f}（{qp.rating_count} 人评）'
    else:
        rating_text = '暂无评分'
    draw.text((x, y), rating_text, font=f_meta, fill=SHARE_TEXT2)
    x += _text_w(draw, rating_text, f_meta) + 18
    draw.text((x, y), '·', font=f_meta, fill=SHARE_MUTED)
    draw.text((x + 24, y), f'{qp.usage_count} 人用过', font=f_meta, fill=SHARE_TEXT2)
    y += 64

    # ---- 步骤：金色序号圆 + 标题 + 右侧时长胶囊 ----
    all_steps = list(qp.steps.all())
    draw.text((L, y), '步骤', font=_share_font('medium', 24), fill=SHARE_MUTED)
    f_cnt = _share_font('regular', 24)
    cnt = f'共 {len(all_steps)} 步' if all_steps else '还没有步骤'
    draw.text((R - _text_w(draw, cnt, f_cnt), y), cnt, font=f_cnt, fill=SHARE_MUTED)
    y += 54
    max_rows = 6
    f_idx = _share_font('bold', 26)
    f_step = _share_font('medium', 34)
    f_dur = _share_font('regular', 24)
    # #066：步骤少的时候底部会空一大片。这里按"可用高度"把行距拉开（84~130px），
    # 多了就压回 84；然后把整块在可用区域里垂直居中，让 3 步和 6 步都是一张均匀的海报。
    shown_rows = min(len(all_steps), max_rows)
    # #068：如果后面还要画「… 还有 N 步」那一行，先把它的高度从可用区里扣掉，
    # 否则 16 步这种会把行距撑满、那一行就贴到底部分隔线/作者行上了（极限样张里实测到过）。
    extra_line = 64 if len(all_steps) > max_rows else 0
    area_top, area_bottom = y - 6, 1188 - extra_line
    row_gap = 84
    if shown_rows:
        row_gap = max(84, min(130, (area_bottom - area_top) // shown_rows))
        used = row_gap * shown_rows
        if used < (area_bottom - area_top):
            y += int((area_bottom - area_top - used) / 2)
    for i, s in enumerate(all_steps[:max_rows], 1):
        draw.rounded_rectangle([L, y - 4, L + 52, y + 48], radius=26, fill=SHARE_ACCENT_SOFT)
        draw.text((L + 26 - _text_w(draw, str(i), f_idx) / 2, y + 8), str(i), font=f_idx, fill=SHARE_ACCENT)
        dur = f'{s.duration_seconds}秒' if s.duration_seconds else '手动'
        dw = _text_w(draw, dur, f_dur) + 44
        pill_left = R - dw
        _pill(draw, pill_left, y, dur, f_dur, SHARE_ACCENT, SHARE_ACCENT_SOFT)
        # #068：标题可用宽 = (整行右边界 - 胶囊宽) - 标题起点 - 间距；
        # 先按推进宽截断加省略号，再用 _draw_clipped 裁一层 → 三个元素（序号圆/标题/胶囊）永不打
        _draw_clipped(img, L + 76, y + 2, s.title, f_step, SHARE_TEXT,
                      pill_left - (L + 76) - STEP_TITLE_GAP)
        y += row_gap
    if len(all_steps) > max_rows:
        draw.text((L + 76, y), f'… 还有 {len(all_steps) - max_rows} 步',
                  font=f_step, fill=SHARE_MUTED)

    # ---- 底部：作者 / 站名 / 金色 CTA ----
    draw.line([L, 1216, R, 1216], fill=SHARE_BORDER, width=1)
    # #069：作者行只给【一个名字】，不再画「官方」胶囊，也不再出现纯数字邮箱前缀这种机器号
    f_author = _share_font('regular', 26)
    draw.text((L, 1246), author_display_name(qp, official=not show_author), font=f_author, fill=SHARE_TEXT2)
    f_site = _share_font('regular', 24)
    site = 'xingdongmao.com'
    draw.text((R - _text_w(draw, site, f_site), 1250), site, font=f_site, fill=SHARE_MUTED)
    f_cta = _share_font('medium', 28)
    cta = '来行动锚，找到你的节奏'
    draw.text(((SHARE_W - _text_w(draw, cta, f_cta)) / 2, 1322), cta, font=f_cta, fill=SHARE_ACCENT)

    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


# ===== #G 分享图片（GET，匿名可，返回 PNG） =====

@require_GET
def quick_share_card(request, pk):
    qp = QuickPattern.objects.select_related('author').prefetch_related('steps').filter(pk=pk).first()
    if not qp:
        return HttpResponse('模板不存在', status=404, content_type='text/plain')

    user = _resolve_user(request)
    # #056：统一可见性判据（can_view 内已含"作者本人始终可见"，不用再单独判 is_author）
    if not qp.can_view(user):
        return HttpResponse('模板不存在', status=404, content_type='text/plain')

    # 作者名默认画「官方」，只有网页版显式带 ?author=1 才画真实名（#029 的约定，保持不变）
    png = _render_share_poster(qp, show_author=request.GET.get('author') == '1')
    return HttpResponse(png, content_type='image/png')


# ===== 搜索推荐（D8） =====

@require_GET
def quick_suggest(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return api_response([])

    qs = QuickPattern.objects.filter(is_listed=True, is_reported=False)
    titles = list(qs.filter(Q(title__icontains=q) | Q(tagline__icontains=q)).values_list('title', flat=True))
    cat_names = [label for key, label in QuickPattern.CATEGORY_CHOICES if q in label]

    result = []
    seen = set()
    for t in titles + cat_names:
        if t and t not in seen:
            seen.add(t)
            result.append(t)
        if len(result) >= 8:
            break
    return api_response(result)


# ===== 微信小程序登录 =====


def _ensure_api_token(user):
    """历史用户可能没有 api_token（自动生成是后加的），登录时补一个，避免返回空 token"""
    if not user.api_token:
        user.save()
    return user.api_token


WX_SESSION_URL = 'https://api.weixin.qq.com/sns/jscode2session'


def _wx_placeholder_email(openid):
    """微信不给邮箱，但 User.email 是必填唯一字段：用 openid 派生一个稳定占位邮箱"""
    return f'wx_{openid}@wx.local'


@csrf_exempt
@require_http_methods(['POST'])
def wx_login(request):
    """小程序静默登录：code → openid → 用户 → api_token"""
    data = _json_body(request)
    code = _s(data.get('code'), 64)
    if not code:
        return api_response({'error': 'code 不能为空'}, 400)

    if not settings.WX_APPID or not settings.WX_APPSECRET:
        # 说清楚缺哪一项，否则前端只看到"登录失败"，没法排查
        return api_response({'error': '服务端未配置 WX_APPID / WX_APPSECRET（环境变量或 .env）'}, 503)

    query = urllib.parse.urlencode({
        'appid': settings.WX_APPID,
        'secret': settings.WX_APPSECRET,
        'js_code': code,
        'grant_type': 'authorization_code',
    })
    try:
        with urllib.request.urlopen(WX_SESSION_URL + '?' + query, timeout=5) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except Exception as exc:  # 网络/超时/非法 JSON 都把原始异常带出去，不吞
        return api_response({'error': f'调用微信 jscode2session 失败：{exc}'}, 502)

    # 微信用 errcode 表示失败（0 或缺省才是成功），原样透出
    errcode = payload.get('errcode') or 0
    if errcode:
        errmsg = payload.get('errmsg', '')
        return api_response({'error': f'微信返回错误 {errcode}: {errmsg}', 'errcode': errcode, 'errmsg': errmsg}, 400)

    openid = payload.get('openid')
    if not openid:
        return api_response({'error': '微信未返回 openid', 'raw': payload}, 502)

    # session_key 暂时用不上（没有解密加密数据的需求），不落库
    user, is_new = User.objects.get_or_create(
        openid=openid,
        defaults={'email': _wx_placeholder_email(openid)},
    )
    if is_new:
        # 微信用户没有密码：留一个不可用密码，避免空密码可登录
        user.set_unusable_password()
        user.save(update_fields=['password'])
    return api_response({'token': _ensure_api_token(user), 'is_new': is_new})


@csrf_exempt
@require_http_methods(['POST'])
def dev_login(request):
    """开发期过渡登录：email → 用户 → api_token。上线前把 ENABLE_DEV_LOGIN 关掉"""
    if not getattr(settings, 'ENABLE_DEV_LOGIN', False):
        return api_response({'error': '开发登录已关闭'}, 403)

    data = _json_body(request)
    email = _s(data.get('email'), 254)
    if not email or '@' not in email:
        return api_response({'error': 'email 无效'}, 400)

    user = User.objects.filter(email__iexact=email).first()
    is_new = False
    if user is None:
        user = User(email=email)
        user.set_unusable_password()
        user.save()
        is_new = True
    return api_response({'token': _ensure_api_token(user), 'is_new': is_new})


# ===== 网页版邮箱密码登录（#027）=====
# 和小程序那套是两套账号：网页用户 openid 为空，微信用户没有可用密码（set_unusable_password），
# 所以同一个邮箱不会串号；以后要做"绑定"再单独设计。

# ===== 登录防爆破 / 忘记密码的限流（#028）=====
# 计数放 Django 缓存（settings.CACHES = 数据库缓存），所以跨 gunicorn worker 也一致。
# 部署时别忘了 python manage.py createcachetable 建表；下面的读写都包了一层，
# 万一表没建也只是"少一层防护"，不会让登录 500。

logger = logging.getLogger(__name__)

LOGIN_MAX_PER_EMAIL = 5                 # 同一邮箱连续失败几次就锁
LOGIN_LOCK_EMAIL_SECONDS = 10 * 60      # 锁多久（#088：15 → 10 分钟，手滑连错的真人少等 5 分钟）
LOGIN_MAX_PER_IP = 20                   # 同一 IP 一小时内失败几次就锁
# #088 没把 IP 阈值压到 5：办公室/校园网是同一个出口 IP，5 次会把整片人锁在门外。
# 单账号的 5 次已经挡住"猜密码"的主要路径，IP 这一层只兜"同一台机器批量试很多账号"。
LOGIN_LOCK_IP_SECONDS = 60 * 60
FORGOT_MAX_PER_IP = 5                   # 同一 IP 一小时能申请几次重置邮件（别让人拿我们的 SMTP 轰炸别人）
FORGOT_LOCK_IP_SECONDS = 60 * 60
REGISTER_MAX_PER_IP = 5                 # 同一 IP 一小时最多建几个新账号
REGISTER_WINDOW_SECONDS = 60 * 60
RESET_MAX_PER_IP = 10                   # 同一 IP 一小时最多试几次重置密码
RESET_WINDOW_SECONDS = 60 * 60
PWD_RESET_TTL_SECONDS = 30 * 60         # 重置链接有效期


def _client_ip(request):
    """真实客户端 IP。

    nginx 用 `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`（DEPLOY.md），
    它的行为是"把 $remote_addr 追加到末尾"，而客户端自己塞的 XFF 会留在前面。
    所以**取最后一段**才是 nginx 亲眼看连接到的那个 IP；取第一段会被伪造的 XFF 绕过限流。
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        parts = [p.strip() for p in xff.split(',') if p.strip()]
        if parts:
            return parts[-1]
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def _fail_key_email(email):
    return 'login_fail_email_' + email.lower()


def _fail_key_ip(ip):
    return 'login_fail_ip_' + ip


def _reset_key(token):
    return 'pwd_reset_' + token


def _cache_get(key, default):
    """缓存读写统一包一层：数据库缓存表万一没建（部署漏跑 createcachetable），
    也不能让登录接口炸成 500——记日志、当"没锁"处理。宁可少一层防护，也不能让人登不进来。"""
    try:
        return cache.get(key, default)
    except Exception:
        logger.exception('读缓存失败 key=%s', key)
        return default


def _cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:
        logger.exception('写缓存失败 key=%s', key)


def _cache_delete(key):
    try:
        cache.delete(key)
    except Exception:
        logger.exception('删缓存失败 key=%s', key)


def _lock_remaining(key, limit, lock_seconds):
    """返回 (是否锁定, 剩余秒数)——计数没到阈值就没锁"""
    count = _cache_get(key, 0)
    if count < limit:
        return False, 0
    try:
        ttl = cache.ttl(key)   # 后端支持才拿得到；拿不到就用配置值兜底
    except Exception:
        ttl = None
    return True, (ttl if ttl else lock_seconds)


def _bump_failure(key, lock_seconds):
    """计数 +1，过期时间跟着最后一次动作往后推（滑动窗口）"""
    _cache_set(key, _cache_get(key, 0) + 1, lock_seconds)


def _clear_failures(email=None, ip=None):
    if email:
        _cache_delete(_fail_key_email(email))
    if ip:
        _cache_delete(_fail_key_ip(ip))


def _lock_message(remaining_seconds):
    """锁定时给用户看的话。别用"操作过于频繁"这种机器腔（#081 定下的调性）"""
    minutes = max(1, int((remaining_seconds + 59) // 60))
    if minutes >= 60:
        return f'试得有点频繁，歇 {max(1, minutes // 60)} 小时再试'
    return f'试得有点频繁，歇 {minutes} 分钟再试'


def _email_password_params(request):
    """注册/登录共用的入参校验。返回 (email, password, error_response)"""
    data = _json_body(request)
    raw_email = _s(data.get('email'))
    # #057④：先卡长度再截断。以前 _s(..., 254) 会把 300 字的输入悄悄截成 254 再校验，
    # 用户看到的是"格式不正确"，原因却无从判断；超长直接给明确的 400。
    if len(raw_email) > 254:
        return None, None, api_response({'error': '邮箱过长（最多 254 个字符）'}, 400)
    # 统一小写：否则 Foo@x.com 和 foo@x.com 会变成两个账号（email 字段是精确匹配的唯一约束）
    email = raw_email.lower()
    password = data.get('password') or ''
    try:
        validate_email(email)
    except ValidationError:
        return None, None, api_response({'error': '邮箱格式不正确'}, 400)
    if len(password) < 6:
        return None, None, api_response({'error': '密码至少 6 位'}, 400)
    return email, password, None


@csrf_exempt
@require_http_methods(['POST'])
def auth_register(request):
    """网页版注册：邮箱 + 密码 → 建号并直接给 token（注册即登录）"""
    email, password, err = _email_password_params(request)
    if err:
        return err

    # 按 IP 限流：一个 IP 一小时最多建 5 个号。
    # 只统计"建成的号"——"该邮箱已注册"这类失败不占额度，否则办公室 NAT 后面
    # 几个人互相把额度用光，谁都注册不了。
    ip = _client_ip(request)
    key = 'register_ip_' + ip
    locked, remaining = _lock_remaining(key, REGISTER_MAX_PER_IP, REGISTER_WINDOW_SECONDS)
    if locked:
        return api_response({'error': _lock_message(remaining)}, 429)

    if User.objects.filter(email__iexact=email).exists():
        return api_response({'error': '该邮箱已注册'}, 400)

    user = User(email=email)
    user.set_password(password)   # Django 自带哈希（PBKDF2），不存明文
    # #057③：别在"先 exists 再 create"之间留缝 —— 同一个邮箱双击提交会两个请求都过 exists，
    # 第二个撞唯一约束变成 500。靠约束兜底 + savepoint，翻译回 400。
    try:
        with transaction.atomic():
            user.save()           # api_token 由 User.save() 自动生成
    except IntegrityError:
        return api_response({'error': '该邮箱已注册'}, 400)
    _bump_failure(key, REGISTER_WINDOW_SECONDS)   # 建号成功才算用掉一次额度
    return api_response({'token': user.api_token, 'email': user.email})


@csrf_exempt
@require_http_methods(['POST'])
def auth_login(request):
    """网页版登录：邮箱 + 密码 → api_token（带失败计数与锁定）"""
    email, password, err = _email_password_params(request)
    if err:
        return err

    # 先看锁没锁：锁定期间即使密码是对的也不放行，否则爆破只是慢一点而已
    ip = _client_ip(request)
    locked, remaining = _lock_remaining(_fail_key_email(email), LOGIN_MAX_PER_EMAIL, LOGIN_LOCK_EMAIL_SECONDS)
    if not locked:
        locked, remaining = _lock_remaining(_fail_key_ip(ip), LOGIN_MAX_PER_IP, LOGIN_LOCK_IP_SECONDS)
    if locked:
        return api_response({'error': _lock_message(remaining)}, 429)

    user = User.objects.filter(email__iexact=email).first()
    # 邮箱不存在 / 密码不对 / 账号停用：回同一句话，不告诉对方"这个邮箱有没有注册过"
    if user is None or not user.check_password(password) or not user.is_active:
        _bump_failure(_fail_key_email(email), LOGIN_LOCK_EMAIL_SECONDS)
        _bump_failure(_fail_key_ip(ip), LOGIN_LOCK_IP_SECONDS)
        return api_response({'error': '邮箱或密码错误'}, 400)

    # 登录成功 → 把这个邮箱和这个 IP 的失败计数都清掉
    _clear_failures(email=email, ip=ip)
    return api_response({'token': _ensure_api_token(user), 'email': user.email})


# ===== 忘记密码（#028）=====

@csrf_exempt
@require_http_methods(['POST'])
def auth_forgot(request):
    """申请重置密码：无论邮箱是否存在都回同一句话，不泄露注册情况"""
    data = _json_body(request)
    email = _s(data.get('email'), 254).lower()
    try:
        validate_email(email)
    except ValidationError:
        return api_response({'error': '邮箱格式不正确'}, 400)

    # 按 IP 限流：否则谁都能拿我们的 SMTP 去轰炸任意邮箱（和邮箱存不存在无关，不泄露信息）
    ip = _client_ip(request)
    key = 'forgot_ip_' + ip
    locked, remaining = _lock_remaining(key, FORGOT_MAX_PER_IP, FORGOT_LOCK_IP_SECONDS)
    if locked:
        return api_response({'error': _lock_message(remaining)}, 429)
    _bump_failure(key, FORGOT_LOCK_IP_SECONDS)

    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        token = secrets.token_urlsafe(32)
        _cache_set(_reset_key(token), user.pk, PWD_RESET_TTL_SECONDS)
        # H5 是 history 路由，链接就是 /app/pages/login/reset?token=xxx（不是 #/ 那种）。
        # 2026-10-15：网页版就部署在 /app/ 下（之前短暂迁到根路径又改回来了），
        # 前缀必须跟 manifest.json 的 h5.router.base 一致，否则邮件里的链接点开是 404
        reset_url = f'{settings.SITE_URL}/app/pages/login/reset?token={token}'
        try:
            send_mail(
                subject='行动锚 · 重置密码',
                message=(
                    '你在「行动锚」网页版申请了重置密码。\n\n'
                    f'点这个链接设置新密码（30 分钟内有效）：\n{reset_url}\n\n'
                    '如果不是你本人操作，忽略这封邮件就行，密码不会变。'
                ),
                from_email=None,   # 用 settings.DEFAULT_FROM_EMAIL
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            # 发信失败不能让接口 500（用户会以为没注册），但后台必须能看到
            logger.exception('重置密码邮件发送失败 email=%s', email)

    return api_response({'message': '如果该邮箱已注册，重置邮件已发送'})


@csrf_exempt
@require_http_methods(['POST'])
def auth_reset(request):
    """用邮件里那个一次性 token 设置新密码"""
    data = _json_body(request)
    token = _s(data.get('token'), 128)
    password = data.get('password') or ''
    if len(password) < 6:
        return api_response({'error': '密码至少 6 位'}, 400)

    # 按 IP 限流：token 是 43 位随机串猜不出来，这里主要防"拿脚本反复打这个接口"
    ip = _client_ip(request)
    limit_key = 'reset_ip_' + ip
    locked, remaining = _lock_remaining(limit_key, RESET_MAX_PER_IP, RESET_WINDOW_SECONDS)
    if locked:
        return api_response({'error': _lock_message(remaining)}, 429)
    _bump_failure(limit_key, RESET_WINDOW_SECONDS)

    key = _reset_key(token)
    user_id = _cache_get(key, None) if token else None
    user = User.objects.filter(pk=user_id).first() if user_id else None
    if user is None:
        # token 不存在（用完删了 / 过期 / 伪造）：都当同一件事，不区分
        return api_response({'error': '链接无效或已过期'}, 400)

    user.set_password(password)
    user.save(update_fields=['password'])
    _cache_delete(key)                    # 一次性：用过即失效
    _clear_failures(email=user.email)     # 重置成功顺带解锁这个邮箱（IP 计数不动）
    return api_response({'ok': True})


# ===== #C 我的笔记（聚合）：前端"我的"页一次拿全，避免按模板逐个请求 =====

@require_GET
@require_token
def quick_my_notes(request):
    notes = QuickNote.objects.filter(user=request.user).select_related('pattern')
    return api_response([
        {
            'id': n.pk,
            'content': n.content,
            'created_at': n.created_at.isoformat(),
            'pattern_id': n.pattern_id,
            'pattern_title': n.pattern.title,
            'pattern_icon': n.pattern.icon,
            # #073：笔记列表也要矢量图标（前端优先 icon_key，空则回退 emoji）
            'pattern_icon_key': n.pattern.icon_key,
        }
        for n in notes
    ])


# ===== #071：个人资料（昵称 / 头像）=====

def _profile_payload(request, user):
    """资料区要的东西：邮箱、昵称、头像绝对地址、对外显示名（#070 的口径）。"""
    avatar_url = ''
    if getattr(user, 'avatar', None):
        try:
            avatar_url = request.build_absolute_uri(user.avatar.url)
        except Exception:
            avatar_url = ''
    return {
        'email': user.email,
        'nickname': getattr(user, 'nickname', '') or '',
        'avatar_url': avatar_url,
        # 昵称/邮箱前缀都不体面时这里就是「行动锚用户」——前端直接显示它，别自己再判一次
        'display_name': user_display_name(user, fallback='行动锚用户'),
    }


@csrf_exempt
@require_token
def me_profile(request):
    """#071 我的资料：GET 读、PUT 改昵称（头像走 /me/avatar/ 单独上传）。"""
    if request.method == 'GET':
        return api_response(_profile_payload(request, request.user))
    if request.method == 'PUT':
        data = _json_body(request)
        nickname = _s(data.get('nickname'), 30)
        # 昵称是给人看的：纯数字（像 10000000 这种）没意义，直接挡住，
        # 否则存进去也会被 user_display_name 判为不可用、显示成「行动锚用户」，用户会困惑。
        if nickname and nickname.isdigit():
            return api_response({'error': '昵称不能是纯数字'}, 400)
        request.user.nickname = nickname
        request.user.save(update_fields=['nickname'])
        return api_response(_profile_payload(request, request.user))
    return api_response({'error': '方法不允许'}, 405)


@csrf_exempt
@require_token
def me_avatar(request):
    """#071 上传头像（multipart，字段名 avatar）。校验复用 users.views._clean_avatar（#057⑤）。"""
    if request.method != 'POST':
        return api_response({'error': '方法不允许'}, 405)
    upload = request.FILES.get('avatar')
    if upload is None:
        return api_response({'error': '没有收到 avatar 文件'}, 400)
    err, new_name = _clean_avatar(upload)
    if err:
        return api_response({'error': err}, 400)
    request.user.avatar.save(new_name, upload, save=False)
    request.user.save(update_fields=['avatar'])
    return api_response(_profile_payload(request, request.user))


@require_GET
@require_token
def quick_history(request):
    """#071 浏览记录：我最近看过的【仍然公开】的模板，时间倒序（最多 100 条）。

    · 只记公开模板：写记录时已过滤（见 quick_detail），这里再过滤一次，
      被下架/被举报之后的记录就不会再露出来；
    · 同一模板只留一行（QuickView 有唯一约束），重看会刷新时间 → 列表天然去重。
    """
    rows = (QuickView.objects
            .filter(user=request.user, pattern__is_listed=True, pattern__is_reported=False)
            .select_related('pattern').prefetch_related('pattern__steps', 'pattern__favorites')
            .order_by('-viewed_at')[:100])
    data = []
    for v in rows:
        d = serialize_quick(v.pattern)
        d['viewed_at'] = v.viewed_at.isoformat()
        data.append(d)
    return api_response(data)
