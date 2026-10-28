import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction
from django.conf import settings
from django.contrib import messages
from patterns.models import Pattern, TimeBlock
from plans.models import UserPlan, UserPlanBlock, DayExecution
from django.utils import timezone
from django.http import HttpResponse
from django.http import JsonResponse
from django.template.loader import render_to_string
from datetime import date, timedelta, datetime, time as dtime
from PIL import Image, ImageDraw, ImageFont
import io

# 字体文件路径
FONTS_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts')
FONT_REGULAR = os.path.join(FONTS_DIR, 'NotoSansSC-Regular.otf')
FONT_BOLD = os.path.join(FONTS_DIR, 'NotoSansSC-Bold.otf')


def _create_today_execution(user):
    """内部函数：为今天创建/更新 DayExecution 聚合快照"""
    today = timezone.localdate()
    enabled_plans = UserPlan.objects.filter(user=user, is_enabled=True)
    all_blocks = UserPlanBlock.objects.filter(plan__in=enabled_plans)
    total = all_blocks.count()
    completed = all_blocks.filter(is_completed=True).count()

    execution, _ = DayExecution.objects.update_or_create(
        user=user,
        date=today,
        defaults={
            'total_blocks': total,
            'completed_blocks': completed,
            'completion_rate': completed / total if total > 0 else 0,
        }
    )
    execution.enabled_plans.set(enabled_plans)
    return execution


@login_required
def calendar_data(request):
    """返回近 90 天每日完成率数据，供热力图使用"""
    today = date.today()
    start_date = today - timedelta(days=89)

    executions = DayExecution.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=today
    ).values('date', 'completion_rate', 'total_blocks', 'completed_blocks', 'skipped_blocks')

    data = {}
    for exe in executions:
        data[exe['date'].strftime('%Y-%m-%d')] = {
            'rate': exe['completion_rate'],
            'total': exe['total_blocks'],
            'completed': exe['completed_blocks'],
            'skipped': exe['skipped_blocks'],
        }

    return JsonResponse({'data': data, 'start': start_date.strftime('%Y-%m-%d'), 'end': today.strftime('%Y-%m-%d')})

@login_required
def publish_as_pattern(request, pk):
    plan = get_object_or_404(UserPlan, pk=pk, user=request.user)
    # 创建新 Pattern，fork_from 指向原模板
    new_pattern = Pattern.objects.create(
        title=request.POST.get('title', plan.title),
        description=request.POST.get('description', ''),
        category=plan.pattern.category if plan.pattern else '',
        difficulty='medium',
        author=request.user,
        fork_from=plan.pattern,
    )
    # 复制时间块
    for block in plan.blocks.all():
        TimeBlock.objects.create(
            pattern=new_pattern,
            order=block.order,
            start_time=block.start_time,
            end_time=block.end_time,
            action=block.action,
            notes=block.notes,
        )
    plan.is_public = True
    plan.save()
    return redirect('patterns:pattern_detail', pk=new_pattern.pk)

@login_required
def calendar_view(request):
    """个人日历热力图页面"""
    return render(request, 'plans/calendar.html')


@login_required
def fork_pattern(request, pattern_pk):
    pattern = get_object_or_404(Pattern, pk=pattern_pk)

    # 防止重复 Fork
    if UserPlan.objects.filter(user=request.user, pattern=pattern).exists():
        messages.warning(request, f'「{pattern.title}」已经在收藏库中，不能重复收藏')
        return redirect('patterns:pattern_detail', pk=pattern_pk)

    plan = UserPlan.fork_from_pattern(pattern, request.user)
    messages.success(request, f'「{plan.title}」已收藏到计划库')
    return redirect('patterns:pattern_detail', pk=pattern_pk)


@login_required
def plan_list(request):
    tab = request.GET.get('tab', 'collection')
    plans = UserPlan.objects.filter(user=request.user).prefetch_related('blocks')
    today = timezone.localdate()

    # "今日计划"标签用
    enabled = plans.filter(is_enabled=True)
    enabled_count = enabled.count()
    merged_blocks = []
    if tab == 'today':
        merged_blocks = UserPlanBlock.objects.filter(
            plan__in=enabled
        ).order_by('start_time')

    return render(request, 'plans/plan_list.html', {
        'plans': plans,
        'tab': tab,
        'enabled_count': enabled_count,
        'merged_blocks': merged_blocks,
        'today': today,
    })

@login_required
@transaction.atomic
def plan_edit(request, pk):
    plan = get_object_or_404(UserPlan, pk=pk, user=request.user)
    blocks = plan.blocks.all()

    if request.method == 'POST':
        # 处理删除
        delete_pk = request.POST.get('delete_block')
        if delete_pk:
            UserPlanBlock.objects.filter(pk=delete_pk, plan=plan).delete()
            return redirect('plans:plan_edit', pk=plan.pk)

        # 处理时间块更新
        for block in blocks:
            start_val = request.POST.get(f'start_time_{block.pk}', '').strip()
            end_val = request.POST.get(f'end_time_{block.pk}', '').strip()
            action_val = request.POST.get(f'action_{block.pk}', '').strip()
            if action_val:
                block.start_time = start_val or '08:00'
                block.end_time = end_val or '08:30'
                block.action = action_val
                block.save()
        # 处理新增
        new_action = request.POST.get('new_action')
        if new_action:
            UserPlanBlock.objects.create(
                plan=plan,
                order=blocks.count(),
                start_time=request.POST.get('new_start_time'),
                end_time=request.POST.get('new_end_time'),
                action=new_action,
            )
        return redirect('plans:plan_edit', pk=plan.pk)

    return render(request, 'plans/plan_edit.html', {'plan': plan, 'blocks': blocks})


@login_required
@ensure_csrf_cookie
def plan_execute(request, pk):
    plan = get_object_or_404(UserPlan, pk=pk, user=request.user)
    blocks = plan.blocks.all()  # Meta ordering = ['start_time'] 自动按时间排序
    today = timezone.localdate()
    return render(request, 'plans/plan_execute.html', {
        'plan': plan,
        'blocks': blocks,
        'today': today,
    })
@login_required
@ensure_csrf_cookie
def daily_execute(request):
    """多计划合并执行页：拉取所有已启用 Plan 的时间块，合并排序"""
    today = timezone.localdate()

    enabled_plans = UserPlan.objects.filter(
        user=request.user, is_enabled=True
    ).prefetch_related('blocks')

    # 每日自动重置：如果有昨天（或更早）完成的块，全部重置为新的一天
    stale_blocks = UserPlanBlock.objects.filter(
        plan__in=enabled_plans,
        is_completed=True,
        completed_at__date__lt=today
    )
    if stale_blocks.exists():
        stale_blocks.update(
            is_completed=False,
            completed_at=None,
            original_action='',
            original_end_time=None,
            has_time_conflict=False,
            conflict_note='',
        )

    # 收集所有时间块，标注来源 Plan
    all_blocks = []
    for plan in enabled_plans:
        for block in plan.blocks.all():
            all_blocks.append({
                'pk': block.pk,
                'plan_title': plan.title,
                'plan_pk': plan.pk,
                'created_at': plan.created_at,
                'start_time': block.start_time,
                'end_time': block.end_time,
                'action': block.action,
                'is_completed': block.is_completed,
                'completed_at': block.completed_at,
                'has_conflict': False,
            })

    # 按开始时间排序
    all_blocks.sort(key=lambda b: b['start_time'])

    # 检测时间冲突：两个块时间重叠 → 两边都标记
    for i in range(len(all_blocks) - 1):
        current = all_blocks[i]
        next_block = all_blocks[i + 1]
        if current['end_time'] > next_block['start_time']:
            current['has_conflict'] = True
            current['conflict_note'] = f"时间与「{next_block['plan_title']}」的 {next_block['start_time'].strftime('%H:%M')} 冲突，请调整"
            next_block['has_conflict'] = True
            next_block['conflict_note'] = f"时间与「{current['plan_title']}」的 {current['start_time'].strftime('%H:%M')} 冲突，请调整"

    all_completed = all(b['is_completed'] for b in all_blocks) if all_blocks else False

    return render(request, 'plans/daily_execute.html', {
        'blocks': all_blocks,
        'all_completed': all_completed,
        'today': today,
    })

@login_required
def activate_plan(request, pk):
    """将某个计划设为今日计划"""
    plan = get_object_or_404(UserPlan, pk=pk, user=request.user)
    today = timezone.localdate()

    # 先清除该用户所有计划的激活状态
    UserPlan.objects.filter(user=request.user).exclude(pk=plan.pk).update(activated_date=None)
    # 再激活当前计划，同时重置所有时间块的完成状态（新的一天从头开始）
    plan.activated_date = today
    plan.save()
    plan.blocks.all().update(
        is_completed=False,
        completed_at=None,
        original_action='',
        original_end_time=None,
    )

    return redirect('plans:plan_execute', pk=plan.pk)


@login_required
def move_block(request, pk, direction):
    """方向：'up' 或 'down' — 只交换 action 与 notes，时间位置不变"""
    block = get_object_or_404(UserPlanBlock, pk=pk, plan__user=request.user)
    if direction == 'up':
        target = UserPlanBlock.objects.filter(
            plan=block.plan, start_time__lt=block.start_time
        ).order_by('-start_time').first()
    else:  # down
        target = UserPlanBlock.objects.filter(
            plan=block.plan, start_time__gt=block.start_time
        ).order_by('start_time').first()

    if target:
        # 只交换动作文字和备注，时间 + order 保持固定
        block.action, target.action = target.action, block.action
        block.notes, target.notes = target.notes, block.notes
        block.save()
        target.save()

    return redirect('plans:plan_edit', pk=block.plan.pk)


@login_required
def inline_edit_block(request, pk):
    """行内编辑时间块的动作或时间（HTMX 驱动）"""
    block = get_object_or_404(UserPlanBlock, pk=pk, plan__user=request.user)

    if request.method == 'POST':
        field = request.POST.get('field', '')
        value = request.POST.get('value', '').strip()
        if not value:
            return HttpResponse('不能为空', status=400)

        if field == 'action':
            block.action = value
            block.save()
            return HttpResponse(render_to_string('plans/partials/inline_edit_span.html',
                                                 {'block': block, 'field': 'action', 'value': value}))

        elif field == 'start_time':
            try:
                h, m = value.split(':')
                block.start_time = dtime(int(h), int(m))
                block.save()
                return HttpResponse(render_to_string('plans/partials/inline_edit_span.html',
                                                     {'block': block, 'field': 'start_time',
                                                      'value': block.start_time.strftime('%H:%M')}))
            except ValueError:
                return HttpResponse('格式：HH:MM', status=400)

        elif field == 'end_time':
            try:
                h, m = value.split(':')
                block.end_time = dtime(int(h), int(m))
                block.save()
                return HttpResponse(render_to_string('plans/partials/inline_edit_span.html',
                                                     {'block': block, 'field': 'end_time',
                                                      'value': block.end_time.strftime('%H:%M')}))
            except ValueError:
                return HttpResponse('格式：HH:MM', status=400)

        return HttpResponse('未知字段', status=400)

    # GET：返回编辑输入框
    field = request.GET.get('field', 'action')
    current = block.action if field == 'action' else (
        block.start_time.strftime('%H:%M') if field == 'start_time' else block.end_time.strftime('%H:%M')
    )

    return HttpResponse(render_to_string('plans/partials/inline_edit_input.html',
                                         {'block': block, 'field': field, 'current': current}))


@login_required
def complete_block(request, pk):
    block = get_object_or_404(UserPlanBlock, pk=pk, plan__user=request.user)
    block.is_completed = True
    block.completed_at = timezone.now()
    block.save()

    # 检查是否所有已启用 Plan 的所有时间块都已完成（支持单 Plan 和多 Plan）
    remaining = UserPlanBlock.objects.filter(
        plan__user=request.user,
        plan__is_enabled=True,
        is_completed=False
    ).count()
    is_all_done = (remaining == 0)

    # 全部完成时立即创建 DayExecution 快照
    if is_all_done:
        _create_today_execution(request.user)

    html = render_to_string('plans/partials/block_complete.html', {'block': block})
    response = HttpResponse(html)

    if is_all_done:
        response['HX-Refresh'] = 'true'

    return response


@login_required
def undo_block(request, pk):
    """撤销完成——把已勾选的任务恢复为未完成"""
    block = get_object_or_404(UserPlanBlock, pk=pk, plan__user=request.user)
    block.is_completed = False
    block.completed_at = None
    block.save()

    html = render_to_string('plans/partials/block_undo.html', {'block': block})
    return HttpResponse(html)


@login_required
def end_today(request):
    """手动结束今日——生成最终 DayExecution 快照"""
    _create_today_execution(request.user)
    messages.success(request, '今日已结束，辛苦了 🌙')
    return redirect('plans:plan_list')


@login_required
def toggle_enabled(request, pk):
    """切换 Plan 的启用/停用状态（上限 3 个）"""
    plan = get_object_or_404(UserPlan, pk=pk, user=request.user)

    if not plan.is_enabled:
        # 要启用：检查是否已达上限
        enabled_count = UserPlan.objects.filter(user=request.user, is_enabled=True).count()
        if enabled_count >= 3:
            messages.warning(request, '不要贪多哦 😅 最多同时启用 3 个计划')
            return redirect('plans:plan_list')

    plan.is_enabled = not plan.is_enabled
    plan.save()
    return redirect('plans:plan_list')


@login_required
def delete_plan(request, pk):
    """从收藏库删除计划"""
    plan = get_object_or_404(UserPlan, pk=pk, user=request.user)
    if request.method == 'POST':
        title = plan.title
        plan.delete()
        messages.success(request, f'「{title}」已从收藏库移除')
    return redirect('plans:plan_list')


@login_required
def save_mood(request):
    """保存今日感受——写入 DayExecution 快照，不依赖 session"""
    execution = _create_today_execution(request.user)

    # 保存感受到当日快照（数据库持久化，不随 session 过期丢失）
    execution.mood = request.POST.get('mood', '')
    execution.note = request.POST.get('note', '')
    execution.save(update_fields=['mood', 'note'])

    messages.success(request, '感受已保存 🤍')

    return redirect('plans:plan_list')


@login_required
def toggle_lazy_mode(request):
    """全局切换轻松模式：将所有已启用 Plan 的 UserPlanBlock 替换为备选动作"""
    enabled_plans = UserPlan.objects.filter(user=request.user, is_enabled=True)

    if request.method == 'POST':
        enable = request.POST.get('enable') == '1'

        for plan in enabled_plans:
            for block in plan.blocks.all():
                if enable:
                    if not block.original_action:
                        block.original_action = block.action
                        block.original_end_time = block.end_time
                    if block.alt_action:
                        block.action = block.alt_action
                    if block.alt_duration_minutes:
                        start_dt = datetime.combine(datetime.today(), block.start_time)
                        new_end = start_dt + timedelta(minutes=block.alt_duration_minutes)
                        block.end_time = new_end.time()
                else:
                    if block.original_action:
                        block.action = block.original_action
                        block.original_action = ''
                    if block.original_end_time:
                        block.end_time = block.original_end_time
                block.save()

        request.session['is_lazy_mode'] = enable

    # 跳转到多计划合并执行页
    first_enabled = enabled_plans.first()
    if first_enabled:
        return redirect('plans:daily_execute')
    return redirect('plans:plan_list')


@login_required
def day_detail(request, pk):
    """查看某一天的执行详情（多 Plan 聚合视图）"""
    execution = get_object_or_404(DayExecution, pk=pk, user=request.user)
    # 获取当天所有启用 Plan 的时间块，按时间排序
    plans = execution.enabled_plans.all()
    blocks = UserPlanBlock.objects.filter(
        plan__in=plans,
        completed_at__date=execution.date
    ).order_by('start_time')

    return render(request, 'plans/day_detail.html', {
        'execution': execution,
        'blocks': blocks,
        'plans': plans,
    })


@login_required
def today_share_card(request):
    """生成今日战绩分享卡片（无 DayExecution 时自动生成快照）"""
    today = timezone.localdate()

    execution = _create_today_execution(request.user)

    if not execution or execution.total_blocks == 0:
        return HttpResponse('今天还没有执行记录', status=404)

    img = Image.new('RGB', (1080, 1440), color='#0f172a')
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype(FONT_BOLD, 68)
        font_body = ImageFont.truetype(FONT_REGULAR, 40)
        font_small = ImageFont.truetype(FONT_REGULAR, 32)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = font_title
        font_small = font_title

    def wrap(text, font, max_w):
        import re
        text = re.sub(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2702-\u27B0\u24C2-\U0001F251\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u200d\uFE0F]', '', text)
        lines, cur = [], ''
        for ch in text:
            test = cur + ch
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_w and cur:
                lines.append(cur); cur = ch
            else:
                cur = test
        if cur: lines.append(cur)
        return lines or [text]

    draw.text((70, 80), f"{today.strftime('%Y.%m.%d')}  今日战绩", fill='#ffffff', font=font_title)
    pct = execution.completion_rate
    color = '#22c55e' if pct >= 0.7 else '#f59e0b' if pct >= 0.4 else '#ef4444'
    draw.text((70, 240), f"完成率 {pct:.0%}", fill=color, font=font_title)
    draw.text((70, 370), f"{execution.completed_blocks}/{execution.total_blocks} 项完成", fill='#94a3b8', font=font_body)

    y = 480
    mood = execution.mood
    note = execution.note
    if mood:
        draw.text((70, y), f"今日感受：{mood}", fill='#fbbf24', font=font_body)
        y += 60
    if note:
        for line in wrap(note[:100], font_small, 940):
            draw.text((70, y), line, fill='#94a3b8', font=font_small)
            y += 40

    y = max(y + 30, 700)
    enabled = UserPlan.objects.filter(user=request.user, is_enabled=True)
    if enabled:
        draw.text((70, y), '今日计划', fill='#6366f1', font=font_body)
        y += 50
        for plan in enabled:
            draw.text((85, y), f"  {plan.title}", fill='#94a3b8', font=font_small)
            y += 40

    draw.text((70, 1360), '来 Pattern，找到你的每日节奏', fill='#6366f1', font=font_small)

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return HttpResponse(buffer, content_type='image/png')
