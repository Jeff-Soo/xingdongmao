"""#046 多模板批量导入：校验 + 落库的共享核心。

两个入口共用这一份逻辑（避免两处规则跑偏）：
  · 内部 API    POST /api/v1/quick/batch-import/   → token + is_staff
  · 管理端页面  /admin/quick/batch-import/          → admin_view（同样只放 is_staff 进）

原则（按任务 #046）：
  · 逐条独立：某条校验不过只跳过它，返回原因，绝不让整批失败；
  · 一律建成【草稿】，内部复核后再发布；
  · 单条写入用事务包住（原子）；
  · 标题去重：同一批内 + 库里已有同名的都跳过并提示；
  · 校验从严：category 必须是枚举 key，title 不能空，步数 1-20（#047 由 8 放宽），时长非负整数。
"""

from django.db import transaction

from .models import QuickPattern, QuickStep

MAX_TEMPLATES = 50   # 一次最多导入多少个模板
MIN_STEPS = 1
MAX_STEPS = 20       # 单个模板最多几步（#047：8 → 20，复杂 SOP 如空调清洗本就 10-20 步）
MAX_TITLE = 100      # 对齐 QuickPattern.title / QuickStep.title 的 max_length
MAX_TAGLINE = 200    # 对齐 QuickPattern.tagline
MAX_DESC = 1000
MAX_LONG_TEXT = 2000  # instruction / explain（模型是 TextField，这里防脏数据）
MAX_MAX_ORDER = 100  # 步骤顺序上限（防脏数据；正常模板不会有 100 步）
MAX_SECONDS = 3600
MAX_ICON = 5         # 对齐 QuickPattern.icon 的 max_length
DEFAULT_ICON = '📋'
# #073：图标从"存 emoji"改成"存 slug"（前端按 slug 画矢量图标），emoji 字段保留做回退。
# 允许的 slug 必须和 xingdongmao/utils/icons.js 的 PICKER_ICONS 一致，否则前端画不出来。
MAX_ICON_KEY = 32    # 对齐 QuickPattern.icon_key
DEFAULT_ICON_KEY = 'clipboard-text'
VALID_ICON_KEYS = {
    'clipboard-text', 'check-square', 'brain', 'door', 'package', 'house', 'shopping-cart',
    'fork-knife', 'cooking-pot', 'flame', 'wrench', 'broom', 'briefcase', 'arrows-clockwise',
    'warning', 'note-pencil', 'key', 'chat-circle-dots', 'clock', 'map-pin', 'car', 'plant',
    'heart', 'list-checks', 'calendar', 'users', 'shield-check', 'first-aid', 'sparkle',
}

CATEGORY_LABELS = dict(QuickPattern.CATEGORY_CHOICES)
VALID_CATEGORIES = set(CATEGORY_LABELS)


# ===== #057⑥ 三个创建入口共用的"创建参数表" =====
# 入口：/api/v1/quick/（App 创建）、/api/v1/quick/import/（App 导入）、batch-import（内部批量）。
# 以前三处各写一遍长度/枚举/图标默认值，改一处漏两处（#056 就是漏出来的）。
# 唯一的口径差异是"超长怎么办"，所以留一个 strict 开关，而不是各写一份：
#   strict=True （内部批量导入）：超长直接判错，导入前逐条提示，别悄悄改用户内容；
#   strict=False（App 创建/导入）：超长截断到上限，用户不该因为多打几个字就保存失败（#056 定的）。

def _text(value, limit, strict, default=''):
    """取一个字符串字段：非字符串先 str()，去空白，超长按 strict 决定判错还是截断。

    limit=None 表示不设上限（description 用：它是 TextField，手工写的长描述不该被悄悄截短）。
    """
    if value is None:
        return default
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if limit is None:
        return value
    if strict and len(value) > limit:
        raise ValueError(f'超过 {limit} 字（{len(value)} 字）')
    return value[:limit]


def clean_pattern_fields(data, strict=False):
    """模板顶层字段（title/tagline/description/category/icon/icon_key）的唯一口径。

    返回 (字段字典, 错误原因)。字段字典可直接解包进 QuickPattern.objects.create()。

    strict 之外的唯一差异：description 在 lenient 路径不截断（模型是 TextField，
    编辑已有模板时不该因为描述长而被缩短），批量导入路径仍按 MAX_DESC 卡。

    #073：icon_key（矢量图标 slug）为空时【不写默认值】，让前端按"没有 slug"回退到 emoji，
    这样批量导入/老客户端不传 icon_key 也不会把已经选好的图标洗掉。
    """
    if not isinstance(data, dict):
        return None, '请求体必须是 JSON 对象'
    try:
        title = _text(data.get('title'), MAX_TITLE, strict)
        if not title:
            return None, 'title 不能为空'
        category = data.get('category') or 'other'
        if category not in VALID_CATEGORIES:
            return None, 'category 无效（只能用 ' + '/'.join(sorted(VALID_CATEGORIES)) + '）'
        icon_key = _text(data.get('icon_key'), MAX_ICON_KEY, strict)
        if icon_key and icon_key not in VALID_ICON_KEYS:
            return None, 'icon_key 无效（不是允许的图标名）'
        return {
            'title': title,
            'tagline': _text(data.get('tagline'), MAX_TAGLINE, strict),
            'description': _text(data.get('description'), MAX_DESC if strict else None, strict),
            'category': category,
            'icon': _text(data.get('icon'), MAX_ICON, strict) or DEFAULT_ICON,
            'icon_key': icon_key,
        }, None
    except ValueError as exc:
        return None, f'{exc}'


def clean_duration(value):
    """步骤时长的唯一口径：能转整数就转，负数取 0，上限 MAX_SECONDS。

    #057②：#057 P2-② 要求 is_timed 只由时长派生（is_timed = duration > 0），
    所以调用方一律写成 `is_timed=clean_duration(x) > 0`，别再单独读请求里的 is_timed。
    """
    seconds = value
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        try:
            seconds = int(str(seconds).strip())
        except (TypeError, ValueError):
            seconds = 0
    return max(0, min(MAX_SECONDS, seconds))



# ===== 给内部导入页用的提示词（#046 §五 定稿版，图片 → 模板 JSON）=====

PROMPT_TEXT = """你是一个 SOP 提取助手。我给你【图片】（可能是带标注的操作说明图、小红书笔记、教程截图等）。请提取其中"可以照着做的操作步骤"，按下面的 JSON 格式输出。

要求：
1. 只提取图片里【明确写/画出来】的操作，不编造、不补外部知识。
2. 把操作细化、原子化成步骤（一步一个动作）。
3. 推断合理的【时长】（秒）：
   - 图里有时间就换算
   - 没有就按动作性质推断（如"浸泡10分钟"=600秒）
   - 纯静态动作写 0
4. 分类从这些里选一个（填 key）：
   life_out 出行准备 / life_home 居家事务 / life_daily 日常事务 /
   work_service 服务行业 / work_office 职场办公 / work_safety 安全操作 / other 其他
5. 图标用一个 emoji。
6. 一张图可能出 0-3 个模板；没内容就返回空数组。
7. 步数控制：单个模板 3-20 步。
   - 正常流程：直接完整输出（哪怕 15-20 步也可以）
   - 如果【超过 20 步】：拆成 2-3 个模板，每个覆盖一个阶段（如"拆装"→"清洁"→"复位"），分别命名
   - 不要为了压缩步数而合并动作（一步一动作更清晰）
8. 【必填，不许留空】：
   - 每个模板的 title（模板名）必须非空；
   - 每一步的 title（动作）必须非空。
   这两项留空后端会整条跳过（等于白导），信息再少也要给一句简短的名字。

输出格式（只输出 JSON，不要别的文字）：
{
  "templates": [
    {
      "title": "",
      "tagline": "",
      "description": "",
      "category": "other",
      "icon": "📋",
      "steps": [
        { "title": "", "instruction": "", "explain": "", "duration_seconds": 0 }
      ]
    }
  ]
}

【图片】：
（把图发给 AI）"""


# ===== 校验 =====

def _clean_text(raw, key, limit, required=False):
    """取一个字符串字段。返回 (值, 错误原因)。"""
    value = raw.get(key)
    if value is None:
        value = ''
    if not isinstance(value, str):
        return None, f'{key} 必须是字符串'
    value = value.strip()
    if required and not value:
        return None, f'{key} 为空'
    if len(value) > limit:
        return None, f'{key} 超过 {limit} 字（{len(value)} 字）'
    return value, None


def _clean_step(raw, idx):
    if not isinstance(raw, dict):
        return None, f'第 {idx} 步不是 JSON 对象'
    title, err = _clean_text(raw, 'title', MAX_TITLE, required=True)
    if err:
        return None, f'第 {idx} 步 {err}'
    instruction, err = _clean_text(raw, 'instruction', MAX_LONG_TEXT)
    if err:
        return None, f'第 {idx} 步 {err}'
    explain, err = _clean_text(raw, 'explain', MAX_LONG_TEXT)
    if err:
        return None, f'第 {idx} 步 {err}'

    seconds = raw.get('duration_seconds', 0)
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        # 容忍 "30" 这种字符串（AI 有时会加引号），但仅限能转成整数的
        try:
            seconds = int(str(seconds).strip())
        except (TypeError, ValueError):
            return None, f'第 {idx} 步 duration_seconds 不是整数'
    if seconds < 0:
        return None, f'第 {idx} 步 duration_seconds 不能为负数'
    if seconds > MAX_SECONDS:
        return None, f'第 {idx} 步 duration_seconds 超过 {MAX_SECONDS} 秒'

    return {
        'title': title,
        'instruction': instruction,
        'explain': explain,
        'duration_seconds': seconds,
        'is_timed': seconds > 0,
    }, None


def clean_template(raw):
    """单个模板校验。返回 (干净数据, None) 或 (None, 原因)。"""
    if not isinstance(raw, dict):
        return None, '不是 JSON 对象'

    # #057⑥：顶层字段走共用口径（strict=True：批量导入宁可判错也不要悄悄截断）
    fields, err = clean_pattern_fields(raw, strict=True)
    if err:
        return None, err

    steps_raw = raw.get('steps')
    if not isinstance(steps_raw, list) or not steps_raw:
        return None, f'steps 为空（至少 {MIN_STEPS} 步）'
    if len(steps_raw) > MAX_STEPS:
        return None, f'步骤过多（{len(steps_raw)} 步，单个模板上限 {MAX_STEPS} 步），建议拆成 2-3 个模板'

    steps = []
    for i, s in enumerate(steps_raw, start=1):
        step, err = _clean_step(s, i)
        if err:
            return None, err
        steps.append(step)

    return {**fields, 'steps': steps}, None


def parse_templates(payload):
    """顶层结构校验。返回 templates 列表，结构不对抛 ValueError。"""
    if not isinstance(payload, dict):
        raise ValueError('请求体必须是 JSON 对象')
    templates = payload.get('templates')
    if not isinstance(templates, list):
        raise ValueError('缺少 templates 数组')
    if not templates:
        raise ValueError('templates 是空数组')
    if len(templates) > MAX_TEMPLATES:
        raise ValueError(f'一次最多 {MAX_TEMPLATES} 个模板（收到 {len(templates)} 个）')
    return templates


def _peek_title(raw):
    """报错时回显一下标题，方便对着 AI 给的 JSON 找问题"""
    if isinstance(raw, dict) and isinstance(raw.get('title'), str):
        return raw['title'].strip()[:MAX_TITLE]
    return ''


def import_templates(templates, author, is_official=True):
    """逐条校验 + 建成草稿。返回 {created, skipped, errors}。"""
    created = 0
    skipped = []
    seen = set()  # 本批次内去重

    for index, raw in enumerate(templates):
        clean, reason = clean_template(raw)
        if reason:
            skipped.append({'index': index, 'title': _peek_title(raw), 'reason': reason})
            continue

        title = clean['title']
        if title in seen:
            skipped.append({'index': index, 'title': title, 'reason': '标题重复（同一批里已出现过）'})
            continue
        if QuickPattern.objects.filter(title=title).exists():
            skipped.append({'index': index, 'title': title, 'reason': '标题已存在，跳过（避免重复上架）'})
            continue

        try:
            with transaction.atomic():
                qp = QuickPattern.objects.create(
                    title=title,
                    tagline=clean['tagline'],
                    description=clean['description'],
                    category=clean['category'],
                    icon=clean['icon'],
                    # #073：批量导入也吃 icon_key（没传就留空 = 前端回退 emoji）
                    icon_key=clean.get('icon_key', ''),
                    author=author,
                    is_official=is_official,
                    status='draft',  # 一律草稿，复核后再发布
                )
                QuickStep.objects.bulk_create([
                    QuickStep(pattern=qp, order=i, **step)
                    for i, step in enumerate(clean['steps'], start=1)
                ])
        except Exception as exc:  # 兜底：单条炸了也不能带塌整批
            skipped.append({'index': index, 'title': title, 'reason': f'写入失败：{exc}'})
            continue

        seen.add(title)
        created += 1

    return {'created': created, 'skipped': skipped, 'errors': []}
