<template>
	<view class="page">
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">我的任务</text>
				<view class="nav-right">
					<!-- #085：日程入口 —— 看排布在那边，打勾还在这页 -->
					<view class="nav-btn" hover-class="hover-dim" @click="goSchedule">
						<app-icon name="calendar" :size="16" tone="muted" />
					</view>
					<view class="nav-btn" hover-class="hover-dim" @click="reload">
						<app-icon name="arrows-clockwise" :size="16" tone="muted" />
					</view>
				</view>
			</view>
		</view>

		<scroll-view
			class="body"
			scroll-y
			:refresher-enabled="true"
			:refresher-triggered="refreshing"
			refresher-background="transparent"
			@refresherrefresh="onRefresh"
		>
			<view class="wrap">
				<!-- 今日完成度：当天做完了几项 / 一共几项 + 步骤进度条（#084：全清时整块变"完成态"） -->
				<view class="today theme-card" :class="{ 'today-done': todayDone }">
					<view class="today-head">
						<view class="today-label-row">
							<text class="today-label">今天</text>
							<!-- 全清：一个小勾 + 「全清了」，让完成态肉眼可见，而不只是数字变了 -->
							<view v-if="todayDone" class="today-tick">
								<app-icon name="check" :size="12" tone="inverse" />
							</view>
							<text v-if="todayDone" class="today-done-text">全清了</text>
						</view>
						<view class="today-num-row">
							<text class="today-num">{{ tasksDone }}</text>
							<text class="today-den">/{{ tasksTotal }}</text>
						</view>
					</view>
					<view class="today-bar">
						<view class="today-bar-in" :style="{ width: stepPct + '%' }"></view>
					</view>
					<text class="today-sub">{{ todaySub }}</text>
				</view>

				<!-- 状态筛选 -->
				<view class="segs">
					<view
						v-for="s in segs"
						:key="s.key"
						class="seg"
						:class="{ 'seg-on': status === s.key }"
						hover-class="hover-dim"
						@click="switchStatus(s.key)"
					>
						<text class="seg-text">{{ s.label }}</text>
					</view>
				</view>

				<!-- 首屏骨架 -->
				<view v-if="loading && !groups.length" class="groups">
					<view v-for="i in 3" :key="i" class="task theme-card">
						<view class="sk-line sk-line-lg"></view>
						<view class="sk-line"></view>
					</view>
				</view>

				<!-- 错误态 -->
				<view v-else-if="errorMsg && !groups.length" class="state">
					<view class="state-mark"><app-icon name="cloud-slash" :size="28" tone="muted" /></view>
					<text class="state-title">没连上</text>
					<text class="state-desc">{{ errorMsg }}</text>
					<view class="state-btn btn-accent" hover-class="hover-dim" @click="reload"><text>再试一次</text></view>
				</view>

				<!-- 空态 -->
				<view v-else-if="!groups.length" class="state">
					<view class="state-mark"><app-icon name="list-checks" :size="28" tone="muted" /></view>
					<text class="state-title">{{ emptyTitle }}</text>
					<text class="state-desc">{{ emptyDesc }}</text>
					<!-- #089：今天空着但有没排日子的任务时，下一步是"排一下"，不是"再挑一张" -->
					<view v-if="showUnscheduledHint" class="state-btn btn-accent" hover-class="hover-dim" @click="goSchedule">
						<text>去排一下</text>
					</view>
					<view v-else-if="status !== 'archived'" class="state-btn btn-accent" hover-class="hover-dim" @click="goLibrary">
						<text>去挑一件小事</text>
					</view>
					<view v-else class="state-btn btn-ghost" hover-class="hover-dim" @click="switchStatus('active')">
						<text>看看进行中的</text>
					</view>
				</view>

				<!-- #089：没排日子的任务不进"今天"，列表上方留一条出口，免得用户以为任务丢了 -->
				<view
					v-if="showUnscheduledHint && groups.length"
					class="unsched-bar"
					hover-class="hover-dim"
					@click="goSchedule"
				>
					<text class="unsched-text">还有 {{ unscheduled }} 件没排日子</text>
					<text class="unsched-go">去排一下 ›</text>
				</view>

				<!-- 按 t-box 时段分组；每组左边一条竖线，是 TimeBlock 那套「时间段」的视觉 -->
				<view v-for="g in groups" :key="g.key" class="group">
					<view class="g-head">
						<view class="g-rail"></view>
						<text class="g-label">{{ g.label }}</text>
						<text class="g-count">{{ g.tasks.length }}</text>
					</view>

					<view
						v-for="t in g.tasks"
						:key="t.id"
						class="task theme-card"
						:class="{ 'task-done': isFinished(t), 'task-focus': String(t.id) === focusTaskId }"
					>
						<view class="t-head" hover-class="hover-dim" @click="toggleExpand(t)">
							<view class="t-icon">
								<app-icon
									v-if="t.source_pattern && t.source_pattern.icon_key"
									:name="t.source_pattern.icon_key"
									:size="19"
									tone="accent"
								/>
								<text v-else class="t-emoji">{{ (t.source_pattern && t.source_pattern.icon) || '📋' }}</text>
							</view>

							<view class="t-main">
								<view class="t-title-row">
									<text class="t-title">{{ t.title }}</text>
									<!-- #087：一次性的做完 = 这任务结束了；习惯/配额的做完只是"今天做完了"，
									     明天还会出现，所以标签要分开说 -->
									<text v-if="isFinished(t)" class="t-badge">已完成</text>
									<text v-else-if="doneToday(t)" class="t-badge t-badge-today">今天做完了</text>
								</view>
								<view class="t-meta">
									<!-- #083：合成一段文本（而不是三个 text 节点）—— 换行时不会把「·」甩到行首 -->
									<text class="t-meta-text">{{ metaText(t) }}</text>
								</view>
								<view class="t-bar">
									<view class="t-bar-in" :style="{ width: taskPct(t) + '%' }"></view>
								</view>
							</view>

							<text v-if="isArchived(t)" class="t-archived">已归档</text>
							<text v-if="t.steps_total" class="t-caret">{{ expanded[t.id] ? '⌃' : '⌄' }}</text>
							<!-- #083：任务设置（改标题/频率/时段/目标次数 + 归档/删除）。
							     放一个"⋯"而不是排三个按钮，卡片上依旧只有一个入口 -->
							<view class="t-more" hover-class="hover-dim" @click.stop="openTaskSettings(t)">
								<text class="t-more-text">⋯</text>
							</view>
						</view>

						<!-- 展开：步骤逐条 tick box（勾上即完成，乐观更新）+ 每条可编辑（#080） -->
						<view v-if="expanded[t.id]" class="t-steps">
							<view v-if="stepsLoading[t.id]" class="t-loading">
								<text class="t-loading-text">加载步骤…</text>
							</view>
							<view
								v-for="s in stepsOf(t.id)"
								:key="s.id"
								class="s"
								:class="{ 's-on': s.is_done }"
								hover-class="hover-dim"
								@click="toggleStep(t, s)"
							>
								<view class="s-box" :class="{ 's-box-on': s.is_done }">
									<app-icon v-if="s.is_done" name="check" :size="12" tone="inverse" />
								</view>
								<view class="s-main">
									<text class="s-title">{{ s.title }}</text>
									<text v-if="s.instruction" class="s-ins">{{ s.instruction }}</text>
								</view>
								<text v-if="s.is_timed && s.duration_seconds" class="s-dur">
									{{ formatDuration(s.duration_seconds) }}
								</text>
								<!-- 编辑这一步：stop 掉冒泡，别顺手把勾选框点了 -->
								<view class="s-edit" hover-class="hover-dim" @click.stop="openStepEdit(t, s)">
									<app-icon name="note-pencil" :size="14" tone="muted" />
								</view>
							</view>

							<!-- 加一步 -->
							<view class="s-add" hover-class="hover-dim" @click.stop="openStepAdd(t)">
								<text class="s-add-text">＋ 加一步</text>
							</view>
						</view>
					</view>
				</view>

				<view class="bar-space"></view>
			</view>
		</scroll-view>

		<!-- #080：步骤编辑面板（改标题/说明/时长、加一步、删一步） -->
		<step-sheet
			:visible="stepSheetVisible"
			:task-id="stepSheetTaskId"
			:step="stepSheetStep"
			@close="stepSheetVisible = false"
			@saved="onStepsSaved"
		/>

		<!-- #083：任务设置（改标题/频率/时段/目标次数 + 归档/删除），复用 task-sheet 的编辑模式 -->
		<task-sheet
			:visible="taskSheetVisible"
			:task="taskSheetTask"
			@close="taskSheetVisible = false"
			@saved="onTaskSaved"
		/>

		<!-- 电脑端右下角悬浮刷新按钮（手机端下拉刷新就够，隐藏） -->
		<view class="fab" hover-class="hover-dim" @click="reload">
			<app-icon name="arrows-clockwise" :size="20" tone="accent" />
		</view>
	</view>
</template>

<script>
	import { get, request, errText } from '@/api/request.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { formatDuration } from '@/utils/adapter.js'
	import { requireLogin } from '@/utils/token.js'
	import AppIcon from '@/components/app-icon/app-icon.vue'
	import StepSheet from '@/components/step-sheet/step-sheet.vue'
	import TaskSheet from '@/components/task-sheet/task-sheet.vue'

	// 与后端 tasks.models.TIMESLOT_ORDER 一致（顺序 = 一天里的先后）
	const SLOT_ORDER = ['morning', 'noon', 'afternoon', 'evening', 'night']
	const SLOT_LABELS = {
		morning: '早上',
		noon: '中午',
		afternoon: '下午',
		evening: '晚上',
		night: '睡前'
	}

	export default {
		components: { AppIcon, StepSheet, TaskSheet },
		data() {
			return {
				statusBarHeight: 20,
				nav: {},
				status: 'active',
				segs: [
					{ key: 'active', label: '进行中' },
					{ key: 'done', label: '已完成' },
					{ key: 'archived', label: '归档' },
					{ key: 'all', label: '全部' }
				],
				tasks: [],
				// #091：顶部「今天」卡专用。切到全部/已完成/归档时列表会换，但这张卡是
				// "今天"的仪表，必须一直是今天那批（跟首页同一口径），不能被 tab 带着跑。
				todayItems: [],
				// #089：没排日子的进行中任务数量。今天这一页只收"排到今天"的，
				// 老任务（#085 之前没有 plan_date）会从这页消失 —— 有这个数字才能提示去哪儿找
				unscheduled: 0,
				loading: false,
				refreshing: false,
				errorMsg: '',
				// #092：首屏拉过一次之后，每次重新显示都静默刷新
				loadedOnce: false,
				fetching: false,
				// #090：从首页带过来的任务 id（定位/高亮用）
				focusId: '',
				focusTaskId: '',
				// 展开状态与步骤缓存：列表接口只给计数，步骤在首次展开时才拉（省流量）
				expanded: {},
				stepsCache: {},
				stepsLoading: {},
				// 正在提交的步骤 id，防止连点重复请求
				pending: {},
				// #080：步骤编辑面板（step=null 表示"加一步"）
				stepSheetVisible: false,
				stepSheetTaskId: '',
				stepSheetStep: null,
				// #083：任务设置面板（传 task 即编辑模式）
				taskSheetVisible: false,
				taskSheetTask: null
			}
		},
		computed: {
			groups() {
				const buckets = {}
				const rest = []
				this.tasks.forEach((t) => {
					const key = t.timeslot || ''
					if (!key) {
						rest.push(t)
						return
					}
					if (!buckets[key]) buckets[key] = []
					buckets[key].push(t)
				})
				const out = []
				SLOT_ORDER.forEach((key) => {
					if (buckets[key] && buckets[key].length) {
						out.push({ key, label: SLOT_LABELS[key], tasks: buckets[key] })
						delete buckets[key]
					}
				})
				// 自定义时段（"通勤时"这种）按字母序接在标准时段后面
				Object.keys(buckets).sort().forEach((key) => {
					out.push({ key, label: key, tasks: buckets[key] })
				})
				if (rest.length) out.push({ key: '__none', label: '未分时段', tasks: rest })
				return out
			},
			tasksTotal() {
				return this.todayItems.length
			},
			tasksDone() {
				return this.todayItems.filter((t) => this.isTaskDone(t)).length
			},
			stepSum() {
				let total = 0
				let done = 0
				this.todayItems.forEach((t) => {
					total += t.steps_total || 0
					done += t.steps_done || 0
				})
				return { total: total, done: done }
			},
			stepPct() {
				const s = this.stepSum
				return s.total ? Math.round((s.done / s.total) * 100) : 0
			},
			// #084：全部做完 = 每一项都完成（含 once 的 done 状态），且至少有一项
			allDone() {
				return this.todayItems.length > 0 && this.tasksDone === this.tasksTotal
			},
			// #084：顶部那句随状态走 —— 空 / 没开始 / 做到一半 / 全清
			todaySub() {
				if (!this.todayItems.length) return '还没开始，不急'
				const s = this.stepSum
				if (!s.total) return '这些任务还没写步骤，展开看看模板'
				if (this.allDone) {
					// 全清：不同 tab 说不同的话（在归档/已完成 tab 里说"明天见"会很怪）
					if (this.status === 'archived') return '收起来的都在这一栏'
					return this.status === 'done' ? '今天没有要做的了，歇会儿吧' : '今天都做完了 🎉 明天见'
				}
				if (s.done === 0) return '今天 0/' + s.total + ' 步，慢慢来'
				const left = this.todayItems.length - this.tasksDone
				return s.done + '/' + s.total + ' 步，慢慢来 · 还有 ' + left + ' 项'
			},
			// #084：全清时给顶部加一个"完成态"的样式钩子
			todayDone() {
				return this.allDone
			},
			// #083：空态按 tab 说不同的话（归档空 ≠ 今天空）
			emptyTitle() {
				if (this.status === 'archived') return '归档里还空着'
				if (this.status === 'done') return '还没有做完的'
				return '今天还空着'
			},
			emptyDesc() {
				if (this.status === 'archived') return '收起来的任务会放在这，想用的时候在任务设置里「放回进行中」。'
				if (this.status === 'done') return '一件件做完的会留在这儿，做完了自然就过来了。'
				// #089：今天这页只收"排到今天"的。老任务没排日子会落在这儿，
				// 要是还说"去挑一件小事"，用户就去找卡了，其实他的任务在未排期里等着
				if (this.unscheduled > 0) {
					return '你有 ' + this.unscheduled + ' 件还没排日子，去日程页把它们放到今天就好；也可以去模板页挑新的。'
				}
				return '挑一件小事开始就好，三十秒也算。在模板页点「加入任务」，它就会到这儿来。'
			},
			// #089：没排日子的任务存在时，列表上方给一条出口（点进去 = 日程页排期）
			showUnscheduledHint() {
				return this.status === 'active' && this.unscheduled > 0
			}
		},
		onLoad(options) {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
			// #090：首页点某张卡进来 → focus=任务 id，加载后自动展开那一条
			this.focusId = (options && options.focus) ? String(options.focus) : ''
			this.reload()
		},
		onShow() {
			// #092：从详情/执行/模板详情「加入我的任务」回来时列表和数字都要变。
			// 不看 tasks.length —— 空态（全做完/没排期）返回时也得刷新。
			// 首屏 onLoad 已经拉过一次，这里用 silent 避免重复 loading 闪一下
			if (this.loadedOnce) this.reload(true)
		},
		methods: {
			// #081/#084：剩余次数的说法按状态走 —— 还有 / 达成 / 不限
			leftText(t) {
				const left = t.remaining_count
				if (left === null) return '不限次数，按自己的节奏来'
				const weekly = t.frequency_type === 'quota' && t.quota_period === 'week'
				if (left <= 0) return weekly ? '本周目标达成，想多做也行' : '目标达成，想多做也行'
				return weekly ? '本周还剩 ' + left + ' 次' : '还剩 ' + left + ' 次'
			},
			// #087：今天做完了吗 —— 习惯/配额看今天的 TaskDay（后端算好 done_today），
			// 昨天做完了不算，明天重新从 0 开始
			doneToday(t) {
				return !!t.done_today
			},
			// 真正"结束"的任务（变灰、以后不再出现）：只有做完的一次性任务会到 done
			isFinished(t) {
				return t.status === 'done'
			},
			// 今天做完了 / 任务结束 —— 顶部进度、全清判断都用它
			isTaskDone(t) {
				if (t.status === 'done') return true
				if (t.steps_total > 0) return !!t.done_today || t.steps_done >= t.steps_total
				return false
			},
			isArchived(t) {
				return t.status === 'archived'
			},
			// #083：卡片第二行合成一段文本 —— "一次性 · 还剩 6 次 · 0/4 步"
			// （以前是三个 text 节点，窄屏换行会把「·」甩到行首，看着像排版坏了）
			metaText(t) {
				const parts = [t.frequency_label]
				if (t.remaining_count !== null) {
					parts.push(this.leftText(t))
				} else if (t.frequency_type === 'quota') {
					parts.push('每周 ' + t.quota_count + ' 次，节奏你定')
				} else if (t.frequency_type === 'habit') {
					// #084：习惯类本来就不该有"目标次数"，说清楚"不限"比留白更让人安心
					parts.push('不限次数，按自己的节奏来')
				}
				if (t.steps_total) parts.push(t.steps_done + '/' + t.steps_total + ' 步')
				return parts.join(' · ')
			},
			taskPct(t) {
				if (!t.steps_total) return t.status === 'done' ? 100 : 0
				return Math.round((t.steps_done / t.steps_total) * 100)
			},
			stepsOf(id) {
				return this.stepsCache[id] || []
			},
			formatDuration,
			goBack() {
				const pages = getCurrentPages()
				if (pages.length > 1) uni.navigateBack()
				else uni.reLaunch({ url: '/pages/index/index' })
			},
			goSchedule() {
				uni.navigateTo({ url: '/pages/schedule/schedule' })
			},
			goLibrary() {
				// #090：模板列表从首页搬到 /pages/library/library
				uni.navigateTo({ url: '/pages/library/library' })
			},
			switchStatus(key) {
				if (this.status === key) return
				this.status = key
				this.reload()
			},
			async onRefresh() {
				this.refreshing = true
				await this.load(true)
				this.refreshing = false
			},
			reload(silent) {
				return this.load(!!silent)
			},
			// #092：silent=true 是"后台刷新"——旧列表先留着，失败也不把画面换成错误页
			async load(silent) {
				if (this.fetching) return
				this.fetching = true
				if (!silent) this.loading = true
				try {
					await requireLogin()
					const params = {}
					if (this.status !== 'all') params.status = this.status
					// #089：进行中 = 「今天」= status=active 且 plan_date=今天（后端唯一口径）。
					// 以前这里拿的是全部 active，排到明年的事也算"今天"，allDone 永远不成立。
					if (this.status === 'active') params.today = 1
					const data = await get('/tasks/', params, { silent: !!silent })
					this.tasks = (data && data.items) || []
					this.unscheduled = (data && data.unscheduled) || 0
					if (this.status === 'active') {
						// 进行中这一栏本来就是今天这批，一份数据两用
						this.todayItems = this.tasks
					} else {
						// 其它 tab 的列表不是今天的 —— 另外取一次今天的摘要，
						// 顶部那张卡说的永远是"今天"，两页数字才对得上
						const todayData = await get('/tasks/', { today: 1 }, { silent: true })
						this.todayItems = (todayData && todayData.items) || []
						this.unscheduled = (todayData && todayData.unscheduled) || 0
					}
					this.errorMsg = ''
					this.loadedOnce = true
					// #090：首页点卡进来 —— 那一条自动展开（步骤直接能勾），并滚到眼前
					if (this.focusId) {
						const hit = this.tasks.find((t) => String(t.id) === String(this.focusId))
						if (hit) {
							if (!this.stepsCache[hit.id]) this.fetchSteps(hit.id)
							this.expanded[hit.id] = true
							this.focusTaskId = String(hit.id)
							this.focusId = ''
							this.$nextTick(() => this.scrollToFocus())
						}
					}
					// 列表刷新后，已经展开的那几条要把步骤重新拉一遍（进度可能变了）
					const openIds = Object.keys(this.expanded).filter((id) => this.expanded[id])
					openIds.forEach((id) => {
						if (this.tasks.some((t) => String(t.id) === String(id))) this.fetchSteps(id)
						else delete this.expanded[id]
					})
				} catch (e) {
					if (e && e.needLogin) return
					// 后台刷新失败就保持原样：用户正在看的东西不该突然变成一个错误页
					if (!silent) this.errorMsg = errText(e, '加载失败')
				} finally {
					this.loading = false
					this.fetching = false
				}
			},
			// ===== #083 任务设置（改 / 归档 / 删除）=====
			openTaskSettings(task) {
				this.taskSheetTask = task
				this.taskSheetVisible = true
			},
			onTaskSaved(evt) {
				const data = evt || {}
				if (data.action === 'delete') {
					// 真删：直接从列表里摘掉，不用再打一次请求
					const i = this.tasks.findIndex((t) => t.id === data.id)
					if (i >= 0) this.tasks.splice(i, 1)
					delete this.expanded[data.id]
					delete this.stepsCache[data.id]
					return
				}
				if (data.task) {
					// 改内容 / 归档 / 放回：先就地更新，再按当前筛选重拉（归档了就不该留在"进行中"里）
					this.replaceTask(data.task)
					if (data.action === 'archive' || data.action === 'restore') {
						this.load(true)
					}
				}
			},
			// ===== #080 步骤编辑 =====
			openStepEdit(task, step) {
				this.stepSheetTaskId = task.id
				this.stepSheetStep = step
				this.stepSheetVisible = true
			},
			openStepAdd(task) {
				this.stepSheetTaskId = task.id
				this.stepSheetStep = null
				this.stepSheetVisible = true
			},
			onStepsSaved(task) {
				// 面板保存/删除后都把整条任务的最新状态灌回来（步骤列表 + 进度 + 完成次数）
				if (!task) return
				this.stepsCache[task.id] = task.steps || []
				this.replaceTask(task)
				// 刚加的步骤还没完成 → 保持展开，让用户看到它
				this.expanded[task.id] = true
			},
			async fetchSteps(id) {
				this.stepsLoading[id] = true
				try {
					const task = await get('/tasks/' + id + '/', null, { silent: true })
					this.stepsCache[id] = (task && task.steps) || []
					this.replaceTask(task)
				} catch (e) {
					uni.showToast({ title: errText(e, '步骤加载失败'), icon: 'none' })
				} finally {
					this.stepsLoading[id] = false
				}
			},
			replaceTask(task) {
				if (!task) return
				const i = this.tasks.findIndex((t) => t.id === task.id)
				if (i >= 0) {
					// 保留列表接口里的字段，用详情/保存返回里更新的那几个覆盖（steps 不在列表结构里）
					// #083：标题/频率/配额/时段/目标次数也会被改，都得跟着更新，否则列表还是旧文案
					const merged = Object.assign({}, this.tasks[i], {
						title: task.title,
						frequency_type: task.frequency_type,
						frequency_label: task.frequency_label,
						quota_period: task.quota_period,
						quota_count: task.quota_count,
						target_count: task.target_count,
						timeslot: task.timeslot,
						timeslot_label: task.timeslot_label,
						steps_total: task.steps_total,
						steps_done: task.steps_done,
						progress: task.progress,
						done_count: task.done_count,
						remaining_count: task.remaining_count,
						// #087：今天做完了没有 —— 列表标签、全清判断都看它
						done_today: task.done_today,
						status: task.status
					})
					this.tasks.splice(i, 1, merged)
				}
			},
			// #090：滚到 focus 那条（只有 H5 有 DOM；小程序端列表不长，展开就够了）
			scrollToFocus() {
				// #ifdef H5
				try {
					const el = document.querySelector('.task-focus')
					if (el && el.scrollIntoView) el.scrollIntoView({ block: 'center' })
				} catch (e) {
					// 拿不到就算了，展开本身已经让用户看见步骤了
				}
				// #endif
			},
			toggleExpand(t) {
				if (!t.steps_total) {
					uni.showToast({ title: '这条任务还没写步骤', icon: 'none' })
					return
				}
				const open = !this.expanded[t.id]
				this.expanded[t.id] = open
				if (open && !this.stepsCache[t.id]) this.fetchSteps(t.id)
			},
			async toggleStep(task, step) {
				const id = task.id
				if (this.pending[step.id]) return
				this.pending[step.id] = true

				// 乐观更新：先改本地（勾选框和进度条立刻动），失败再回滚
				const prev = step.is_done
				step.is_done = !prev
				const before = {
					steps_done: task.steps_done,
					status: task.status,
					done_count: task.done_count,
					remaining_count: task.remaining_count,
					done_today: task.done_today
				}
				task.steps_done = this.stepsOf(id).filter((s) => s.is_done).length
				// #087：全勾 ≠ 任务结束。习惯/配额明天还要再做，所以只有一次性任务才动 status
				task.done_today = task.steps_total > 0 && task.steps_done >= task.steps_total
				if (task.frequency_type === 'once') {
					task.status = task.done_today ? 'done' : 'active'
				}

				try {
					const res = await request('/tasks/' + id + '/steps/' + step.id + '/', 'PATCH', { is_done: step.is_done })
					// 用后端返回的整条任务覆盖：done_count / remaining_count / status 都以它为准
					this.stepsCache[id] = (res && res.steps) || this.stepsCache[id]
					this.replaceTask(res)
					// #092：告诉首页「今天变了」——不只靠切页时的 onShow，
					// 谁监听着谁刷新（首页隐藏着也不会白跑）
					uni.$emit('task:changed')
					// #084：勾上的反馈分三层 —— 勾一步不打扰；整张做完说一句；今天全清再放大一句
					if (res && res.change === 'completed') {
						// replaceTask 已把这条并入列表，这里等一拍让 computed 重新算
						this.$nextTick(() => {
							if (this.allDone) {
								uni.showToast({ title: '今天都做完了 🎉 明天见', icon: 'none' })
							} else {
								uni.showToast({ title: '这张做完了', icon: 'none' })
							}
						})
					}
				} catch (e) {
					step.is_done = prev
					task.steps_done = before.steps_done
					task.status = before.status
					task.done_count = before.done_count
					task.remaining_count = before.remaining_count
					task.done_today = before.done_today
					uni.showToast({ title: errText(e, '没保存上，再试一次'), icon: 'none' })
				} finally {
					this.pending[step.id] = false
				}
			}
		}
	}
</script>

<style scoped>
	/* 页面骨架：和 mine.vue / index.vue 一致的「导航 + 撑满的滚动体」布局
	   （这几条每个页面都自己写一遍 —— 全局样式只管外观，不管布局） */
	.page {
		display: flex;
		flex-direction: column;
		height: 100vh;
		background-color: var(--bg);
	}

	.nav {
		flex-shrink: 0;
		background-color: var(--card);
	}

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

	/* #085：导航右侧两个按钮（日程 + 刷新）并排，右侧留白和左边对称 */
	.nav-right {
		display: flex;
		align-items: center;
		margin-right: -12rpx;
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

	.body {
		flex: 1;
		height: 0;
	}

	.wrap {
		padding: 8rpx 32rpx 0;
	}

	/* ===== 今日完成度 ===== */
	.today {
		margin-top: 8rpx;
		padding: 32rpx;
	}

	.today-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}

	.today-label-row {
		display: flex;
		align-items: center;
	}

	/* #084：全清态 —— 小勾徽标 + 「全清了」，和"还没开始"一眼区分 */
	.today-tick {
		width: 34rpx;
		height: 34rpx;
		margin-left: 12rpx;
		border-radius: 50%;
		background-color: var(--accent);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.today-done-text {
		margin-left: 10rpx;
		font-size: 24rpx;
		font-weight: 600;
		color: var(--accent);
	}

	.today-done {
		border-color: var(--accent);
	}

	.today-done .today-sub {
		color: var(--accent);
	}

	.today-label {
		font-size: 26rpx;
		color: var(--text-2);
		letter-spacing: 2rpx;
	}

	.today-num-row {
		display: flex;
		align-items: baseline;
	}

	.today-num {
		font-size: 56rpx;
		line-height: 1;
		font-weight: 600;
		color: var(--text);
		font-variant-numeric: tabular-nums;
	}

	.today-den {
		margin-left: 6rpx;
		font-size: 28rpx;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}

	.today-bar {
		height: 10rpx;
		margin-top: 22rpx;
		border-radius: 999rpx;
		background-color: var(--surface-2, rgba(0, 0, 0, 0.06));
		overflow: hidden;
	}

	.today-bar-in {
		height: 100%;
		border-radius: 999rpx;
		background-color: var(--accent);
		transition: width 320ms cubic-bezier(0.2, 0.8, 0.2, 1);
	}

	.today-sub {
		display: block;
		margin-top: 16rpx;
		font-size: 24rpx;
		color: var(--muted);
	}

	/* ===== 状态筛选 ===== */
	.segs {
		display: flex;
		margin-top: 24rpx;
	}

	.seg {
		box-sizing: border-box;
		min-height: 72rpx;
		padding: 0 24rpx;
		margin-right: 14rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
	}

	.seg-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	.seg-text {
		font-size: 24rpx;
		color: var(--muted);
	}

	.seg-on .seg-text {
		color: var(--accent);
		font-weight: 600;
	}

	/* ===== 分组（t-box 的竖线视觉）===== */
	.group {
		margin-top: 34rpx;
	}

	.g-head {
		display: flex;
		align-items: center;
	}

	.g-rail {
		width: 8rpx;
		height: 26rpx;
		margin-right: 14rpx;
		border-radius: 999rpx;
		background-color: var(--accent);
		opacity: 0.75;
	}

	.g-label {
		font-size: 26rpx;
		font-weight: 600;
		color: var(--text);
		letter-spacing: 2rpx;
	}

	.g-count {
		margin-left: 12rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	/* ===== 任务卡 ===== */
	.task {
		margin-top: 18rpx;
		padding: 24rpx;
	}

	/* #090：从首页点进来的那一条，描边提亮一下，让用户知道"就是这张" */
	.task-focus {
		border-color: var(--accent);
	}

	.task-done {
		opacity: 0.72;
	}

	.t-head {
		display: flex;
		align-items: flex-start;
	}

	.t-icon {
		flex-shrink: 0;
		width: 64rpx;
		height: 64rpx;
		margin-right: 18rpx;
		border-radius: 18rpx;
		background-color: var(--accent-soft);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.t-emoji {
		font-size: 30rpx;
	}

	.t-main {
		flex: 1;
		min-width: 0;
	}

	.t-title-row {
		display: flex;
		align-items: center;
	}

	.t-title {
		flex: 1;
		min-width: 0;
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.t-badge {
		flex-shrink: 0;
		margin-left: 12rpx;
		padding: 2rpx 12rpx;
		border-radius: 999rpx;
		font-size: 20rpx;
		color: var(--success, #3f8f5f);
		border: 2rpx solid var(--success, #3f8f5f);
	}

	/* #087：「今天做完了」不是"这任务结束了" —— 用标志色而不是绿勾，卡片也不变灰 */
	.t-badge-today {
		color: var(--accent);
		border-color: var(--accent);
	}

	.t-meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		margin-top: 8rpx;
	}

	.t-meta-text {
		font-size: 22rpx;
		line-height: 1.5;
		color: var(--muted);
	}

	.t-bar {
		height: 8rpx;
		margin-top: 16rpx;
		border-radius: 999rpx;
		background-color: var(--surface-2, rgba(0, 0, 0, 0.06));
		overflow: hidden;
	}

	.t-bar-in {
		height: 100%;
		border-radius: 999rpx;
		background-color: var(--accent);
		transition: width 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
	}

	.t-caret {
		flex-shrink: 0;
		width: 48rpx;
		text-align: center;
		font-size: 24rpx;
		color: var(--muted);
		line-height: 64rpx;
	}

	/* #083：归档标记（弱化的灰标签，和"已完成"的绿标区分开） */
	.t-archived {
		flex-shrink: 0;
		margin-right: 8rpx;
		padding: 2rpx 12rpx;
		border-radius: 999rpx;
		font-size: 20rpx;
		color: var(--muted);
		border: 2rpx solid var(--border);
	}

	/* #083：「⋯」任务设置入口 —— 44px 触控，别和展开箭头挤成一团 */
	.t-more {
		flex-shrink: 0;
		width: 64rpx;
		height: 64rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 16rpx;
	}

	.t-more-text {
		font-size: 32rpx;
		line-height: 1;
		color: var(--muted);
	}

	/* ===== 步骤 ===== */
	.t-steps {
		margin-top: 18rpx;
		padding-top: 8rpx;
		border-top: 2rpx solid var(--border);
	}

	.t-loading-text {
		font-size: 24rpx;
		color: var(--muted);
	}

	.s {
		display: flex;
		align-items: flex-start;
		padding: 18rpx 0;
	}

	.s + .s {
		border-top: 2rpx solid var(--border);
	}

	.s-box {
		flex-shrink: 0;
		box-sizing: border-box;
		width: 44rpx;
		height: 44rpx;
		margin-right: 18rpx;
		border-radius: 12rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.s-box-on {
		border-color: var(--accent);
		background-color: var(--accent);
	}

	.s-main {
		flex: 1;
		min-width: 0;
	}

	.s-title {
		display: block;
		font-size: 27rpx;
		color: var(--text);
		line-height: 1.45;
	}

	.s-on .s-title {
		color: var(--muted);
		text-decoration: line-through;
	}

	.s-ins {
		display: block;
		margin-top: 4rpx;
		font-size: 23rpx;
		color: var(--muted);
		line-height: 1.5;
	}

	.s-dur {
		flex-shrink: 0;
		margin-left: 14rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	/* #080：每条步骤右侧的编辑入口（44px 触控；点它不会触发打勾） */
	.s-edit {
		flex-shrink: 0;
		width: 64rpx;
		height: 64rpx;
		margin-left: 10rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 16rpx;
	}

	/* #080：加一步 —— 虚线框，和"＋ 添加步骤"的既有习惯一致 */
	.s-add {
		box-sizing: border-box;
		margin-top: 16rpx;
		min-height: 84rpx;
		border-radius: 16rpx;
		border: 2rpx dashed var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.s-add-text {
		font-size: 25rpx;
		color: var(--muted);
	}

	/* ===== 状态页 / 骨架 ===== */
	.state {
		padding: 90rpx 20rpx;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.state-mark {
		width: 108rpx;
		height: 108rpx;
		border-radius: 54rpx;
		background-color: var(--surface-2, rgba(0, 0, 0, 0.05));
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.state-title {
		margin-top: 26rpx;
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
	}

	.state-desc {
		margin-top: 12rpx;
		font-size: 24rpx;
		color: var(--muted);
		text-align: center;
		line-height: 1.6;
	}

	.state-btn {
		margin-top: 30rpx;
		height: 84rpx;
		padding: 0 44rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 27rpx;
	}

	/* #089：未排期出口 —— 一条细栏，不抢任务卡的视觉 */
	.unsched-bar {
		margin: 0 0 18rpx;
		padding: 18rpx 22rpx;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border: 1px dashed var(--border);
		border-radius: 16rpx;
	}

	.unsched-text {
		font-size: 24rpx;
		color: var(--text-2);
	}

	.unsched-go {
		font-size: 24rpx;
		color: var(--accent);
		font-weight: 600;
	}

	.sk-line {
		height: 24rpx;
		margin: 14rpx 0;
		border-radius: 8rpx;
		background-color: var(--surface-2, rgba(0, 0, 0, 0.06));
	}

	.sk-line-lg {
		width: 55%;
		height: 30rpx;
	}

	.bar-space {
		height: 60rpx;
	}

	.fab {
		display: none;
	}

	/* ===== 电脑端 ===== */
	@media (min-width: 768px) {
		.unsched-bar {
			max-width: 820px;
			margin: 0 auto 18px;
		}

		.wrap {
			max-width: 860px;
			margin: 0 auto;
			padding: 16px 24px 0;
		}
		.today {
			margin-top: 8px;
			padding: 22px 24px;
			border-radius: var(--r-card);
		}
		.today-label {
			font-size: 13px;
		}
		.today-num {
			font-size: 34px;
		}
		.today-den {
			font-size: 14px;
		}
		.today-bar {
			height: 6px;
			margin-top: 14px;
		}
		.today-sub {
			font-size: 12px;
			margin-top: 10px;
		}
		.today-tick {
			width: 18px;
			height: 18px;
			margin-left: 8px;
		}
		.today-done-text {
			font-size: 12px;
			margin-left: 6px;
		}
		.segs {
			margin-top: 18px;
		}
		.seg {
			min-height: 38px;
			padding: 0 16px;
			margin-right: 10px;
			border-width: 1px;
			cursor: pointer;
		}
		.seg-text {
			font-size: 13px;
		}
		.group {
			margin-top: 26px;
		}
		.g-label {
			font-size: 13px;
		}
		.task {
			margin-top: 12px;
			padding: 18px;
		}
		.t-head {
			cursor: pointer;
		}
		.t-icon {
			width: 36px;
			height: 36px;
			margin-right: 12px;
			border-radius: 10px;
		}
		.t-title {
			font-size: 15px;
		}
		.t-meta-text {
			font-size: 12px;
		}
		.t-bar {
			height: 5px;
			margin-top: 10px;
		}
		.t-caret {
			width: 28px;
			line-height: 36px;
			font-size: 12px;
		}
		.t-archived {
			font-size: 11px;
			padding: 1px 8px;
			border-width: 1px;
		}
		.t-more {
			width: 32px;
			height: 32px;
			border-radius: 8px;
			cursor: pointer;
		}
		.t-more-text {
			font-size: 18px;
		}
		.s {
			padding: 12px 0;
			cursor: pointer;
		}
		.s-box {
			width: 22px;
			height: 22px;
			margin-right: 12px;
			border-radius: 6px;
			border-width: 1px;
		}
		.s-title {
			font-size: 14px;
		}
		.s-ins {
			font-size: 12px;
		}
		.s-dur {
			font-size: 12px;
		}
		.s-edit {
			width: 32px;
			height: 32px;
			margin-left: 6px;
			border-radius: 8px;
			cursor: pointer;
		}
		.s-add {
			margin-top: 12px;
			min-height: 42px;
			border-radius: 8px;
			border-width: 1px;
			cursor: pointer;
		}
		.s-add-text {
			font-size: 13px;
		}
		.state-btn {
			height: 42px;
			font-size: 14px;
			cursor: pointer;
		}
		.fab {
			position: fixed;
			right: 32px;
			bottom: 32px;
			width: 56px;
			height: 56px;
			border-radius: 28px;
			background-color: var(--surface);
			border: 1px solid var(--border);
			box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
			display: flex;
			align-items: center;
			justify-content: center;
			cursor: pointer;
		}
	}
</style>
