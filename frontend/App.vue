<script>
	export default {
		onLaunch: function() {
			console.log('App Launch')
		},
		onShow: function() {
			console.log('App Show')
		},
		onHide: function() {
			console.log('App Hide')
		}
	}
</script>

<style>
	/* 主题变量统一放这里：页面里只用 var(--xxx)，不写死颜色 */
	page {
		--bg: #F7F5F2;
		--card: #FFFFFF;
		--accent: #E2703A;
		--accent-soft: rgba(226, 112, 58, 0.12);
		--muted: #8C8579;
		--text: #23201D;
		--border: #ECE7E0;
		background-color: var(--bg);
		color: var(--text);
		font-size: 28rpx;
		line-height: 1.5;
	}

	.theme-card {
		background-color: var(--card);
		border-radius: 24rpx;
	}

	.text-accent { color: var(--accent); }
	.text-muted { color: var(--muted); }

	.btn-accent {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 88rpx;
		border-radius: 24rpx;
		background-color: var(--accent);
		color: #FFFFFF;
		font-size: 32rpx;
		font-weight: 600;
	}

	.btn-ghost {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 88rpx;
		border-radius: 24rpx;
		border: 2rpx solid var(--border);
		color: var(--text);
		font-size: 30rpx;
	}

	.tag {
		padding: 4rpx 16rpx;
		border-radius: 999rpx;
		background-color: rgba(0, 0, 0, 0.05);
		color: var(--muted);
		font-size: 22rpx;
	}

	.tag-cat {
		background-color: var(--accent-soft);
		color: var(--accent);
	}

	/* ===== #059/#060：全站返回键（圆形 ‹）垂直/水平居中 —— **一处定义**，手机/平板/电脑共用 =====
	   ⚠️ 全站返回键统一用这两套 class，别另造：
	        · 普通页面：`.nav-btn`（外层圆）+ `.nav-btn-icon`（里面那个 ‹）—— detail/create/mine/login/forgot/reset
	        · 执行页顶栏：`.step-back` + `.step-back-icon`
	      #060 全站扫漏：这两套就是全部 8 个返回键，没有漏网的；以后新增页面请复用，
	      否则吃不到下面的补偿（新 class 不会自动生效）。

	   为什么放这里（#ifdef H5 之前）：小程序端同样偏，这条必须进 mp 的 app.wxss 才生效。

	   实测（390 与 1440 两档 × 7 个页面，像素级量"字形墨迹中心 vs 圆心"，见
	   specs/bug扫描报告.md 第十一/十二节）：
	     · 水平：字形中心比圆心左 0.7px → 盒子居中没问题（各页 .nav-btn 本来就是 flex 双向居中）
	     · 垂直：字形中心比圆心【下】4.3px → 这是字形在行盒里的位置问题，不是盒子问题
	   为什么不能用负 margin：#058 写的是 margin-top:-4px，但父级是 align-items:center 的 flex，
	   负 margin 先把 margin-box 压小、再被居中算法分掉一半 → 实测只上移了 2px（4.3 → 2.3），
	   所以"看着还是偏下"。transform 不参与居中计算，位移量 1:1。
	   备选写法（若某端不支持对 <text> 用 transform）：position:relative; top:-4px; left:1px。 */
	.nav-btn,
	.step-back {
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.nav-btn-icon,
	.step-back-icon {
		/* display:block —— transform 对"非替换行内元素"不生效，显式块级化保证两端（H5/mp）都吃这条补偿 */
		display: block;
		/* 行盒 = 字号：消掉 line-height 带来的上下不均 */
		line-height: 1;
		/* 字形视觉补偿：右移 1px、上移 4px。
		   实测原始偏移 (x -0.7px, y +4.3px)；取整像素补偿后残差 ≈ (x -0.3, y +0.3)，
		   都在半个像素内，而且字形仍落在像素网格上（分数偏移会把 ‹ 的抗锯齿擦糊：墨迹高度 13px → 11px）。 */
		transform: translate(1px, -4px);
	}

	/* ===== 网页版（H5）：双模式配色 + 全局基线（设计规范 §二/§六） ===== */
	/* #ifdef H5 */
	/* 配色只在变量定义处出现：深色为默认，浅色跟随系统。
	   --card 是各页面已经在用的名字，这里别名到 --surface，免得逐页改名；
	   --accent-text 是主按钮上的文字色（深色模式近黑、浅色模式用白）。 */
	page, :root {
		--bg: #0E0E10;
		--surface: #17171A;
		--surface-2: #1F1F23;
		--border: #26262B;
		--text: #F2F0ED;
		--text-2: #B8B5B0;
		--muted: #8A8783;
		--accent: #B8956A;
		--accent-soft: rgba(184, 149, 106, 0.15);
		--accent-text: #0E0E10;
		--card: #17171A;
		/* 状态色：成功（已发布/解析成功）与危险（删除/解析失败），深色下取偏亮的，保证对比度 */
		--success: #4EA87A;
		--danger: #E2725B;
		/* #036②：所有页面标题块统一高度。64px 太空（文字只占 1/3），收到 44px 后
		   文字能占到块高的 2/3 以上（配合下面的 .nav-title 行高）。 */
		--nav-h: 44px;
		/* 标题字号。按【实测像素】定的：把字形画到 canvas 上逐行扫 alpha，
		   Noto Sans SC 的中文墨迹高度 ≈0.95×字号。块 44px、字号 30px → 墨迹 ≈28.5px
		   = 块高的 ≈64%（#038 曾按 6/7 定到 40px/86%，实机觉得太满，按反馈改回 30px）。 */
		--nav-fs: 30px;
		--content-w: 1200px;
		--content-pad: 32px;
		/* 圆角三档（#035）：手机一档更小（8px，屏窄时大圆角显臃肿），
		   平板/电脑回到设计规范值（卡片 12px / 按钮 10px）。
		   各页面一律引用这三个变量，别再各写各的 px——"有的页面圆角大、有的小"就是这么来的。 */
		--r-card: 8px;   /* 卡片、导航浮卡、弹层、操作栏 */
		--r-btn: 8px;    /* 按钮、输入框、次级动作 */
		--r-chip: 6px;   /* 标签、分类/排序小控件 */
		/* 全屏图片预览的遮罩：两种模式都用深色（灯箱底不该跟主题变浅），浅色块不覆盖它 */
		--scrim: rgba(0, 0, 0, 0.92);
		/* #040 蒙层高亮的遮罩：比灯箱浅一档，否则高亮区外一片死黑、看不出页面在哪 */
		--scrim-tour: rgba(0, 0, 0, 0.62);
	}

	@media (prefers-color-scheme: light) {
		page, :root {
			--bg: #F7F5F2;
			--surface: #FFFFFF;
			--surface-2: #F1EEE9;
			--border: #E8E4DE;
			--text: #1A1A1A;
			--text-2: #4A4744;
			--muted: #8C8579;
			--accent: #A67C52;
			--accent-soft: rgba(166, 124, 82, 0.12);
			--accent-text: #FFFFFF;
			--card: #FFFFFF;
			--success: #2E8B57;
			--danger: #C0392B;
		}
	}

	@media (max-width: 767px) {
		page, :root {
			--content-pad: 20px;
		}
	}

	/* 平板/电脑：圆角回到设计规范值（#035 ②：手机 8px / 电脑 12px） */
	@media (min-width: 768px) {
		page, :root {
			--r-card: 12px;
			--r-btn: 10px;
		}
	}

	/* ===== #065：隐藏滚动条（只隐藏"视觉上的条"，滚动能力一点不动） =====
	   实测改前：列表滚动容器 `offsetWidth - clientWidth = 10px`（Windows 经典滚动条），
	   手机端也照样显示 → 挡视野。全站统一隐藏（首页/我的/详情/执行/弹层都吃到）。
	   真正的规则写在文件末尾「#065 隐藏滚动条」那段（放在最后才能压住后面那些旧样式）。 */

	/* #058⑫：大屏不再"内容太少占屏"。
	   1200px 在 1440/1920 屏上两侧各留 120/360px，看着空旷；分档放宽，
	   并且只放宽到"内容列"，正文块另有自己的易读宽度（见各页 max-width）。 */
	@media (min-width: 1440px) {
		page, :root {
			--content-w: 1440px;
			--nav-fs: 32px;
		}
	}
	@media (min-width: 1800px) {
		page, :root {
			--content-w: 1560px;
			--nav-fs: 34px;
		}
	}

	/* 平板/电脑：把 rpx 的换算基准钉在 16px（正好是 375 设计稿的 1:1）。
	   手机上 rpx 跟着屏宽走是对的（原生手感），但 768px 以上继续跟着放大就过头了：
	   876px 的平板上 96rpx 会被算成 112px，卡片图标/间距会被撑变形。
	   钉 16px 之后，全站 rpx 尺寸在平板和电脑上完全一致（28rpx=14px、96rpx=48px）。 */
	@media (min-width: 768px) {
		html {
			font-size: 16px !important;
		}
	}

	html, body {
		background-color: var(--bg);
		color: var(--text);
	}

	uni-page-body {
		background-color: var(--bg);
	}

	/* 卡片：微弱边框代替阴影，圆角走 --r-card（手机 8px / 电脑 12px，设计规范 §六③④ + #035） */
	.theme-card {
		background-color: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--r-card);
	}

	/* 按钮：主按钮圆角 --r-btn + 深色字；次按钮透明底 + 细边框 */
	.btn-accent {
		border-radius: var(--r-btn);
		background-color: var(--accent);
		color: var(--accent-text);
	}
	.btn-ghost {
		border-radius: var(--r-btn);
		border: 1px solid var(--border);
		background-color: transparent;
		color: var(--text);
	}

	/* 标签：--r-chip 圆角 + 次级面（设计规范 §4.2） */
	.tag {
		padding: 4px 10px;
		border-radius: var(--r-chip);
		background-color: var(--surface-2);
		color: var(--text-2);
		font-size: 12px;
	}
	.tag-cat {
		background-color: var(--accent-soft);
		color: var(--accent);
	}

	/* 导航/顶栏（#043 重做）：
	   **容器只负责"占位 + 避让刘海"，一律不画任何东西**；所有视觉（底色 / 细边框 / 两头全圆）
	   都收到内层胶囊 .nav-inner 上。

	   为什么要改：根因是各页基础样式里都有一句 `.nav { background-color: var(--card) }`，
	   它被 scoped 成 [data-v-x]，优先级比这里的全局 .nav 高 → 网页版一直是**容器自己**在铺底色：
	   · 平板/电脑：整条通栏都是卡片色（本该透明的留白也被染了）；
	   · 手机：容器就是那个胶囊，可它的 padding-top 是 max(12px, env(safe-area-inset-top))，
	     刘海机型上会变成 47px —— 那块被撑高的区域同样是实底色，
	     看起来就是"胶囊底下还带着一块背景"。
	   现在避让改用 margin（margin 不画东西），padding 归零，胶囊永远只有 --nav-h 那么高。 */
	.nav, .topbar {
		box-sizing: border-box;
		padding-top: 0 !important;
		padding-bottom: 0;
		background-color: transparent !important;
		/* 边框也要清掉，而且必须 !important：首页等页面自己的 scoped 规则里
		   还留着 `.nav { border-bottom: 1px solid var(--border) }`，优先级比全局高 */
		border: none !important;
	}
	/* 内层 = 胶囊本体。
	   #045：高度必须是"标题块 + 上下内边距"。#043 把背景从 .nav 挪到这一层时，
	   只搬了 height: var(--nav-h)（44px），漏掉了 .nav 上原来的 12px 上下内边距，
	   于是胶囊从 68px 悄悄塌成 44px —— 而标题的行盒正好是 44px，看着就"占满、拥挤"。
	   现在：胶囊 = 12 + 44 + 12 = 68px；里面那 44px 才是 --nav-h 定义的"标题块"，
	   文字墨迹占比仍按标题块算（29/44 ≈ 66%）。 */
	.nav-inner, .topbar-inner {
		box-sizing: border-box;
		height: calc(var(--nav-h) + 24px) !important;
		margin-top: 0 !important;
		padding: 12px 8px !important;
		max-width: var(--content-w);
		margin-left: auto !important;
		margin-right: auto !important;
		background-color: var(--card);
		border: 1px solid var(--border);
		border-radius: 999px;
	}

	/* #038①：标题字号统一并明显加大。上一版只把行盒撑到 30px，字号还是各页的 rpx
	   （手机≈21px），用户看到的墨迹高度只有块高的 ~1/2 ✗。
	   现在直接上字号变量：块 44px / 字号 30px → 中文墨迹 ≈29px ≈ 块高的 64%。
	   ⚠️ 必须 !important：各页 .nav-title 被 scoped 成 [data-v-x]，普通全局规则压不住他们。 */
	.nav-title {
		font-size: var(--nav-fs) !important;
		line-height: var(--nav-h) !important; /* 行盒 = 块高 → 文字在块内垂直居中 */
	}

	/* #043：导航容器透明了，原来的毛玻璃整块通栏已经没有意义（而且容器一模糊就是一层背景）。
	   胶囊自己有实底，滚动内容不会从它底下透出来。 */

	/* #032/#038/#043：手机上胶囊左右留 --content-pad，顶部用 margin 避让刘海（不画色）。
	   平板/电脑同样是"浮着的胶囊"，只是宽度对齐到 --content-w 内容列。 */
	@media (max-width: 767px) {
		.nav, .topbar {
			margin: max(12px, env(safe-area-inset-top)) var(--content-pad) 0;
		}
		/* 卡片和下面第一块内容之间留一口气，别贴死 */
		.body > .uni-scroll-view > .uni-scroll-view > .uni-scroll-view-content {
			padding-top: 12px;
		}
	}

	/* 平板/电脑：同样是"浮着的胶囊"，宽度对齐到 --content-w 内容列，并与第一块内容留 12px。
	   ⚠️ 必须显式 width: 100%：flex 列里一旦左右 margin 是 auto，子项就不再 stretch，
	   会缩成内容宽（实测只有 230px，胶囊会变成居中的小药丸）。 */
	@media (min-width: 768px) {
		.nav, .topbar {
			width: 100%;
			max-width: var(--content-w);
			margin: max(12px, env(safe-area-inset-top)) auto 12px;
		}
	}

	/* 返回按钮做成圆形（触控区仍是 44px，视觉是个圆）。
	   .step-back 是执行页顶栏的返回键，类名不同但要做成同一个样子。 */
	.nav-btn,
	.step-back {
		/* #045：加 border-box，让这枚圆键的外框正好 = --nav-h（44px，触控目标下限），
		   否则 44px + 上下 1px 边框 = 46px，比胶囊里的 44px 标题块还高、会顶到内边距里。 */
		box-sizing: border-box;
		width: var(--nav-h) !important;
		height: var(--nav-h) !important;
		border: 1px solid var(--border);
		border-radius: 50%;
		background-color: var(--surface-2);
		/* #058②：‹ 是文字字形，默认基线对齐会偏上、看着"没居中"。
		   容器改成 flex 居中，字形由行盒接管，圆键里就是一个正中的箭头。 */
		display: flex !important;
		align-items: center;
		justify-content: center;
		overflow: hidden;
	}
	.nav-btn-icon,
	.step-back-icon {
		/* #058②：字形本身再往上顶一点点（‹ 的字身在下半部分），并加大到 30px。
		   ⚠️ 各页 .nav-btn-icon 被 scoped 成 [data-v-x]，必须 !important 才压得住。
		   #059：居中补偿已统一挪到上面公共块的 transform（这里不再写 margin-top，
		   否则两处补偿叠加会过头）。 */
		font-size: 30px !important;
		line-height: 1 !important;
		font-weight: 500;
		color: var(--text);
	}
	/* 导航右侧那个纯占位按钮别跟着变圆底（它里面是空的） */
	.nav-btn-ghost {
		border-color: transparent;
		background-color: transparent;
	}

	/* #058②：桌面端把返回键做成可点得准的按钮（hover 反馈 + 手型光标）。
	   只在有真实指针的设备上生效，手机端不受影响。 */
	@media (hover: hover) {
		.nav-btn:not(.nav-btn-ghost),
		.step-back {
			cursor: pointer;
			transition: background-color 160ms ease, border-color 160ms ease;
		}
		.nav-btn:not(.nav-btn-ghost):hover,
		.step-back:hover {
			background-color: var(--accent-soft);
			border-color: var(--accent);
		}
	}

	/* 手机上用"动态视口高度"：地址栏收起/展开时 100vh 比可视高度大，底部内容会被切掉（#030 ④⑤）。
	   不支持的浏览器会忽略这行并退回各页原本的 100vh，属于优雅降级。 */
	.page {
		height: 100dvh !important;
	}

	/* ===== #058④：零散的小点击目标，电脑端统一抬到可点的尺寸 =====
	   清除 ✕ / 退出登录 / 弹层关闭 / 引导跳过 —— 这些以前只有字形那么大，
	   鼠标"往下一点点就点不到"。手机端不动（那边本来就够大且有 hover 反馈）。 */
	@media (min-width: 768px) {
		.search-clear,
		.tip-clear,
		.account-out,
		.sheet-close,
		.tip-skip {
			box-sizing: border-box;
			display: inline-flex !important;
			align-items: center;
			justify-content: center;
			min-width: 44px;
			min-height: 44px;
			padding: 0 10px !important;
		}
	}
	@media (hover: hover) {
		.search-clear,
		.tip-clear,
		.account-out,
		.sheet-close,
		.tip-skip {
			cursor: pointer;
		}
	}

	/* 页面级滚动区（各页的 .body）：限宽居中。
	   ⚠️ #030 ③：横向留白**不能放在容器上**。放在容器上时，uni 内部那个真正滚动的元素
	   右边缘会退到留白以内，滚动条就压在卡片上；改成容器通栏、内容自己留白，
	   滚动条才会落在屏幕右缘（手机上）/内容列右缘（电脑上）。 */
	.body {
		box-sizing: border-box;
		width: 100%;
		max-width: var(--content-w);
		margin: 0 auto;
	}

	/* 只命中页面级滚动区（.body 往下正好两层），
	   不会碰到里面的横向 scroll-view（首页分类行、创建页 emoji 行） */
	.body > .uni-scroll-view > .uni-scroll-view > .uni-scroll-view-content {
		box-sizing: border-box;
		padding-left: var(--content-pad);
		padding-right: var(--content-pad);
	}

	/* #030 ②：下拉刷新的背景/图标/文字都跟随主题。
	   页面上的 refresher-background 写死过浅色，这里用 !important 压掉它和它的行内样式；
	   图标是 uni 默认那套纯绿 SVG，也一并换成标志色。 */
	.uni-scroll-view-refresher {
		background-color: var(--bg) !important;
	}
	.uni-scroll-view-refresh-inner {
		color: var(--muted) !important;
	}
	.uni-scroll-view-refresh__icon path,
	.uni-scroll-view-refresh__spinner circle {
		fill: var(--accent) !important;
		stroke: var(--accent) !important;
	}

	/* #065：这里原来是"滚动条跟随深浅模式"的自定义样式（10px + 主题色）。
	   实测发现它把新加的隐藏规则压掉了 —— 原因有二：
	     · `::-webkit-scrollbar{width:10px}` 在后面，同选择器后写的赢；
	     · `html,body,.body,.uni-scroll-view…{scrollbar-width:thin}` 比 `*` 更具体，
	       而且只要设了标准属性 `scrollbar-width`，Chromium 就【忽略】`::-webkit-scrollbar`。
	   现在统一改成隐藏（保留滚动能力），并把自定义配色留给"以后想显式打开"时用：
	   想恢复"细条 + 跟随主题"，把下面 @media 里的注释解开、并删掉上面那条 `*{scrollbar-width:none}` 即可。 */
	* {
		/* !important：页面级还有 `[data-v-x]::-webkit-scrollbar{width:6px}`（创建页弹层），
		   只有这样才能保证全站统一"看不到条" */
		scrollbar-width: none !important;
		-ms-overflow-style: none !important;
	}
	::-webkit-scrollbar {
		width: 0 !important;
		height: 0 !important;
		display: none !important;
	}
	/* —— 以下为"想显式开启滚动条"时的配色（#065 起默认关闭，需要时把整段注释解开）
	@media (min-width: 768px) {
		::-webkit-scrollbar { width: 10px; height: 10px; }
		::-webkit-scrollbar-track { background: var(--bg); }
		::-webkit-scrollbar-thumb { background: var(--border); border-radius: 5px; }
		::-webkit-scrollbar-thumb:hover { background: var(--muted); }
		html, body, .body, .uni-scroll-view, uni-scroll-view, .cats {
			scrollbar-width: thin;
			scrollbar-color: var(--border) var(--bg);
		}
	}
	*/

	/* #044：那个"方形纯背景色"就是**卡片被滚出上边界时被切平的顶边**——
	   卡片自己有 --r-card 圆角，可一旦它的顶边滚到滚动区上沿之外，切口就是一条直角线，
	   紧贴着上面的胶囊，看着就是"一个方形的纯色块"。
	   修法：把滚动区收成跟卡片同宽（左右各留 --content-pad）+ 同一个圆角，并真正裁剪内容
	   → 卡片被切时切出来的就是这段圆角，跟卡片自己的圆角对得上。
	   ⚠️ ①必须放在文件最后：上面那句 `.body {... margin: 0 auto }` 是简写，写在它前面会被重置。
	   ⚠️ ②只做手机：窄屏是悬浮滚动条，收窄不会把滚动条压到卡片上；
	      平板/电脑的滚动条占位，收窄会压住卡片（#030 ③ 踩过），那里保持原样。 */
	@media (max-width: 767px) {
		.body {
			box-sizing: border-box;
			width: auto; /* 压掉基类的 width: 100%，否则加了左 margin 会整体右移、右边溢出 */
			margin-left: var(--content-pad);
			margin-right: var(--content-pad);
			border-radius: var(--r-card);
			overflow: hidden;
		}
		.body > .uni-scroll-view > .uni-scroll-view > .uni-scroll-view-content {
			padding-left: 0;
			padding-right: 0;
		}
	}
	/* #endif */
</style>