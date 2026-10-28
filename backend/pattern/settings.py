"""
Django settings for pattern project.
"""
from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ===== 从 .env / 环境变量读取敏感配置（生产直接给环境变量，见 DEPLOY.md）=====
SECRET_KEY = config('SECRET_KEY')
# 默认 False：配置漏了就当生产跑，宁可静态文件 404 也不要带着 DEBUG=True 上线；
# 本地开发在 .env 里显式写 DEBUG=True
DEBUG = config('DEBUG', default=False, cast=bool)

# 逗号分隔。默认值只够本地/局域网联调，线上必须用环境变量写真实域名
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost,192.168.28.160', cast=Csv())

# ===== 应用注册 =====
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 第三方
    'allauth',
    'allauth.account',
    # 本地 app
    'users',
    'patterns',
    'plans',
    'quick',
    'tasks',   # #079：日常任务层（UserTask/UserTaskStep），靠 FK 引用 quick 模板
    'api',
]

# ===== 中间件 =====
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # allauth 必需
]

ROOT_URLCONF = 'pattern.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # 全局模板目录
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pattern.wsgi.application'

# ===== 数据库（PostgreSQL） =====
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# ===== 缓存（登录防爆破计数 / 密码重置 token 都放这里）=====
# 用数据库缓存，不用默认的 LocMemCache：后者每个进程一份，
# gunicorn 多 worker 下失败计数各算各的，真实阈值会被放大成 worker 数倍（限流形同虚设）。
# ⚠️ 部署时除了 migrate，还要跑一次：python manage.py createcachetable（建表，可重复执行）
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'pattern_cache',
    }
}

# ===== 自定义 User 模型 =====
AUTH_USER_MODEL = 'users.User'

# ===== django-allauth 配置 =====
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1
# --- django-allauth 配置（新版） ---
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = 'optional'   # 开发用 optional，上线改 mandatory
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# ===== 邮件配置（QQ邮箱） =====
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.qq.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

# ===== 密码验证 =====
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ===== 国际化 =====
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# ===== CSRF 配置（HTMX 需要 JS 读取 csrftoken Cookie） =====
CSRF_COOKIE_HTTPONLY = False

# ===== 静态文件 / 上传文件 =====
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'pattern' / 'static',
]
# collectstatic 的落点（部署时 nginx 直接托管这个目录）
STATIC_ROOT = BASE_DIR / 'staticfiles'

# 用户头像等上传文件（users 的资料页上传头像会用到；生产由 nginx 托管 MEDIA_ROOT）
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# #057：/media/ 下的用户上传文件一律带 nosniff，别让浏览器把伪装成图片的文件按 HTML 解析。
# Django 走 static() 守 media 时由 SecurityMiddleware 加这个头；生产是 nginx 直接托管，
# 必须在 nginx 的 location /media/ 里也加 add_header X-Content-Type-Options nosniff always;
SECURE_CONTENT_TYPE_NOSNIFF = True

# ===== 默认主键字段 =====
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===== 微信小程序登录 =====
# AppSecret 只从环境变量或本地 .env 读（python-decouple 会先看环境变量），不硬编码、不入库
WX_APPID = config('WX_APPID', default='wx2964cf2966258d88')
WX_APPSECRET = config('WX_APPSECRET', default='')
# 开发登录接口开关：默认跟随 DEBUG（本地自动开、上线自动关），要强制开就设 ENABLE_DEV_LOGIN=True
ENABLE_DEV_LOGIN = config('ENABLE_DEV_LOGIN', default=DEBUG, cast=bool)

# ===== UGC 开关（与小程序 xingdongmao/utils/config.js 的 ENABLE_UGC 语义一致）=====
# 现状（#029）：**网页端恢复 UGC，小程序端保持隐藏**（小程序主体还是个人主体，一恢复又会被驳回）。
# 分工：
#   · 入口：网页端由前端 `ENABLE_UGC = IS_H5 ? true : false` 打开；小程序端前端仍关着，
#     详情页作者也被前端固定显示「官方」，所以接口即使返回真实名，审核侧看到的还是「官方」。
#   · 分享图是后端画的、前端盖不住 → 默认仍画「官方」，只有网页版显式带 `?author=1` 才画真实名
#     （见 quick_share_card）。所以小程序侧完全不会露出用户昵称。
#   · 这个开关本身管的是"写接口放行"：True 时创建/导入/发布/编辑/删除/Fork 才可用（网页端要用）。
# #057（Jeff 决策 1A）：默认值改成 **False** —— "默认关，要开显式开"，漏配不会裸奔。
#   本地和服务器都靠 .env 里显式写 ENABLE_UGC=True 来开（两边都已写明）；
#   改完确认 POST /api/v1/quick/ 不是 403、网页端能创建/发布，小程序端入口仍然隐藏。
ENABLE_UGC = config('ENABLE_UGC', default=False, cast=bool)

# ===== 站点自身地址（邮件里的链接要用）=====
# 密码重置邮件里的链接必须指向用户真正打得开的地址；本地/测试环境用环境变量覆盖成 127.0.0.1:8000
SITE_URL = config('SITE_URL', default='https://xingdongmao.com').rstrip('/')

# ===== 生产 / HTTPS 相关 =====
# 全部默认关闭，本地 http 开发不受影响；部署时按 DEPLOY.md 逐项用环境变量打开
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)
# 跑在 nginx 反代后面时打开：让 Django 认 X-Forwarded-Proto，
# 否则 SECURE_SSL_REDIRECT 会把 https 请求也当 http 无限重定向
BEHIND_PROXY = config('BEHIND_PROXY', default=False, cast=bool)
if BEHIND_PROXY:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
