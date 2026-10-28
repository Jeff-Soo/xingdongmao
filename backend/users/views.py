from django.shortcuts import render, get_object_or_404, redirect
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from patterns.models import Pattern
from plans.models import DayExecution

User = get_user_model()

# #057⑤：头像上传白名单。以前 request.FILES['avatar'] 直接塞进 ImageField ——
# 什么类型都收、多大都收、文件名由用户决定（能塞 .html/.svg 到 /media/ 下）。
MAX_AVATAR_BYTES = 2 * 1024 * 1024          # 2MB
AVATAR_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
AVATAR_EXT = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}


def _clean_avatar(upload):
    """校验头像文件。返回 (错误信息, 新文件名) —— 错误为 None 表示通过。

    三重校验：content_type 白名单 → 大小上限 → 用 Pillow 真解一遍（后缀和声明都能伪造，
    只有真的能解码成图片才放行），文件名由服务端重命名，不用用户给的名字。
    """
    if upload.size is None or upload.size == 0:
        return '头像文件是空的', None
    if upload.size > MAX_AVATAR_BYTES:
        return f'头像不能超过 {MAX_AVATAR_BYTES // 1024 // 1024}MB', None
    if (upload.content_type or '').lower() not in AVATAR_TYPES:
        return '只支持 JPG / PNG / WebP / GIF 图片', None

    from PIL import Image as PILImage   # 头像才用到，别拖慢其它请求
    try:
        probe = PILImage.open(upload)
        probe.verify()                  # verify() 之后对象不可再用，所以再 open 一次拿 format
        upload.seek(0)
        fmt = (PILImage.open(upload).format or '').upper()
        upload.seek(0)
    except Exception:
        return '这个文件不是有效的图片', None

    if fmt not in AVATAR_EXT:
        return '只支持 JPG / PNG / WebP / GIF 图片', None
    return None, f'avatar.{AVATAR_EXT[fmt]}'


def user_profile(request, pk):
    profile_user = get_object_or_404(User, pk=pk)
    patterns = Pattern.objects.filter(author=profile_user, fork_from__isnull=True)
    # 执行统计
    total_executions = DayExecution.objects.filter(user=profile_user).count()
    avg_rate = DayExecution.objects.filter(user=profile_user).aggregate(
        avg=models.Avg('completion_rate')
    )['avg'] or 0
    return render(request, 'users/profile.html', {
        'profile_user': profile_user,
        'patterns': patterns,
        'total_executions': total_executions,
        'avg_rate': avg_rate,
    })

@login_required
def profile(request):
    """个人资料编辑页"""
    if request.method == 'POST':
        upload = request.FILES.get('avatar')
        if upload is not None:
            err, new_name = _clean_avatar(upload)
            if err:
                messages.error(request, err)
                return redirect('users:profile')
            # #057⑤：存进 storage 时由服务端决定文件名（同名会由 storage 自动加随机后缀，
            # 不会覆盖别人）；上传目录由 avatar 字段的 upload_to='avatars/' 决定。
            request.user.avatar.save(new_name, upload, save=False)
        request.user.interest_tags = request.POST.get('interest_tags', '')
        request.user.theme = request.POST.get('theme', 'warm')
        request.user.save()
        messages.success(request, '资料已更新')
        return redirect('users:profile')
    return render(request, 'users/profile_edit.html', {
        'themes': [
            ('🌾', 'warm', '#faf5ee', '暖陶'),
            ('🌿', 'mint', '#edf5f0', '薄绿'),
            ('🏔', 'frost', '#eef2f6', '霜灰'),
            ('🌙', 'night', '#0f0f1a', '暗夜'),
            ('⬜', 'pure-white', '#fafafa', '纯白'),
            ('⬛', 'pure-black', '#000000', '纯黑'),
        ],
    })
