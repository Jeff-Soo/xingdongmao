import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import Pattern, TimeBlock
from django.utils import timezone
from plans.models import UserPlan
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from PIL import Image, ImageDraw, ImageFont
import io

# 字体文件路径（PIL 需要本地文件路径，不是 Django static URL）
FONTS_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts')
FONT_REGULAR = os.path.join(FONTS_DIR, 'NotoSansSC-Regular.otf')
FONT_BOLD = os.path.join(FONTS_DIR, 'NotoSansSC-Bold.otf')

def pattern_list(request):
    patterns = Pattern.objects.all().prefetch_related('time_blocks')

    # 关键词搜索
    q = request.GET.get('q', '')
    if q:
        patterns = patterns.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(category__icontains=q)
        )

    # 难度筛选
    difficulty = request.GET.get('difficulty', '')
    if difficulty:
        patterns = patterns.filter(difficulty=difficulty)

    return render(request, 'patterns/list.html', {
        'patterns': patterns,
        'current_q': q,
        'current_difficulty': difficulty,
    })


@login_required
def create_pattern(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        difficulty = request.POST.get('difficulty', 'medium')
        category = request.POST.get('category', '').strip()
        if not title:
            messages.error(request, '模板名称不能为空')
            return redirect('patterns:create_pattern')

        pattern = Pattern.objects.create(
            title=title, description=description,
            difficulty=difficulty, category=category,
            author=request.user,
        )

        created_count = 0
        total = int(request.POST.get('total_blocks', '0'))
        for i in range(1, total + 1):
            action = request.POST.get(f'action_{i}', '').strip()
            if not action:
                continue
            is_floating = request.POST.get(f'floating_{i}') == 'on'
            floating_label = request.POST.get(f'floating_label_{i}', '').strip()
            start = request.POST.get(f'start_time_{i}', '').strip()
            end = request.POST.get(f'end_time_{i}', '').strip()

            TimeBlock.objects.create(
                pattern=pattern, order=i,
                start_time=start or ('00:00' if is_floating else '08:00'),
                end_time=end or ('00:00' if is_floating else '08:30'),
                action=action,
                is_floating=is_floating,
                floating_label=floating_label or action,
            )
            created_count += 1

        if created_count == 0:
            pattern.delete()
            messages.error(request, '请至少添加一个任务后再保存')
            return redirect('patterns:create_pattern')
        messages.success(request, f'模板「{title}」创建成功！（{created_count} 个任务）')
        return redirect('patterns:pattern_detail', pk=pattern.pk)

    categories = Pattern.objects.values_list('category', flat=True).distinct().exclude(category='').order_by('category')
    return render(request, 'patterns/create.html', {'existing_categories': categories})


def pattern_detail(request, pk):
    pattern = get_object_or_404(Pattern.objects.prefetch_related('time_blocks'), pk=pk)
    already_forked = False
    if request.user.is_authenticated:
        already_forked = UserPlan.objects.filter(user=request.user, pattern=pattern).exists()
    return render(request, 'patterns/detail.html', {
        'pattern': pattern,
        'already_forked': already_forked,
    })


def home(request):
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 6:
        greeting = '夜深了 🌙'
    elif hour < 12:
        greeting = '早上好 ☀️'
    elif hour < 14:
        greeting = '中午好 🍜'
    elif hour < 18:
        greeting = '下午好 🌤'
    else:
        greeting = '晚上好 🌙'

    today = timezone.localdate()
    today_plan = None
    if request.user.is_authenticated:
        today_plan = UserPlan.objects.filter(
            user=request.user, activated_date=today
        ).first()
    return render(request, 'home.html', {
        'today_plan': today_plan,
        'greeting': greeting,
    })


@login_required
def edit_pattern(request, pk):
    """编辑自己创建的模板的时间块"""
    pattern = get_object_or_404(Pattern, pk=pk, author=request.user)
    blocks = pattern.time_blocks.all()

    if request.method == 'POST':
        pattern.title = request.POST.get('title', pattern.title).strip() or pattern.title
        pattern.description = request.POST.get('description', '').strip()
        pattern.difficulty = request.POST.get('difficulty', pattern.difficulty)
        pattern.category = request.POST.get('category', '').strip()
        pattern.save()

        delete_pk = request.POST.get('delete_block')
        if delete_pk:
            TimeBlock.objects.filter(pk=delete_pk, pattern=pattern).delete()
            return redirect('patterns:edit_pattern', pk=pattern.pk)

        for block in blocks:
            start = request.POST.get(f'start_time_{block.pk}', '').strip()
            end = request.POST.get(f'end_time_{block.pk}', '').strip()
            action = request.POST.get(f'action_{block.pk}', '').strip()
            if action:
                block.start_time = start or None
                block.end_time = end or None
                block.action = action
                block.save()

        new_action = request.POST.get('new_action', '').strip()
        if new_action:
            TimeBlock.objects.create(
                pattern=pattern, order=blocks.count() + 1,
                start_time=request.POST.get('new_start_time') or '08:00',
                end_time=request.POST.get('new_end_time') or '08:30',
                action=new_action,
            )

        messages.success(request, '模板已更新')
        return redirect('patterns:edit_pattern', pk=pattern.pk)

    categories = Pattern.objects.values_list('category', flat=True).distinct().exclude(category='').order_by('category')
    return render(request, 'patterns/edit.html', {
        'pattern': pattern, 'blocks': blocks, 'existing_categories': categories,
    })


@login_required
def delete_pattern(request, pk):
    """删除自己创建的模板"""
    pattern = get_object_or_404(Pattern, pk=pk, author=request.user)
    if request.method == 'POST':
        title = pattern.title
        pattern.delete()
        messages.success(request, f'模板「{title}」已删除')
        return redirect('patterns:pattern_list')
    return redirect('patterns:pattern_detail', pk=pattern.pk)


def wrap_text(draw, text, font, max_width):
    """把文字按像素宽度自动换行，返回行列表。自动过滤 emoji"""
    import re
    # 过滤 emoji 和特殊符号（Pillow 默认字体不支持）
    text = re.sub(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2702-\u27B0\u24C2-\U0001F251\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u200d\uFE0F]', '', text)
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


@login_required
def share_card(request, pk):
    """生成模板分享卡片 PNG"""
    pattern = get_object_or_404(Pattern.objects.prefetch_related('time_blocks'), pk=pk)

    img = Image.new('RGB', (1080, 1440), color='#1e1b4b')
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype(FONT_BOLD, 68)
        font_body = ImageFont.truetype(FONT_REGULAR, 40)
        font_small = ImageFont.truetype(FONT_REGULAR, 32)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = font_title
        font_small = font_title

    max_w = 940  # 卡片可用宽度

    # 标题（自动换行）
    y = 80
    for line in wrap_text(draw, pattern.title, font_title, max_w):
        draw.text((70, y), line, fill='#ffffff', font=font_title)
        y += 80

    if pattern.description:
        y += 15
        desc_lines = wrap_text(draw, pattern.description[:120], font_body, max_w)
        for line in desc_lines[:3]:
            draw.text((70, y), line, fill='#c7d2fe', font=font_body)
            y += 48

    y = max(y + 30, 350)
    draw.text((70, y), '每日时间轴', fill='#a5b4fc', font=font_body)
    y += 70
    for block in pattern.time_blocks.all()[:10]:
        if y > 1250:
            draw.text((70, y), f'... 还有 {pattern.time_blocks.count() - 10} 个任务', fill='#6366f1', font=font_small)
            break
        if block.is_floating:
            label = block.floating_label or block.action
            text = f"  {label[:30]}"
        else:
            tm = block.start_time.strftime('%H:%M') if block.start_time else '--:--'
            text = f"{tm}  {block.action[:30]}"
        draw.text((85, y), text, fill='#e0e7ff', font=font_small)
        y += 50

    draw.text((70, 1330), '扫码 Fork 跟练', fill='#fbbf24', font=font_body)
    draw.text((70, 1390), 'Pattern App 找到属于你的每日节奏', fill='#6366f1', font=font_small)

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return HttpResponse(buffer, content_type='image/png')


def export_pattern(request, pk):
    """导出模板为纯文本"""
    pattern = get_object_or_404(Pattern.objects.prefetch_related('time_blocks'), pk=pk)

    lines = []
    lines.append(f"{'='*40}")
    lines.append(f"\U0001f4cb {pattern.title}")
    lines.append(f"{'='*40}")
    if pattern.description:
        lines.append(f"\n{pattern.description}")
    lines.append(f"\n难度：{pattern.get_difficulty_display()}")
    if pattern.category:
        lines.append(f"分类：{pattern.category}")
    if pattern.tags:
        lines.append(f"标签：{pattern.tags}")
    lines.append(f"\n{'─'*40}")
    lines.append("\U0001f4c5 时间轴")
    lines.append(f"{'─'*40}")

    for block in pattern.time_blocks.all():
        if block.is_floating:
            label = block.floating_label or block.action
            lines.append(f"\n\U0001f504 浮动: {label}")
        else:
            start = block.start_time.strftime('%H:%M') if block.start_time else '--:--'
            end = block.end_time.strftime('%H:%M') if block.end_time else '--:--'
            lines.append(f"\n{start} ─ {end}")
        lines.append(f"  {block.action}")
        if block.notes:
            lines.append(f"  \U0001f4dd {block.notes}")
        if block.alt_action:
            lines.append(f"  \u2615 轻松模式：{block.alt_action}")

    lines.append(f"\n{'='*40}")
    lines.append("由 Pattern App 生成")
    lines.append(f"{'='*40}")

    content = '\n'.join(lines)
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{pattern.title}.txt"'
    return response