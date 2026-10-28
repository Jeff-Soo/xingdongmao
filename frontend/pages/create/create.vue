<template>
	<view class="page">
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">{{ isEdit ? '编辑模板' : '创建模板' }}</text>
				<view class="nav-btn nav-btn-ghost"></view>
			</view>
		</view>

		<scroll-view class="body" scroll-y :scroll-y="!dragging">
			<!-- ===== 基本信息 ===== -->
			<view class="block theme-card">
				<text class="block-title">基本信息</text>

				<view class="field">
					<text class="label">标题 <text class="req">*</text></text>
					<input class="input" v-model="form.title" :maxlength="40" placeholder="如：出门前 5 分钟检查清单" placeholder-class="ph" />
				</view>

				<view class="field">
					<text class="label">一句话效果</text>
					<input class="input" v-model="form.tagline" :maxlength="60" placeholder="如：出门前扫一遍，回头拿钥匙最烦" placeholder-class="ph" />
				</view>

				<view class="field">
					<text class="label">什么时候用</text>
					<textarea class="textarea" v-model="form.description" :maxlength="300" placeholder="描述一下适用场景（可留空）" placeholder-class="ph" />
				</view>

				<view class="field">
					<text class="label">分类</text>
					<picker mode="selector" :range="categoryLabels" :value="categoryIndex" @change="onCategoryChange">
						<view class="picker">
							<text class="picker-text">{{ currentCategoryLabel }}</text>
							<text class="picker-arrow">▾</text>
						</view>
					</picker>
				</view>

				<view class="field">
					<text class="label">图标</text>
					<!-- #073：图标选择器从 emoji 换成矢量图标（同一套 slug 存进 icon_key），
					     换行平铺而不是横向滚动 —— 一眼看全，也不用担心滚不到最后一个 -->
					<view class="icon-grid">
						<view
							v-for="k in PICKER_ICONS"
							:key="k"
							class="icon-cell"
							:class="{ 'icon-cell-on': form.iconKey === k }"
							hover-class="hover-dim"
							@click="form.iconKey = form.iconKey === k ? '' : k"
						>
							<app-icon :name="k" :size="22" :tone="form.iconKey === k ? 'accent' : 'muted'" />
						</view>
					</view>
				</view>
			</view>

			<!-- ===== 步骤 ===== -->
			<view class="block theme-card">
				<view class="block-head">
					<text class="block-title">步骤（{{ steps.length }}）</text>
					<view class="import-btn" hover-class="hover-dim" @click="openImport"><text>从文本导入</text></view>
				</view>

				<text v-if="!steps.length" class="steps-empty">还没有步骤。点「+ 添加步骤」自己写，或者「从文本导入」把整段贴进来。没步骤只能存草稿，发不出去。</text>

				<view
					v-for="(s, i) in steps"
					:key="s.key"
					class="step"
					:class="{ 'step-drag': dragging && dragIndex === i }"
					:style="stepStyle(i)"
				>
					<view class="step-head" @click="toggleStep(i)">
						<!-- #076 拖拽手柄（≡ 三条杠）：按住就能拖，鼠标/手指两端都走同一套逻辑；
						     H5 上还能聚焦后用 ↑/↓ 精确移动（键盘/无障碍的退路，所以没把上移下移当按钮留着） -->
						<view
							class="step-handle"
							hover-class="hover-dim"
							:tabindex="isH5 ? 0 : -1"
							:aria-label="'拖动排序：第 ' + (i + 1) + ' 步'"
							@touchstart.stop.prevent="onDragStart($event, i, 'touch')"
							@touchmove.stop.prevent="onDragMove($event)"
							@touchend.stop="onDragEnd()"
							@touchcancel.stop="onDragEnd()"
							@mousedown.stop.prevent="onDragStart($event, i, 'mouse')"
							@keydown="onHandleKey($event, i)"
							@click.stop="onHandleClick"
						>
							<app-icon name="drag-handle" :size="18" tone="muted" />
						</view>
						<text class="step-order">{{ i + 1 }}</text>
						<view class="step-head-main">
							<text class="step-title">{{ s.title || '（未填动作）' }}</text>
							<text class="step-sub">{{ stepSummary(s) }}</text>
						</view>
						<!-- #075：删除键只留这一个（原来工具行里还有一个「删除这一步」，重复）；
						     手机上原来靠工具行那个，现在这个对手机也显示 -->
						<view class="step-del" hover-class="hover-dim" @click.stop="removeStep(i)"><text>删除</text></view>
						<text class="step-caret">{{ openIndex === i ? '▾' : '▸' }}</text>
					</view>

					<view v-if="openIndex === i" class="step-body">
						<view class="field">
							<text class="label">动作（短）<text class="req">*</text></text>
							<input class="input" v-model="s.title" :maxlength="40" placeholder="如：检查钥匙在不在" placeholder-class="ph" />
						</view>
						<view class="field">
							<text class="label">画面文字（执行时卡片上显示）</text>
							<textarea class="textarea" v-model="s.instruction" :maxlength="300" placeholder="如：摸一下外套右侧口袋，确认钥匙在里面" placeholder-class="ph" />
						</view>
						<view class="field">
							<text class="label">为什么这么做（可选，执行页可展开）</text>
							<textarea class="textarea" v-model="s.explain" :maxlength="300" placeholder="如：钥匙最常忘，动手摸一下比凭记忆可靠" placeholder-class="ph" />
						</view>
						<view class="field">
							<text class="label">时长（秒，0 = 不计时）</text>
							<input class="input input-small" type="number" v-model="s.duration" placeholder="0" placeholder-class="ph" />
							<view class="dur-row">
								<view
									v-for="d in DURATIONS"
									:key="d"
									class="dur"
									:class="{ 'dur-on': Number(s.duration) === d }"
									@click="s.duration = String(d)"
								>
									<text class="dur-text">{{ d ? d + '秒' : '不计时' }}</text>
								</view>
							</view>
						</view>
					</view>
				</view>

				<view class="add-step" hover-class="hover-dim" @click="addStep"><text>+ 添加步骤</text></view>
			</view>

			<view class="bar-space"></view>
		</scroll-view>

		<!-- ===== 底部操作 ===== -->
		<view class="action-bar">
			<view v-if="!isEdit" class="btn-ghost act act-side" hover-class="hover-dim" @click="submit('draft')">
				<text>{{ saving ? '提交中…' : '保存草稿' }}</text>
			</view>
			<view
				class="btn-accent act act-main"
				:class="{ 'act-off': !isEdit && !steps.length }"
				hover-class="hover-dim"
				@click="onMainTap"
			>
				<text>{{ submitText }}</text>
			</view>
		</view>

		<!-- ===== 用 AI 生成步骤（#032 ③ / #033 ②③ 重排）===== -->
		<view v-if="importVisible" class="mask" @click="closeImport">
			<view class="sheet" @click.stop>
				<view class="sheet-head">
					<text class="sheet-title">用 AI 生成步骤</text>
					<text class="sheet-close" hover-class="hover-dim" @click="closeImport">✕</text>
				</view>

				<!-- 下部（#037 重排）：粘贴框 → 标题 → AI 提示词（复制 + 全文）→ 结果预览。
				     这一整块自己滚动（#033 ②）；提示词挪到标题下面，改标题/主题时提示词就在视线里。 -->
				<view class="sheet-body">
					<textarea
						class="sheet-input"
						v-model="importText"
						:maxlength="4000"
						placeholder="动作 | 时长 | 画面文字 | 为什么"
						placeholder-class="ph"
					/>

					<!-- 标题只留这一个输入框（#033 ③，合并了原来的「主题」）：
					     既是提示词里的主题，也是"生成草稿"用的模板标题 -->
					<view class="sheet-field">
						<text class="sheet-field-label">标题</text>
						<input
							class="input sheet-field-input"
							v-model="importTitle"
							:maxlength="40"
							placeholder="如：出门前 5 分钟检查"
							placeholder-class="ph"
						/>
						<text class="sheet-field-tip">填了会写进提示词的主题；生成草稿就用它当标题</text>
					</view>

					<!-- #037：AI 提示词区（含复制按钮 + 提示词全文），就放在标题下面 -->
					<view class="sheet-prompt">
						<view class="sheet-prompt-head">
							<text class="sheet-prompt-label">AI 提示词（跟着上面的标题走）</text>
							<view class="copy-btn btn-accent" hover-class="hover-dim" @click="copyAiPrompt">
								<text>复制 AI 提示词</text>
							</view>
						</view>
						<text class="sheet-prompt-text">{{ aiPromptText }}</text>
						<text class="sheet-hint">把提示词发给 AI（ChatGPT / DeepSeek / 豆包…），再把结果整段粘到上面的框里</text>
					</view>

					<view v-if="importParsed" class="sheet-result">
						<text class="result-line">
							识别到 {{ importPreview.length }} 步<text v-if="importSkipped.length">，跳过 {{ importSkipped.length }} 行</text>
						</text>
						<view v-for="w in importSkipped" :key="'w' + w.line" class="warn-line">
							<text class="warn-text">第 {{ w.line }} 行：{{ w.reason }}</text>
						</view>
						<view v-for="(p, i) in importPreview" :key="'p' + i" class="preview-line">
							<text class="preview-idx">{{ i + 1 }}</text>
							<view class="preview-main">
								<text class="preview-title">{{ p.title }}</text>
								<text class="preview-sub">{{ p.duration_seconds > 0 ? p.duration_seconds + ' 秒' : '不计时' }}{{ p.instruction ? ' · ' + p.instruction : '' }}</text>
								<text v-if="p.explain" class="preview-explain">为什么：{{ p.explain }}</text>
							</view>
						</view>
						<text v-if="importPreview.length" class="sheet-note">「为什么」也会一起存下来，生成后仍可在步骤里逐条改</text>
					</view>
				</view>

				<!-- 底部操作（#033 ②）：固定在弹层最下方，不随上面的内容滚走，也不会被压扁 -->
				<view class="sheet-actions">
					<view class="sheet-act btn-ghost" hover-class="hover-dim" @click="parseImport"><text>解析</text></view>
					<view
						class="sheet-act btn-ghost"
						:class="{ 'sheet-act-off': !importPreview.length }"
						hover-class="hover-dim"
						@click="fillSteps"
					>
						<text>填到步骤</text>
					</view>
					<view
						class="sheet-act btn-accent"
						:class="{ 'sheet-act-off': !importPreview.length }"
						hover-class="hover-dim"
						@click="createFromImport"
					>
						<text>生成草稿</text>
					</view>
				</view>
			</view>
		</view>

		<!-- #041 创建页引导（复用 #040 的蒙层高亮；H5 专属，组件内部自判 IS_H5） -->
		<!-- #057⑮：模板 + import + 注册三处一起加编译期条件，小程序端不再打这份 DOM 死代码 -->
		<!-- #ifdef H5 -->
		<onboarding-tour
			:visible="createTourVisible"
			:steps="createSteps"
			mark-key="onboarding_create_v1"
			@done="onCreateTourDone"
		/>
		<!-- #endif -->
	</view>
</template>

<script>
	import { get, post, request } from '@/api/request.js'
	import { ensureLogin } from '@/utils/token.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { toStepList, SOURCE_QUICK } from '@/utils/adapter.js'
	import { IS_H5 } from '@/utils/config.js'
	// #ifdef H5
	import OnboardingTour from '@/components/onboarding-tour/onboarding-tour.vue'
	// #endif
	import { isCreateDone, markCreateDone } from '@/utils/onboarding.js'
	// #073：图标选择器改成矢量图标（共享同一套 slug 与渲染组件）
	import { PICKER_ICONS } from '@/utils/icons.js'
	import AppIcon from '@/components/app-icon/app-icon.vue'

	// 必须和后端 QuickPattern.CATEGORY_CHOICES 一致：提交 key，显示 label
	const CATEGORIES = [
		{ key: 'life_out', label: '出行准备' },
		{ key: 'life_home', label: '居家事务' },
		{ key: 'life_daily', label: '日常事务' },
		{ key: 'work_service', label: '服务行业' },
		{ key: 'work_office', label: '职场办公' },
		{ key: 'work_safety', label: '安全操作' },
		{ key: 'other', label: '其他' }
	]

	const DURATIONS = [0, 30, 60, 300, 600]

	// 步骤在表单里带一个本地 key（列表渲染/展开/排序都用它，不用数组下标做 key）
	let stepSeq = 0
	function makeStep(step) {
		const s = step || {}
		return {
			key: 's' + ++stepSeq,
			title: s.title || '',
			instruction: s.instruction || '',
			explain: s.explain || '',
			duration: String(s.duration_seconds || 0)
		}
	}

	export default {
		// #ifdef H5
		components: { OnboardingTour, AppIcon },
		// #endif
		// #ifndef H5
		components: { AppIcon },
		// #endif
		data() {
			return {
				statusBarHeight: 20,
				nav: {},
				id: '',
				// #076：H5 才给手柄 tabindex（键盘 ↑/↓ 排序）；小程序没有键盘
				isH5: IS_H5,
				PICKER_ICONS,
				DURATIONS,
				categoryLabels: CATEGORIES.map((c) => c.label),
				categoryIndex: CATEGORIES.length - 1,
				// #073：图标默认留空（不预设第一个），提交时为空就不传 icon_key，
				// 前端列表会回退成默认的矢量图标 —— 不用再靠 emoji 兜底
				form: { title: '', tagline: '', description: '', icon: '', iconKey: '' },
				steps: [],
				openIndex: -1,
				// #076 拖拽排序的临时状态：dragging=正在拖；dragIndex=拖谁；dragOver=会落到哪；
				// dragDy=跟手的位移；dragH=被拖卡片的高度（用来给别的卡片让位）；cardRects=拖拽开始时量到的各卡片位置
				dragging: false,
				dragIndex: -1,
				dragOver: -1,
				dragDy: 0,
				dragH: 0,
				dragStartY: 0,
				cardRects: [],
				// 手机浏览器 touch 之后会补一发 mousedown，用它做去重的时间戳
				lastTouchAt: 0,
				// 拖完之后的这一小段时间内忽略 click（否则冒泡到步头会把卡片展开）
				suppressClickUntil: 0,
				loading: false,
				saving: false,
				status: '',
				// #041 创建页引导（复用 #040 的蒙层高亮组件）：只对"第一次创建"的人弹，
				// 标记 onboarding_create_v1 独立于 #040 的两个
				createTourVisible: false,
				// #042：pierce 决定这一步能不能"点穿"（挖空区放行点击）：
				//   stay = 可以操作（聚焦输入框），推进仍靠"下一步"
				//   end  = 点开弹层类（"从文本导入"会弹 sheet）→ 引导先收场，不跟弹层打架
				//   next = 点了就算完成这一步（"＋ 添加步骤"无害，点完直接进下一步）
				//   不写 = 只演示（"发布"是真动作，绝不让点穿，防止误触发）
				createSteps: [
					{ sel: '.block .field .input', text: '你脑子里那套流程，先给它起个名字——别人一看就懂那种', pierce: 'stay' },
					{
						sel: '.import-btn',
						text: '懒得一条条写？把整段过程粘进来，它自己拆成步骤（AI 也能帮你写）',
						pierce: 'end'
					},
					{ sel: '.add-step', text: '想自己写也行，一步一步加，加几条都随你', pierce: 'next' },
					{ sel: '.action-bar .act-main', text: '填完就能发；还没想好也行，先存草稿，回头接着写' }
				],
				// 导入弹层（#032 改成"AI 提示词"模式；#033 ③ 合并成一个「标题」输入）
				importVisible: false,
				// 标题：填了就写进提示词的主题，也是生成草稿用的标题；不填则提示词留占位
				importTitle: '',
				importText: '',
				importParsed: false,
				importPreview: [],
				importSkipped: []
			}
		},
		computed: {
			isEdit() {
				return !!this.id
			},

			// 一键复制的「AI 提示词」（#032 ③）。
			// 标题没填也给一段能直接用的文本：留一句人话占位，用户跟 AI 说主题即可。
			aiPromptText() {
				const theme = (this.importTitle || '').trim() || '（把这里换成你的主题，例如：出门前 5 分钟检查）'
				return [
					'你是一个 SOP 生成助手。请为【' + theme + '】生成一份分步操作流程。',
					'',
					'严格按下面格式输出，一行一步，四个字段用 | 分隔：',
					'',
					'动作 | 时长 | 画面文字 | 为什么',
					'',
					'字段说明：',
					'- 动作：这一步做什么，短语，不超过 12 字',
					'- 时长：整数秒数（如 60）；不需要计时的步骤写 0',
					'- 画面文字：执行时手机上显示的详细动作说明',
					'- 为什么：这一步的原理或原因（一句话）',
					'',
					'要求：',
					'- 每行 4 段，用英文竖线 | 分隔',
					'- 不要写序号、不要写额外解释、不要空行',
					'- 步骤 3 到 20 步：正常流程完整输出；超过 20 步就拆成 2-3 个模板分别生成（如"拆装"→"清洁"→"复位"），不要为了压步数而合并动作',
					'',
					'示例：',
					'检查钥匙 | 30 | 摸一下外套右侧口袋，确认钥匙带了 | 钥匙最常忘，动手摸比凭记忆可靠'
				].join('\n')
			},
			currentCategoryLabel() {
				return this.categoryLabels[this.categoryIndex] || '其他'
			},
			categoryKey() {
				const c = CATEGORIES[this.categoryIndex] || CATEGORIES[CATEGORIES.length - 1]
				return c.key
			},
			submitText() {
				if (this.saving) return '提交中…'
				if (this.isEdit) return '保存'
				// #058⑦：0 步时按钮直接说清为什么不能发布（以前按钮只是变淡，
				// 用户点了只看到一句话的 toast，容易理解成"保存坏了"）
				if (!this.steps.length) return '至少加 1 步'
				return '发布'
			}
		},
		// #041：首次进创建页教怎么创建。编辑已有模板（带 id）不弹——那不是"创建"。
		// 放 onReady：DOM 渲染好了蒙层才量得到目标位置
		onReady() {
			if (!IS_H5 || this.isEdit) return
			if (!isCreateDone()) this.createTourVisible = true
		},
		onLoad(options) {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
			this.id = (options && options.id) || ''
			if (this.id) this.loadForEdit()
		},
		onUnload() {
			// #076：拖到一半就离开页面时，把挂在 window 上的鼠标监听摘掉
			// #ifdef H5
			if (typeof window !== 'undefined') {
				if (this.onWinMove) window.removeEventListener('mousemove', this.onWinMove)
				if (this.onWinUp) window.removeEventListener('mouseup', this.onWinUp)
			}
			// #endif
			this.onWinMove = null
			this.onWinUp = null
			this.dragging = false
		},
		methods: {
			// #041：引导走完/跳过都收场（标记组件自己也会写，这里再兜一层）
			onCreateTourDone() {
				this.createTourVisible = false
				markCreateDone()
			},
			// ===== 编辑模式：预填 =====
			async loadForEdit() {
				this.loading = true
				try {
					// 自己的草稿只有作者能看，详情接口要靠 token 认人，所以先静默登录
					await ensureLogin()
					const d = await get('/quick/' + this.id + '/', null, { silent: true })
					this.form.title = d.title || ''
					this.form.tagline = d.tagline || ''
					this.form.description = d.description || ''
					this.form.icon = d.icon || ''
					// #073：编辑时优先回填矢量图标 slug（老数据没有就留空，展示走 emoji 回退）
					this.form.iconKey = d.icon_key || ''
					this.status = d.status || ''
					const idx = CATEGORIES.findIndex((c) => c.key === d.category_key)
					this.categoryIndex = idx >= 0 ? idx : CATEGORIES.length - 1
					this.steps = toStepList(d.steps, SOURCE_QUICK).map(makeStep)
				} catch (e) {
					uni.showToast({ title: (e && e.data && e.data.error) || '加载失败', icon: 'none' })
				} finally {
					this.loading = false
				}
			},

			// ===== 步骤编辑 =====
			addStep() {
				this.steps.push(makeStep())
				this.openIndex = this.steps.length - 1
			},
			removeStep(i) {
				this.steps.splice(i, 1)
				if (this.openIndex === i) this.openIndex = -1
				else if (this.openIndex > i) this.openIndex -= 1
				// #058⑦：删完必须给反馈 —— 以前静默删掉，用户不知道点没点中，
				// 删光了也不知道下一步该干什么（"首次用户直接卡死"就是这个）
				if (!this.steps.length) {
					uni.showToast({ title: '步骤删光了，这样只能存草稿', icon: 'none' })
				} else {
					uni.showToast({ title: '删掉一步，还剩 ' + this.steps.length + ' 步', icon: 'none' })
				}
			},
			// #076：键盘/无障碍的精确移动（H5 手柄聚焦后按 ↑/↓ 走这里）；
			// 视觉上的主要方式是拖拽，两个都落到同一个 reorder()
			moveStep(i, delta) {
				const j = i + delta
				if (j < 0 || j >= this.steps.length) return
				this.reorder(i, j)
			},

			/** 把第 from 步挪到第 to 位（拖拽松手 / 键盘移动共用） */
			reorder(from, to) {
				if (from === to || from < 0 || to < 0) return
				const moved = this.steps.splice(from, 1)[0]
				this.steps.splice(to, 0, moved)
				// 展开中的那一步要跟着走，否则用户会看到别的步骤突然展开
				if (this.openIndex === from) this.openIndex = to
				else if (from < this.openIndex && this.openIndex <= to) this.openIndex -= 1
				else if (to <= this.openIndex && this.openIndex < from) this.openIndex += 1
			},

			// ===== #076 拖拽排序 =====
			// 两端同一套逻辑：手柄上的 touchstart/touchmove/touchend（手机 + 小程序）
			// 加上 H5 桌面端的 mousedown + window 上的 mousemove/mouseup（鼠标拖出卡片也要收到事件）。
			// 位移用 inline transform 跟手；目标位置靠"被拖卡片中心落在哪个槽位的中心之外"来判定；
			// 其余卡片按 -h/+h 平移让位（h = 被拖卡片高度），松手才真正改数组顺序。

			pointerY(e) {
				// uni-app H5 会把鼠标事件也补上 touches（跨端统一），所以三种取法都试一遍
				const t = (e.touches && e.touches.length && e.touches[0]) ||
					(e.changedTouches && e.changedTouches.length && e.changedTouches[0]) || null
				if (t && typeof t.clientY === 'number') return t.clientY
				return e.clientY || 0
			},
			/** 量所有步骤卡的位置（拖拽开始时量一次；拖拽期间页面不滚动）
			 *  H5 直接用 DOM 量：实测 uni.createSelectorQuery 在这个宿主里会抛
			 *  "not a function"，一抛 await 后面的代码（挂鼠标监听）就再也执行不到，
			 *  表现就是"卡片浮起来了但怎么拖都不动、松手也不落位"。小程序端没有 DOM，走 uni 的查询。 */
			measureCards() {
				// #ifdef H5
				try {
					const nodes = document.querySelectorAll('.step')
					const rects = []
					for (let k = 0; k < nodes.length; k++) {
						const r = nodes[k].getBoundingClientRect()
						rects.push({ top: r.top, height: r.height })
					}
					if (rects.length) {
						this.cardRects = rects
						return Promise.resolve()
					}
				} catch (e) {
					// 落到下面的 uni 查询兜底
				}
				// #endif
				return new Promise((resolve) => {
					try {
						uni.createSelectorQuery()
							.selectAll('.step')
							.boundingClientRect((rects) => {
								this.cardRects = rects || []
								resolve()
							})
							.exec()
					} catch (e) {
						// 量不到就退化成"不排序"，但绝不能让拖拽状态卡住
						this.cardRects = []
						resolve()
					}
				})
			},
			async onDragStart(e, i, kind) {
				// 只有一步时没什么可排的，不进入拖拽态（否则点击会被吃掉）
				if (this.steps.length < 2) return
				// ⚠️ 不能用 "有没有 e.touches" 判断输入方式：uni-app H5 会给鼠标事件也补上 touches，
				// 那样鼠标拖拽会被误判成触摸，从而不挂 window 监听 → 卡片浮起来却怎么拖都不动。
				// 所以由模板显式传 'touch' / 'mouse'。
				const isTouch = kind === 'touch'
				if (isTouch) this.lastTouchAt = Date.now()
				// 手机浏览器在 touch 之后还会补一发 mousedown，别让它把刚开始的拖拽重置掉
				else if (Date.now() - (this.lastTouchAt || 0) < 800) return
				if (this.dragging) return

				this.dragging = true
				this.dragIndex = i
				this.dragOver = i
				this.dragDy = 0
				this.dragStartY = this.pointerY(e)

				// #ifdef H5
				// ⚠️ 先挂监听再量位置：量位置失败也要保证 mouseup 能收到，否则拖拽状态会卡死
				if (!isTouch && typeof window !== 'undefined') {
					this.onWinMove = (ev) => this.onDragMove(ev)
					this.onWinUp = () => this.onDragEnd()
					window.addEventListener('mousemove', this.onWinMove)
					window.addEventListener('mouseup', this.onWinUp)
				}
				// #endif

				await this.measureCards()
				const r = this.cardRects[i]
				this.dragH = r ? r.height : 0
			},
			onDragMove(e) {
				if (!this.dragging) return
				this.dragDy = this.pointerY(e) - this.dragStartY
				const rects = this.cardRects
				const cur = rects[this.dragIndex]
				if (!cur) return
				// 被拖卡片当前的中心点
				const center = cur.top + this.dragH / 2 + this.dragDy
				// 每次从"原位"重新算：往上拖就找第一个中心越过的槽位，往下拖反之
				let over = this.dragIndex
				for (let idx = 0; idx < rects.length; idx++) {
					if (idx === this.dragIndex) continue
					const mid = rects[idx].top + rects[idx].height / 2
					if (idx < this.dragIndex && this.dragDy < 0 && center < mid) over = Math.min(over, idx)
					else if (idx > this.dragIndex && this.dragDy > 0 && center > mid) over = Math.max(over, idx)
				}
				if (over !== this.dragOver) this.dragOver = over
			},
			onDragEnd() {
				if (!this.dragging) return
				// #ifdef H5
				if (typeof window !== 'undefined') {
					if (this.onWinMove) window.removeEventListener('mousemove', this.onWinMove)
					if (this.onWinUp) window.removeEventListener('mouseup', this.onWinUp)
				}
				this.onWinMove = null
				this.onWinUp = null
				// #endif
				const from = this.dragIndex
				const to = this.dragOver
				// 真拖过（位移超过一丢丢）才屏蔽接下来的 click，纯点一下手柄不算
				if (Math.abs(this.dragDy) > 6) this.suppressClickUntil = Date.now() + 400
				this.dragging = false
				this.dragIndex = -1
				this.dragOver = -1
				this.dragDy = 0
				this.dragH = 0
				this.cardRects = []
				if (from >= 0 && to >= 0 && from !== to) this.reorder(from, to)
			},
			/** 每张卡片的位移：被拖的跟手 + 放大；其余按方向让出一个身位（带过渡） */
			stepStyle(i) {
				if (!this.dragging) return ''
				if (i === this.dragIndex) {
					return 'position: relative; z-index: 6; transition: none; transform: translateY(' +
						this.dragDy + 'px) scale(1.02);'
				}
				let shift = 0
				if (this.dragIndex < this.dragOver && i > this.dragIndex && i <= this.dragOver) shift = -this.dragH
				else if (this.dragIndex > this.dragOver && i >= this.dragOver && i < this.dragIndex) shift = this.dragH
				return 'transform: translateY(' + shift + 'px); transition: transform 180ms cubic-bezier(.2,.8,.2,1);'
			},
			/** H5：手柄聚焦后按 ↑/↓ 精确移动（拖拽的无障碍退路） */
			onHandleKey(e, i) {
				const key = e && e.key
				if (key !== 'ArrowUp' && key !== 'ArrowDown') return
				if (e.preventDefault) e.preventDefault()
				const delta = key === 'ArrowUp' ? -1 : 1
				const j = i + delta
				if (j < 0 || j >= this.steps.length) return
				this.moveStep(i, delta)
				// 移动后 DOM 顺序变了，把焦点还给同一个手柄，才能连续按
				// #ifdef H5
				this.$nextTick(() => {
					if (typeof document === 'undefined') return
					const handles = document.querySelectorAll('.step-handle')
					const el = handles[j]
					if (el && el.focus) el.focus()
				})
				// #endif
			},
			toggleStep(i) {
				// #076：刚拖完的那一下 click 要吃掉 —— 拖拽松手时浏览器会补一发 click，
				// 它会冒泡到步头把卡片展开（"拖完莫名其妙展开了一张卡"）
				if (Date.now() < (this.suppressClickUntil || 0)) return
				this.openIndex = this.openIndex === i ? -1 : i
			},
			/** 手柄只负责拖拽：点它不展开卡片（展开走标题/箭头） */
			onHandleClick() {},
			stepSummary(s) {
				const parts = [Number(s.duration) > 0 ? Number(s.duration) + ' 秒' : '不计时']
				if (s.instruction) parts.push(s.instruction)
				return parts.join(' · ')
			},

			// ===== 提交 =====
			safeIcon() {
				// icon 字段后端 max_length=5，按码点截断（emoji 可能占 2 个码点）
				const chars = Array.from((this.form.icon || '').trim())
				return chars.slice(0, 5).join('') || '📋'
			},
			buildPayload() {
				const title = (this.form.title || '').trim()
				if (!title) {
					uni.showToast({ title: '标题还没写', icon: 'none' })
					return null
				}
				const steps = []
				for (let i = 0; i < this.steps.length; i++) {
					const s = this.steps[i]
					const st = (s.title || '').trim()
					// 后端会静默丢掉没有 title 的步骤，这里先挡住，别让用户白填
					if (!st) {
						this.openIndex = i
						uni.showToast({ title: '第 ' + (i + 1) + ' 步还没填动作', icon: 'none' })
						return null
					}
					const sec = Math.max(0, Math.round(Number(s.duration) || 0))
					steps.push({
						order: i,
						title: st,
						instruction: (s.instruction || '').trim(),
						explain: (s.explain || '').trim(),
						duration_seconds: sec,
						is_timed: sec > 0
					})
				}
				return {
					title: title,
					tagline: (this.form.tagline || '').trim(),
					description: (this.form.description || '').trim(),
					category: this.categoryKey,
					icon: this.safeIcon(),
					// #073：矢量图标 slug（'' = 没有 slug，前端回退默认图标）
					icon_key: this.form.iconKey || '',
					steps: steps
				}
			},

			// 发布前至少要一步（后端也会拦，这里让用户先看到原因）
			onMainTap() {
				if (this.isEdit) {
					this.submit('save')
					return
				}
				if (!this.steps.length) {
					uni.showToast({ title: '至少加一步才能发', icon: 'none' })
					return
				}
				this.submit('publish')
			},

			async submit(mode) {
				if (this.saving) return
				const payload = this.buildPayload()
				if (!payload) return
				this.saving = true
				try {
					await ensureLogin()
					if (this.isEdit) {
						await request('/quick/' + this.id + '/edit/', 'PUT', payload, { silent: true })
						uni.showToast({ title: '存好了', icon: 'none' })
					} else {
						const created = await post('/quick/', payload, { silent: true })
						const newId = created && created.id
						const publish = mode === 'publish' && newId
						if (publish) {
							await post('/quick/' + newId + '/publish/', {}, { silent: true })
						}
						uni.showToast({ title: publish ? '已发布' : '已存草稿', icon: 'none' })
						// 发布完去看详情，存草稿去"我创建的"继续管
						this.leaveTo(publish ? '/pages/detail/detail?id=' + newId : '/pages/mine/mine?tab=created')
					}
				} catch (e) {
					uni.showToast({ title: (e && e.data && e.data.error) || '没存上，再试一次', icon: 'none' })
				} finally {
					this.saving = false
				}
			},

			leaveTo(url) {
				// 等 toast 露个脸再跳，避免刚提示就切页
				setTimeout(() => uni.redirectTo({ url: url }), 600)
			},

			// ===== 快速导入（先本地解析预览，确认后再提交）=====
			openImport() {
				// #033 ③：标题只有弹层里这一个输入框。上方表单填过就先带进来，
				// 省得用户"上面填了标题、弹层里却是空的"（原先两边各填一次，还只认上面那个）
				if (!this.importTitle && this.form.title) this.importTitle = this.form.title
				this.importVisible = true
				this.importParsed = false
				this.importPreview = []
				this.importSkipped = []
			},
			closeImport() {
				this.importVisible = false
			},
			parseDuration(text) {
				const t = (text || '').trim()
				if (!t) return 0
				let m = t.match(/^(\d+(?:\.\d+)?)\s*(?:秒|s)?$/i)
				if (m) return Math.round(Number(m[1]))
				// 后端只认"秒/纯数字"，这里顺手把"分钟"换算掉，省得用户白填
				m = t.match(/^(\d+(?:\.\d+)?)\s*(?:分钟|分|min|m)$/i)
				if (m) return Math.round(Number(m[1]) * 60)
				return null
			},
			// 一键复制提示词：不弹确认，复制完给一句提示（H5 和小程序都支持 setClipboardData）
			copyAiPrompt() {
				uni.setClipboardData({
					data: this.aiPromptText,
					success: () => {
						// 微信自带的"内容已复制"提示会被这句顶掉，所以带上下一步动作
						uni.showToast({ title: '提示词复制好了，去问 AI 吧', icon: 'none' })
					},
					fail: () => uni.showToast({ title: '没复制上，长按上面的文字手动复制', icon: 'none' })
				})
			},
			parseLine(line) {
				const parts = String(line).split('|').map((p) => p.trim())
				if (parts.length < 2) return { reason: '缺少 | 分隔符' }
				const title = parts[0]
				if (!title) return { reason: '动作为空' }
				const seconds = this.parseDuration(parts[1])
				if (seconds === null) return { reason: '时长看不懂（用秒，如 60秒 / 1分钟）' }
				// 四段：动作 | 时长 | 画面文字 | 为什么（#032 ③）
				// 老的三段格式照样能用（为什么留空）；多于四段就把多出来的并进「为什么」，不丢内容
				return {
					step: {
						title: title,
						instruction: parts[2] || '',
						explain: parts.length >= 4 ? parts.slice(3).join(' | ') : '',
						duration_seconds: seconds,
						is_timed: seconds > 0
					}
				}
			},
			parseImport() {
				const lines = (this.importText || '').split('\n')
				const preview = []
				const skipped = []
				lines.forEach((line, i) => {
					if (!line.trim()) return // 空行直接忽略，不算失败
					const r = this.parseLine(line)
					if (r.step) preview.push(r.step)
					else skipped.push({ line: i + 1, reason: r.reason })
				})
				this.importPreview = preview
				this.importSkipped = skipped
				this.importParsed = true
				if (!preview.length) uni.showToast({ title: '没解析出步骤，检查一下格式，或者手动加', icon: 'none' })
			},
			fillSteps() {
				if (!this.importPreview.length) {
					uni.showToast({ title: '先把内容粘进来，再点「解析」', icon: 'none' })
					return
				}
				this.importPreview.forEach((p) => this.steps.push(makeStep(p)))
				// #033 ③：标题就在弹层里填，顺手同步回上方表单，关掉弹层后不用再填一遍
				if (this.importTitle.trim()) this.form.title = this.importTitle.trim()
				const n = this.importPreview.length
				this.closeImport()
				uni.showToast({ title: '填进来 ' + n + ' 步', icon: 'none' })
			},
			async createFromImport() {
				if (!this.importPreview.length) {
					uni.showToast({ title: '先把内容粘进来，再点「解析」', icon: 'none' })
					return
				}
				// #033 ①：标题来源统一成弹层里这个输入框。原先读的是 this.form.title（上方表单），
				// 用户在弹层里填的标题根本没被用上，还会被"先在上方填个标题"顶回来。
				const title = (this.importTitle || '').trim()
				if (!title) {
					uni.showToast({ title: '先写个标题吧', icon: 'none' })
					return
				}
				this.form.title = title
				try {
					await ensureLogin()
					// 归一化成后端认的 "动作 | 秒 | 画面文字 | 为什么"（#032：第 4 段也要带上，
					// 后端 quick_import 已同步支持解析 explain）
					const lines = this.importPreview.map(
						(p) => p.title + ' | ' + p.duration_seconds + ' | ' + (p.instruction || '') + ' | ' + (p.explain || '')
					)
					const d = await post('/quick/import/', {
						title: title,
						tagline: (this.form.tagline || '').trim(),
						category: this.categoryKey,
						icon: this.safeIcon(),
						icon_key: this.form.iconKey || '',
						lines: lines
					}, { silent: true })
					const skipped = (d && d.skipped_lines) || []
					const pid = d && d.pattern && d.pattern.id
					this.closeImport()
					uni.showToast({ title: skipped.length ? '已生成草稿，跳过 ' + skipped.length + ' 行' : '已生成草稿', icon: 'none' })
					// 转成编辑模式，继续补「为什么」和顺序
					if (pid) this.leaveTo('/pages/create/create?id=' + pid)
				} catch (e) {
					uni.showToast({ title: (e && e.data && e.data.error) || '没导进来，再试一次', icon: 'none' })
				}
			},

			onCategoryChange(e) {
				this.categoryIndex = Number(e.detail.value) || 0
			},
			goBack() {
				// #058③：与详情页同一套判断（页面栈 → 浏览器历史 → 首页兜底），
				// 别让返回键在网页版变成隐藏的"回首页"
				if (getCurrentPages().length > 1) {
					uni.navigateBack()
					return
				}
				// #ifdef H5
				if (typeof window !== 'undefined' && window.history && window.history.length > 1) {
					window.history.back()
					return
				}
				// #endif
				uni.reLaunch({ url: '/pages/library/library' })
			}
		}
	}
</script>

<style>
	.page {
		position: relative;
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
		background-color: var(--bg);
	}

	/* ===== 导航 ===== */
	.nav {
		flex-shrink: 0;
		background-color: var(--card);
	}

	/* 高度/上边距以微信胶囊为准；这组静态值是拿不到胶囊数据时的兜底 */
	.nav-inner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 32px;
		margin-top: 6px;
		padding: 0 16rpx;
	}

	.nav-btn {
		width: 88rpx;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.nav-btn-icon {
		font-size: 56rpx;
		line-height: 1;
		color: var(--text);
	}

	.nav-title {
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text);
	}

	.hover-dim {
		opacity: 0.6;
	}

	.body {
		flex: 1;
		height: 0;
	}

	/* ===== 表单 ===== */
	.block {
		margin: 24rpx;
		padding: 32rpx;
	}

	.block-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.block-title {
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
	}

	.field {
		margin-top: 28rpx;
	}

	.label {
		display: block;
		margin-bottom: 12rpx;
		font-size: 26rpx;
		color: var(--muted);
	}

	.req {
		color: var(--accent);
	}

	.input {
		box-sizing: border-box;
		width: 100%;
		height: 80rpx;
		padding: 0 24rpx;
		border-radius: 20rpx;
		background-color: var(--bg);
		font-size: 28rpx;
		color: var(--text);
	}

	.input-small {
		width: 320rpx;
	}

	.textarea {
		box-sizing: border-box;
		width: 100%;
		height: 150rpx;
		padding: 20rpx 24rpx;
		border-radius: 20rpx;
		background-color: var(--bg);
		font-size: 28rpx;
		line-height: 1.5;
		color: var(--text);
	}

	.ph {
		color: var(--muted);
	}

	.picker {
		height: 80rpx;
		padding: 0 24rpx;
		border-radius: 20rpx;
		background-color: var(--bg);
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.picker-text {
		font-size: 28rpx;
		color: var(--text);
	}

	.picker-arrow {
		font-size: 24rpx;
		color: var(--muted);
	}

	/* #073 图标选择器：平铺网格（原来是横向滚动的 emoji 行 + 手输 emoji 输入框） */
	.icon-grid {
		display: flex;
		flex-wrap: wrap;
		margin-top: 4rpx;
	}

	.icon-cell {
		width: 88rpx;
		height: 88rpx;
		margin: 0 12rpx 12rpx 0;
		border-radius: 20rpx;
		background-color: var(--bg);
		border: 2rpx solid transparent;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.icon-cell-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	/* ===== 步骤 ===== */
	.import-btn {
		height: 56rpx;
		padding: 0 24rpx;
		border-radius: 999rpx;
		background-color: var(--accent-soft);
		display: flex;
		align-items: center;
		font-size: 24rpx;
		color: var(--accent);
	}

	.steps-empty {
		display: block;
		margin-top: 24rpx;
		font-size: 26rpx;
		color: var(--muted);
		line-height: 1.6;
	}

	.step {
		margin-top: 20rpx;
		padding: 20rpx 24rpx;
		border-radius: 20rpx;
		background-color: var(--bg);
	}

	.step-head {
		display: flex;
		align-items: center;
	}

	.step-order {
		flex-shrink: 0;
		width: 44rpx;
		height: 44rpx;
		margin-right: 16rpx;
		border-radius: 22rpx;
		background-color: var(--accent-soft);
		color: var(--accent);
		font-size: 24rpx;
		font-weight: 600;
		text-align: center;
		line-height: 44rpx;
	}

	.step-head-main {
		flex: 1;
		min-width: 0;
	}

	.step-title {
		display: block;
		font-size: 28rpx;
		font-weight: 600;
		color: var(--text);
	}

	.step-sub {
		display: block;
		margin-top: 4rpx;
		font-size: 22rpx;
		color: var(--muted);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.step-caret {
		flex-shrink: 0;
		margin-left: 12rpx;
		font-size: 24rpx;
		color: var(--muted);
	}

	/* #076 拖拽手柄（≡ 三条杠）：放步骤卡最左侧。88rpx(=44px) 的触控区；
	   touch-action:none 关掉浏览器默认手势 —— 否则手机上按住一拖就变成滚页面 */
	.step-handle {
		flex-shrink: 0;
		width: 88rpx;
		height: 88rpx;
		margin-right: 4rpx;
		border-radius: 20rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		touch-action: none;
		/* 手柄上起手拖拽时别把卡片文字选中（鼠标拖过去会拖出一道蓝色选区） */
		user-select: none;
		-webkit-user-select: none;
	}

	/* 被拖起来的卡片：浮起（阴影 + 描边；位移/放大走 inline transform） */
	.step-drag {
		border-color: var(--accent);
		background-color: var(--card);
		box-shadow: 0 16rpx 40rpx rgba(0, 0, 0, 0.35);
	}

	/* #075：删除键只留这一个（工具行里那句「删除这一步」已删）。手机上也要能删，
	   所以不再 display:none；44px 触控目标 */
	.step-del {
		flex-shrink: 0;
		box-sizing: border-box;
		min-height: 88rpx;
		padding: 0 20rpx;
		margin-left: 8rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		/* 手机上卡片窄，"删除"两个字会被挤成竖排（变成一个圆疙瘩），这里禁止折行 */
		white-space: nowrap;
		font-size: 24rpx;
		color: #c0392b;
		border: 2rpx solid rgba(192, 57, 43, 0.35);
		border-radius: 999rpx;
	}
	/* 桌面端：删除键抬到 40px 起（鼠标点着不累） */
	@media (min-width: 768px) {
		.step-del {
			min-height: 40px;
			padding: 0 12px;
			font-size: 13px;
			border-radius: var(--r-btn);
		}
	}
	@media (hover: hover) {
		.step-del {
			cursor: pointer;
		}
		.step-del:hover {
			background-color: rgba(192, 57, 43, 0.1);
		}
	}

	.step-body {
		margin-top: 24rpx;
		padding-top: 8rpx;
		border-top: 2rpx solid var(--border);
	}

	.dur-row {
		display: flex;
		align-items: center;
		margin-top: 12rpx;
	}

	.dur {
		height: 56rpx;
		padding: 0 20rpx;
		margin-right: 12rpx;
		border-radius: 999rpx;
		background-color: var(--card);
		display: flex;
		align-items: center;
	}

	.dur-on {
		background-color: var(--accent-soft);
	}

	.dur-text {
		font-size: 22rpx;
		color: var(--muted);
	}

	.dur-on .dur-text {
		color: var(--accent);
		font-weight: 600;
	}

	.add-step {
		margin-top: 24rpx;
		height: 88rpx;
		border-radius: 20rpx;
		border: 2rpx dashed var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 28rpx;
		color: var(--accent);
	}

	.bar-space {
		height: 40rpx;
	}

	/* ===== 底部操作 ===== */
	.action-bar {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		padding: 20rpx 24rpx;
		padding-bottom: calc(20rpx + constant(safe-area-inset-bottom));
		padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
		background-color: var(--card);
		border-top: 2rpx solid var(--border);
	}

	.act {
		height: 88rpx;
	}

	.act-side {
		flex-shrink: 0;
		width: 240rpx;
		margin-right: 20rpx;
	}

	.act-main {
		flex: 1;
	}

	/* 0 步时的"发布"：视觉上禁用，点一下给原因 */
	.act-off {
		opacity: 0.45;
	}

	/* ===== 导入弹层 ===== */
	.mask {
		position: absolute;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		z-index: 20;
		background-color: rgba(0, 0, 0, 0.45);
		display: flex;
		align-items: flex-end;
	}

	.sheet {
		box-sizing: border-box;
		width: 100%;
		max-height: 86vh;
		/* #033 ②：这一层是「上固定 / 中滚动 / 下固定」的容器。
		   以前只有 max-height、没有 overflow，子节点也没写 flex: none，
		   于是内容一多 flex 就把它们往下压（复制按钮 44px→31px、粘贴框 144px→28px），
		   压不动的那截直接溢出卡片外、又被 .page 的 overflow:hidden 裁掉——
		   "被吞、下拉才出现、还点不准"就是这个原因。 */
		overflow: hidden;
		padding: 32rpx 24rpx 0;
		border-radius: 32rpx 32rpx 0 0;
		background-color: var(--card);
		display: flex;
		flex-direction: column;
	}

	/* #037：AI 提示词区（挪到标题下面，在可滚动的 .sheet-body 里，所以不写 flex: none） */
	.sheet-prompt {
		margin-top: 24rpx;
	}
	.sheet-prompt-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.sheet-prompt-label {
		flex: 1;
		min-width: 0;
		font-size: 24rpx;
		color: var(--text-2);
	}
	.sheet-prompt-text {
		display: block;
		box-sizing: border-box;
		max-height: 260rpx;
		margin-top: 12rpx;
		padding: 20rpx 24rpx;
		border-radius: 20rpx;
		background-color: var(--bg);
		font-size: 22rpx;
		line-height: 1.6;
		color: var(--muted);
		white-space: pre-wrap; /* 提示词是带换行的整段文本，要按原样显示 */
		overflow-y: auto;
	}

	/* 下部：粘贴框 / 标题 / 结果预览都在这层里滚，撑不破弹层 */
	.sheet-body {
		flex: 1 1 auto;
		min-height: 0; /* 不写 0 的话 flex 子项最小高度=内容高度，滚动条出不来 */
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
	}

	.sheet-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.sheet-title {
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text);
	}

	.sheet-close {
		padding: 0 12rpx;
		font-size: 28rpx;
		color: var(--muted);
	}

	.sheet-hint {
		/* #033 ③：提示语现在在 .sheet-top 里（普通块级容器），
		   必须显式 block 才能吃到 margin-top（flex 子项会被自动块级化，普通容器里不会） */
		display: block;
		margin-top: 12rpx;
		font-size: 24rpx;
		color: var(--muted);
		line-height: 1.5;
	}

	.sheet-input {
		box-sizing: border-box;
		width: 100%;
		height: 220rpx;
		margin-top: 16rpx;
		padding: 20rpx 24rpx;
		border-radius: 20rpx;
		background-color: var(--bg);
		font-size: 26rpx;
		line-height: 1.5;
		color: var(--text);
	}

	/* 标题输入（#033 ③：合并掉原来的「主题」，只留这一个输入框，样式走 .input） */
	.sheet-field {
		margin-top: 24rpx;
	}
	.sheet-field-label {
		display: block;
		margin-bottom: 10rpx;
		font-size: 24rpx;
		color: var(--text-2);
	}
	.sheet-field-tip {
		display: block;
		margin-top: 8rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	/* 底部操作：固定贴在弹层最下面（#033 ②），内容再多也在，不再被压扁 */
	.sheet-actions {
		flex: none;
		display: flex;
		align-items: center;
		padding: 20rpx 0;
		padding-bottom: calc(20rpx + constant(safe-area-inset-bottom));
		padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
		background-color: var(--card);
	}

	.sheet-act {
		flex: 1;
		height: 80rpx;
		margin-right: 12rpx;
		font-size: 26rpx;
	}

	.sheet-act:last-child {
		margin-right: 0;
	}

	.sheet-act-off {
		opacity: 0.45;
	}

	/* #033 ②：结果区不再自己开滚动条（嵌套滚动最难用手指），统一交给 .sheet-body 滚 */
	.sheet-result {
		margin-top: 20rpx;
		padding-bottom: 8rpx;
	}

	.result-line {
		display: block;
		font-size: 26rpx;
		color: var(--text);
	}

	.warn-line {
		margin-top: 12rpx;
		padding: 12rpx 20rpx;
		border-radius: 12rpx;
		background-color: rgba(192, 57, 43, 0.08);
	}

	.warn-text {
		font-size: 24rpx;
		color: #c0392b;
	}

	.preview-line {
		display: flex;
		margin-top: 16rpx;
	}

	.preview-idx {
		flex-shrink: 0;
		width: 40rpx;
		height: 40rpx;
		margin-right: 14rpx;
		border-radius: 20rpx;
		background-color: var(--accent-soft);
		color: var(--accent);
		font-size: 22rpx;
		text-align: center;
		line-height: 40rpx;
	}

	.preview-main {
		flex: 1;
		min-width: 0;
	}

	.preview-title {
		display: block;
		font-size: 26rpx;
		color: var(--text);
	}

	.preview-sub {
		display: block;
		margin-top: 4rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	.sheet-note {
		display: block;
		margin: 20rpx 0 8rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	/* ===== 网页版（H5）：按设计规范完善（#029 §4.1 / §4.2） ===== */
	/* #ifdef H5 */
	/* 电脑端：表单居中限宽 720px；手机端全宽（.body 已由 App.vue 限宽居中） */
	.block,
	.add-step {
		box-sizing: border-box;
		width: 100%;
		max-width: 720px;
		margin-left: auto;
		margin-right: auto;
	}

	/* 输入框 / 文本域 / 选择器：次级面 + 细边框 + 按钮级圆角（#035 起统一走 --r-btn） */
	.input,
	.textarea,
	.picker,
	.sheet-input {
		background-color: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: var(--r-btn);
		color: var(--text);
	}

	/* 步骤卡片：卡片面 + --r-card 圆角；电脑端 hover 微升起（规范 §4.1） */
	.step {
		background-color: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--r-card);
	}
	@media (hover: hover) {
		.step {
			transition: transform 200ms ease, border-color 200ms ease;
		}
		.step:not(.step-drag):hover {
			transform: translateY(-2px);
			border-color: var(--accent-soft);
		}
	}
	/* 序号用标志色（规范：标志色只用在 logo / 激活 / 主按钮 / 序号） */
	.step-order {
		background-color: var(--accent-soft);
		color: var(--accent);
	}
	.step-title {
		color: var(--text);
	}

	/* 拖拽手柄：电脑端给抓取手势 + 键盘聚焦环（手柄能聚焦，↑/↓ 也能排序） */
	.step-handle {
		cursor: grab;
	}
	.step-handle:active {
		cursor: grabbing;
	}
	.step-handle:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		background-color: var(--accent-soft);
	}

	/* 次要动作（导入 / 解析）统一成次按钮 */
	.import-btn,
	.sheet-act {
		background-color: transparent;
		border: 1px solid var(--border);
		border-radius: var(--r-btn);
		color: var(--text);
	}
	.add-step {
		border: 1px dashed var(--border);
		border-radius: var(--r-card);
		color: var(--text-2);
	}

	/* 底部操作栏（#031 ①）：做成"浮起来的圆角条"——四角 12px、左右离屏幕边一档留白、底部不封死。
	   ⚠️ 安全区写进 bottom 偏移，而不是写进 padding：
	   - 写在 bottom：整条栏在 iPhone 上再往上抬 env(safe-area-inset-bottom)，稳稳躲开 home indicator；
	   - 若写进 padding，栏内部会被撑高，视觉上"栏很高但按钮挤在中间"，反而更丑（#030 ⑤ 刚修过这里）。
	   所以下面用 padding-bottom 覆盖掉基类里那句 calc(20rpx + env(...))。 */
	.action-bar {
		position: fixed;
		left: 0;
		right: 0;
		bottom: calc(12px + env(safe-area-inset-bottom));
		z-index: 15;           /* 比导入弹层（.mask，z-index 20）低一档，弹层打开时能盖住它 */
		box-sizing: border-box;
		width: calc(100% - 2 * var(--content-pad));
		max-width: 720px;      /* 跟上面的表单同宽；电脑端不拉成通栏 */
		margin: 0 auto;
		padding: 20rpx 24rpx;
		padding-bottom: 20rpx; /* 覆盖基类的安全区 padding：安全区已由 bottom 承担 */
		border: 1px solid var(--border);
		border-top: 1px solid var(--border);
		border-radius: var(--r-card);
		background-color: var(--card);
	}
	/* 正文末尾给浮栏留位（含安全区），别让最后一屏被压住 */
	.bar-space {
		height: calc(120px + env(safe-area-inset-bottom));
	}
	.act-main {
		border-radius: var(--r-btn);
	}

	/* 快速导入弹层：电脑端改成居中对话框（宽屏下从底部拉一条通栏很怪） */
	@media (min-width: 768px) {
		.mask {
			align-items: center;
		}
		.sheet {
			max-width: 560px;
			margin: 0 auto;
			border-radius: var(--r-card);
		}
	}
	/* 粘贴框用等宽字体，"动作 | 时长 | 画面文字"才对得齐 */
	.sheet-input {
		font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
		line-height: 1.6;
	}
	.sheet-hint {
		color: var(--muted);
	}
	/* 解析结果：成功用标志色，失败行用危险色 */
	.result-line {
		color: var(--accent);
	}
	.warn-line {
		background-color: color-mix(in srgb, var(--danger) 12%, transparent);
		border-radius: var(--r-chip);
	}
	.warn-text {
		color: var(--danger);
	}
	.preview-line {
		border-bottom: 1px solid var(--border);
	}
	.preview-idx {
		color: var(--accent);
	}
	.preview-title {
		color: var(--text);
	}
	.preview-sub,
	.sheet-note {
		color: var(--muted);
	}
	/* #endif */
	/* ===== AI 提示词弹层（#032 ③） ===== */
	/* #ifdef H5 */
	/* ①②（标题区圆角浮卡 + 圆形返回按钮）已提升到 App.vue 的全局 H5 样式，所有页面统一，
	   这里不再重复定义。 */

	/* ③ 弹层：复制按钮（#037 起挪到标题下面，跟"AI 提示词"标签同一行） */
	.copy-btn {
		margin-top: 4px;
		height: 44px;
		border-radius: var(--r-btn);
	}
	/* #037：提示词区在标题下面，一行放"标签 + 复制按钮"，下面跟提示词全文 */
	.sheet-prompt-head .copy-btn {
		flex: none;
		margin-top: 0;
		padding: 0 16px;
	}
	.sheet-prompt-label {
		color: var(--text-2);
	}
	.sheet-prompt-text {
		border: 1px solid var(--border);
		border-radius: var(--r-btn);
		background-color: var(--surface-2);
	}
	.sheet-prompt-text::-webkit-scrollbar {
		width: 6px;
	}

	/* #033 ②：弹层整体改用 dvh（手机地址栏收起/键盘弹出时 100vh 会算多），
	   并把它从 .page（overflow: hidden）里解放出来——溢出内容不再被页面裁掉，
	   而是由 .sheet-body 自己滚。 */
	.mask {
		position: fixed;
		height: 100vh;
		height: 100dvh;
		overflow: hidden;
	}
	.sheet {
		max-height: calc(100vh - 24px);
		max-height: calc(100dvh - 24px);
		box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.35);
	}
	@media (max-width: 767px) {
		/* #035 ②：手机端底部弹层也换成收小后的圆角（基类 32rpx 在手机上≈21px，比卡片还圆） */
		.sheet {
			border-radius: var(--r-card) var(--r-card) 0 0;
		}
	}
	/* 底部操作条：加一条分隔线，让人一眼看出这是"固定的一层"而不是正文内容 */
	.sheet-actions {
		padding-top: 12px;
		padding-bottom: calc(12px + env(safe-area-inset-bottom));
		border-top: 1px solid var(--border);
	}
	.sheet-field-label,
	.sheet-field-tip {
		color: var(--muted);
	}
	.sheet-body::-webkit-scrollbar {
		width: 6px;
	}
	/* 解析结果里的第 4 段「为什么」 */
	.preview-explain {
		display: block;
		margin-top: 4px;
		font-size: 12px;
		line-height: 1.5;
		color: var(--muted);
	}
	/* #endif */
</style>
