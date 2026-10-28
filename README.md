# 行动锚 · XingDongMao

> 一个把「想做」变成「在做」的每日计划工具。
> 模板不是货架，是弹药；主页不是目录，是今天。

在线站点：https://xingdongmao.com （H5，挂在 `/app/` 下）

---

## 这是什么

大多数人不是不知道该做什么，而是「知道，但没做」。行动锚把注意力从「收藏了多少模板」挪到「今天做没做」，围绕这一件事设计：

- **今天主页**：打开就看到今天要做的事，一条进度条告诉我们今天走到了哪，做完了会替你收工。
- **模板库**：生活类与职业类 SOP 模板（传菜、托盘、开店、家务、健身……），点一下就能变成今天的任务。模板是弹药，不是收藏品。
- **任务系统**：一条任务可以是「一次」「配额」（例如一周两次）或「习惯」；带步骤、时段（上午/下午/夜晚）、排期。
- **时间轴日程**：日 / 周 / 月 / 季四档视图。手机上用手指滑、电脑上用鼠标拖、用滚轮滚，三种方式都行。
- **搜索**：模糊搜索模板，多选合并成一条任务后直接加入今天。
- **分享卡**：服务端 Pillow 渲染的模板分享图，中文字体随仓库附带，新克隆的环境也能直接出图。

> 版本说明：本仓库是 2026-10-22 的代码快照。

## 目录结构

```
backend/     Django 后端（REST API + 管理后台 + 分享图渲染）
  api/       序列化、视图聚合、分享图
  quick/     模板库（QuickPattern / QuickStep）
  tasks/     任务（UserTask / UserTaskStep / TaskDay）
  plans/     早期日程模型（网页版沿用）
  users/     账号（allauth + 微信登录占位）
  pattern/   Django 工程配置（settings / urls / wsgi）
  static/    图标与中文字体（分享图依赖，故意入库）

frontend/    uni-app 前端（一套代码，H5 + 微信小程序）
  pages/     index（今天）/ library（模板库）/ tasks / schedule / search
             / execute / create / detail / login / mine
  components/ task-sheet / step-sheet / share-sheet / app-icon / 引导
```

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Django 6.0.6 + django-allauth + PostgreSQL（psycopg2），Pillow 渲染分享图 |
| 前端 | uni-app（Vue 3 语法），H5 与微信小程序共用一套页面 |
| 部署 | nginx + gunicorn，systemd 托管 |

## 本地跑起来

### 后端

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # 按需改数据库连接
python manage.py migrate
python manage.py runserver
```

需要本机有 PostgreSQL。数据库连接、密钥、邮件等全部通过 `.env` 注入（见 `.env.example`），**仓库里不含任何密钥**。

### 前端

用 HBuilderX 打开 `frontend/` 直接运行到浏览器（H5）或微信开发者工具（小程序）。

H5 的挂载前缀由 `frontend/manifest.json` 里的 `h5.router.base` 决定，部署时须与网关路径保持一致。

## 环境变量

见 `backend/.env.example`，全部由 `python-decouple` 读取。缺失的关键项（`SECRET_KEY`、数据库）会导致启动失败，这是有意为之。

## 说明

- 这是一个个人项目，代码在 AI 辅助下完成，仍在持续迭代。
- 仓库为 2026-10-22 的快照，功能以该时点为准。
- 未附带开源许可证：代码公开用于阅读与学习，保留所有权利。
