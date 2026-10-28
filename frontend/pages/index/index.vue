<template>
	<view class="page">
		<!-- pages.json 里 navigationStyle=custom，标题栏要自己画 -->
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-brand">
					<text class="nav-title">行动锚</text>
					<text class="nav-sub">{{ dateText }}</text>
				</view>
				<!-- #091：模板应急的眼到即到 —— 搜索回到首页右上，和「我的」并排 -->
				<view class="nav-acts">
					<view class="nav-search" hover-class="hover-dim" @click="goSearch">
						<view class="nav-search-pill"><app-icon name="magnifying-glass" :size="17" tone="muted" /></view>
					</view>
					<view class="nav-mine" hover-class="hover-dim" @click="goMine">
						<view class="nav-mine-pill" :style="pillStyle"><text class="nav-mine-text">我的</text></view>
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
				<!-- 今天：这一屏的主角。「今天 x/y」+ 步骤进度条 -->
				<view class="today theme-card" :class="{ 'today-done': allDone }">
					<view class="today-head">
						<view class="today-left">
							<view class="today-label-row">
								<text class="today-label">今天</text>
								<view v-if="allDone" class="today-tick">
									<app-icon name="check" :size="12" tone="inverse" />
								</view>
								<text v-if="allDone" class="today-done-text">全清了</text>
							</view>
						</view>
						<view class="today-num-row">
							<text class="today-num">{{ doneCount }}</text>
							<text class="today-den">/{{ tasks.length }}</text>
						</view>
					</view>
					<view class="today-bar">
						<view class="today-bar-in" :style="{ width: stepPct + '%' }"></view>
					</view>
					<text class="today-sub">{{ todaySub }}</text>
				</view>

				<!-- 骨架 -->
				<view v-if="loading && !tasks.length" class="groups">
					<view v-for="i in 2" :key="i" class="task theme-card">
						<view class="sk-line sk-line-lg"></view>
						<view class="sk-line"></view>
					</view>
				</view>

				<!-- 未登录：首页是可以看的，但"今天"得登录才存得住 -->
				<view v-else-if="needLogin" class="state">
					<view class="state-mark"><app-icon name="tray" :size="26" tone="muted" /></view>
					<text class="state-title">登录一下，你的今天才存得住</text>
					<text class="state-desc">登进来，今天要做的就在这一屏；没登录也能先看看下面这几个。</text>
					<view class="state-btn btn-accent" hover-class="hover-dim" @click="goLogin"><text>登录</text></view>
				</view>

				<!-- 错误 -->
				<view v-else-if="errorMsg && !tasks.length" class="state">
					<view class="state-mark"><app-icon name="cloud-slash" :size="26" tone="muted" /></view>
					<text class="state-title">没连上</text>
					<text class="state-desc">{{ errorMsg }}</text>
					<view class="state-btn btn-accent" hover-class="hover-dim" @click="load()"><text>再试一次</text></view>
				</view>

				<!-- 今天的任务：上午 / 下午 / 夜晚 三段（没有任务的时段不显示） -->
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
						:class="{ 'task-focus': String(t.id) === focusId }"
						:hover-class="'hover-dim'"
						@click="openTask(t)"
					>
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
								<text v-if="doneToday(t)" class="t-badge t-badge-today">今天做完了</text>
							</view>
							<text class="t-meta">{{ metaText(t) }}</text>
							<view class="t-bar">
								<view class="t-bar-in" :style="{ width: taskPct(t) + '%' }"></view>
							</view>
						</view>
						<text class="t-caret">›</text>
					</view>
				</view>

				<!-- 空态：给 3 个推荐（不做"空白页 + 一个按钮"） -->
				<view v-if="!loading && !needLogin && !errorMsg && !tasks.length" class="empty">
					<view class="empty-mark"><app-icon name="tray" :size="26" tone="muted" /></view>
					<text class="empty-title">{{ emptyTitle }}</text>
					<text class="empty-desc">{{ emptyDesc }}</text>
					<view
						v-for="p in recommendations"
						:key="p.id"
						class="rec theme-card"
						hover-class="hover-dim"
						@click="addRec(p)"
					>
						<view class="rec-icon">
							<app-icon v-if="p.icon_key" :name="p.icon_key" :size="20" tone="accent" />
							<text v-else class="t-emoji">{{ p.icon || '🧠' }}</text>
						</view>
						<view class="rec-body">
							<text class="rec-title">{{ p.title }}</text>
							<text v-if="p.tagline" class="rec-tagline">{{ p.tagline }}</text>
							<text class="rec-meta">{{ p.step_count }} 步 · {{ p.category }}</text>
						</view>
						<view class="rec-add">
							<text class="rec-add-text">{{ addingId === p.id ? '加着…' : '＋ 今天做' }}</text>
						</view>
					</view>
				</view>

				<!-- 模板库入口：模板列表搬走了，但门一直开着 -->
				<view class="lib-entry theme-card" hover-class="hover-dim" @click="goLibrary">
					<view class="lib-icon"><app-icon name="list-checks" :size="19" tone="accent" /></view>
					<view class="lib-body">
						<text class="lib-title">模板库</text>
						<text class="lib-sub">{{ libSub }}</text>
					</view>
					<text class="lib-caret">›</text>
				</view>

				<view class="safe-bottom"></view>
			</view>
		</scroll-view>

		<!-- #040 新手引导（两层，H5 专属）；#090 起三步都指着"今天"这一屏 -->
		<!-- #ifdef H5 -->
		<onboarding-intro :visible="introVisible" @done="onIntroDone" />
		<onboarding-tour :visible="tourVisible" :steps="tourSteps" @done="onTourDone" />
		<!-- #endif -->
	</view>
</template>

<script>
	import { get, post, errText } from '@/api/request.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { ENABLE_UGC, IS_H5 } from '@/utils/config.js'
	import AppIcon from '@/components/app-icon/app-icon.vue'
	// #ifdef H5
	import OnboardingIntro from '@/components/onboarding-intro/onboarding-intro.vue'
	import OnboardingTour from '@/components/onboarding-tour/onboarding-tour.vue'
	// #endif
	import { isIntroDone, isTourDone, markIntroDone, markTourDone } from '@/utils/onboarding.js'

	// 与后端 tasks.models.TIMESLOT_ORDER 对齐；#090 首页按"上午/下午/夜晚"三段归并
	const SLOT_LABELS = {
		morning: '早上',
		noon: '中午',
		afternoon: '下午',
		evening: '晚上',
		night: '睡前'
	}
	// 一天三段：上午 = 早上+中午、下午 = 下午、夜晚 = 晚上+睡前（其余自定义时段单列一段）
	const BUCKETS = [
		{ key: 'am', label: '上午', slots: ['morning', 'noon'] },
		{ key: 'pm', label: '下午', slots: ['afternoon'] },
		{ key: 'night', label: '夜晚', slots: ['evening', 'night'] }
	]
	const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

	export default {
		// #ifdef H5
		components: { OnboardingIntro, OnboardingTour, AppIcon },
		// #endif
		// #ifndef H5
		components: { AppIcon },
		// #endif
		data() {
			return {
				statusBarHeight: 20,
				nav: {},
				enableUgc: ENABLE_UGC,
				// #040 新手引导：全屏引导（讲概念）→ 首页蒙层高亮（教操作）
				introVisible: false,
				tourVisible: false,
				// 今天的任务（后端唯一口径：active 且 plan_date=今天）
				tasks: [],
				// 有没排日子的任务时，空态和底部入口要提一句"任务没丢"
				unscheduled: 0,
				// 三个推荐（热门前 3，公共接口，未登录也能拿）
				recommendations: [],
				addingId: 0,
				loading: false,
				refreshing: false,
				// #092：首屏拉过一次之后，每次重新显示都静默刷新（有旧数据就先显示旧数据）
				loadedOnce: false,
				fetching: false,
				// #092 兜底监听（H5）—— 存起来是为了卸载时能摘掉
				onPopState: null,
				onVisible: null,
				needLogin: false,
				errorMsg: '',
				// 从任务页跳回来时高亮哪一张（点首页卡片进详情用）
				focusId: ''
			}
		},
		onLoad(options) {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight)
			this.focusId = (options && options.focus) ? String(options.focus) : ''
			// #092：任务页勾了一步会发这个事件 —— 首页不管当时在不在前台都能知道
			uni.$on('task:changed', this.onTaskChanged)
			this.load()
			this.loadRecommendations()
		},
		// #092：从任务页/模板库/详情页回来，重新拉一次今天的任务，数字和列表都跟着变。
		// 不看 tasks.length —— 今天空着（全做完 / 没排期）返回时也得刷新，否则空态永远停在旧的。
		onShow() {
			if (this.loadedOnce) this.load(true)
		},
		onUnload() {
			uni.$off('task:changed', this.onTaskChanged)
		},
		mounted() {
			// #092 兜底：有的浏览器「返回上一页」不走 uni 的 onShow（history 回退、切后台再回前台），
			// 补两个原生监听，保证回来时一定会重新拉一次。
			// #ifdef H5
			this.onPopState = () => {
				if (this.loadedOnce) this.load(true)
			}
			this.onVisible = () => {
				if (document.visibilityState === 'visible' && this.loadedOnce) this.load(true)
			}
			window.addEventListener('popstate', this.onPopState)
			document.addEventListener('visibilitychange', this.onVisible)
			// #endif
		},
		beforeUnmount() {
			// #ifdef H5
			if (this.onPopState) window.removeEventListener('popstate', this.onPopState)
			if (this.onVisible) document.removeEventListener('visibilitychange', this.onVisible)
			// #endif
		},
		onReady() {
			if (!IS_H5) return
			if (!isIntroDone()) this.introVisible = true
			else if (!isTourDone()) this.startTour()
		},
		computed: {
			pillStyle() {
				return this.nav && this.nav.capsuleHeight ? { height: this.nav.capsuleHeight + 'px' } : {}
			},
			dateText() {
				const d = new Date()
				return `${d.getMonth() + 1}月${d.getDate()}日 ${WEEKDAYS[d.getDay()]}`
			},
			// 今天做完了几件（不是截止状态 —— 一次性任务做完才算结束）
			doneCount() {
				return this.tasks.filter((t) => this.doneToday(t)).length
			},
			stepSum() {
				let done = 0
				let total = 0
				this.tasks.forEach((t) => {
					done += t.today_steps_done || 0
					total += t.steps_total || 0
				})
				return { done, total }
			},
			stepPct() {
				const s = this.stepSum
				if (!s.total) return 0
				return Math.round((s.done / s.total) * 100)
			},
			// 今天的进度条只算今天（#087：昨天的完成不该带到今天）
			allDone() {
				return this.tasks.length > 0 && this.doneCount === this.tasks.length
			},
			todaySub() {
				if (this.needLogin) return '登录之后，这一屏就是你的今天'
				if (!this.tasks.length) {
					if (this.unscheduled > 0) return `还有 ${this.unscheduled} 件没排日子`
					return '还没开始，不急'
				}
				if (this.allDone) return '今天都做完了 🎉 明天见'
				const s = this.stepSum
				if (!s.total) return '这几件还没写步骤，点开加一步'
				if (!s.done) return `今天 0/${s.total} 步，慢慢来`
				return `${s.done}/${s.total} 步，慢慢来`
			},
			emptyTitle() {
				return this.unscheduled > 0 ? '今天还空着' : '今天还没有安排'
			},
			emptyDesc() {
				if (this.unscheduled > 0) {
					return `你有 ${this.unscheduled} 件还没排日子。挑一件放到今天，或者从下面直接开始。`
				}
				return '从下面挑一件，点一下它今天就在这儿了。'
			},
			libSub() {
				return this.tasks.length ? '再做点别的，去库里挑' : '现成的做法都在这儿'
			},
			// 引导的三步跟着首页内容走：有任务 → 指向任务卡；没任务 → 指向推荐
			tourSteps() {
				const steps = [{ sel: '.today', text: '今天要做几件，这儿写着。做完数字就变', pierce: 'stay' }]
				if (this.tasks.length) {
					steps.push({ sel: '.group .task', text: '点一张进去，步骤在那儿一条条勾', pierce: 'end' })
				} else if (this.recommendations.length) {
					steps.push({ sel: '.rec', text: '没想法就从这儿挑一件，点一下就是今天的任务', pierce: 'end' })
				}
				steps.push({ sel: '.lib-entry', text: '想再多点选择，模板库里还有一堆，挑一件就成', pierce: 'end' })
				return steps
			},
			// 按三段归并；空段的组不出现在页面上（spec「有任务的时段才显示」）
			groups() {
				const out = []
				BUCKETS.forEach((b) => {
					const list = this.tasks.filter((t) => b.slots.indexOf(t.timeslot) >= 0)
					if (list.length) out.push({ key: b.key, label: b.label, tasks: list })
				})
				// 自定义时段（后端 timeslot 是自由字符串，允许用户自己填）单独兜一段
				const known = BUCKETS.reduce((acc, b) => acc.concat(b.slots), [])
				const rest = this.tasks.filter((t) => !t.timeslot || known.indexOf(t.timeslot) < 0)
				if (rest.length) out.push({ key: 'other', label: '没定时段', tasks: rest })
				return out
			}
		},
		methods: {
			startTour() {
				this.tourVisible = true
			},
			onIntroDone() {
				this.introVisible = false
				markIntroDone()
				if (!isTourDone()) this.startTour()
			},
			onTourDone() {
				this.tourVisible = false
				markTourDone()
			},
			// #092：silent=true 是"后台刷新"——旧数据先留着，请求失败也不把画面换成错误页，
			// 只有首屏（非 silent）才让用户看到错误和「再试一次」。
			async load(silent) {
				if (this.fetching) return
				this.fetching = true
				if (!silent) this.loading = true
				try {
					const data = await get('/tasks/', { today: 1 }, { silent: true })
					this.needLogin = false
					this.errorMsg = ''
					this.tasks = (data && data.items) || []
					this.unscheduled = (data && data.unscheduled) || 0
					this.loadedOnce = true
				} catch (e) {
					// 没登录不算错误：首页本来就该能看，只是没有"今天"
					if (e && e.needLogin) {
						this.needLogin = true
						this.tasks = []
						this.unscheduled = 0
						this.loadedOnce = true
					} else if (!silent) {
						this.errorMsg = errText(e, '加载失败')
					}
				} finally {
					this.loading = false
					this.fetching = false
				}
			},
			// 推荐位：热门前 3（/quick/ 是公开接口，未登录也能拿）
			async loadRecommendations() {
				try {
					const data = await get('/quick/', { sort: 'hot', page: 1, page_size: 3 }, { silent: true })
					this.recommendations = (data && data.results) || []
				} catch (e) {
					this.recommendations = []
				}
			},
			// 点推荐 → 直接变成今天的任务（后端不传 plan_date 就是今天）
			async addRec(p) {
				if (!p || this.addingId) return
				if (this.needLogin) {
					uni.navigateTo({ url: '/pages/login/login' })
					return
				}
				this.addingId = p.id
				try {
					// 模板本身没有时段，按现在几点放到对应段里 —— 不然新加进来的任务会落进
					// 「没定时段」那一组，看着像没归类
					const h = new Date().getHours()
					const slot = h < 11 ? 'morning' : h < 17 ? 'afternoon' : 'evening'
					await post('/tasks/', { pattern_id: p.id, timeslot: slot })
					uni.showToast({ title: '好，今天做一次试试', icon: 'none' })
					await this.load(true)
				} catch (e) {
					uni.showToast({ title: errText(e, '没加上，再试一次'), icon: 'none' })
				} finally {
					this.addingId = 0
				}
			},
			doneToday(t) {
				return !!t.done_today
			},
			taskPct(t) {
				if (!t.steps_total) return t.done_today ? 100 : 0
				return Math.round(((t.today_steps_done || 0) / t.steps_total) * 100)
			},
			// 一张卡只留必要信息：进度 + 频率/剩余（多了在窄屏上会折行折断）
			metaText(t) {
				const seg = []
				seg.push(t.steps_total ? `${t.today_steps_done || 0}/${t.steps_total} 步` : '还没写步骤')
				if (t.remaining_count === null || t.remaining_count === undefined) {
					if (t.frequency_type === 'habit') seg.push('想做就做')
				} else if (t.remaining_count === 0) {
					seg.push('这周期做够了')
				} else if (t.frequency_type === 'once') {
					seg.push('还没做')
				} else {
					seg.push(`还剩 ${t.remaining_count} 次`)
				}
				return seg.join(' · ')
			},
			// 点卡 → 任务页（在那儿打勾）；带上 focus，让那一条自动展开
			openTask(t) {
				uni.navigateTo({ url: '/pages/tasks/tasks?focus=' + t.id })
			},
			// #092：任务页那边勾了一步 → 事件到了就静默重拉（页面隐藏着也没关系，回来就是新的）
			onTaskChanged() {
				if (this.loadedOnce) this.load(true)
			},
			async onRefresh() {
				this.refreshing = true
				await Promise.all([this.load(true), this.loadRecommendations()])
				this.refreshing = false
			},
			goLibrary() {
				uni.navigateTo({ url: '/pages/library/library' })
			},
			goSearch() {
				uni.navigateTo({ url: '/pages/search/search' })
			},
			goMine() {
				uni.navigateTo({ url: '/pages/mine/mine' })
			},
			goLogin() {
				uni.navigateTo({ url: '/pages/login/login' })
			}
		}
	}
</script>

<style scoped>
	/* 页面骨架：每个页面自己写一遍（全局样式只管外观，不管布局） */
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
		padding: 0 24rpx 0 32rpx;
	}

	.nav-brand {
		display: flex;
		align-items: baseline;
		min-width: 0;
	}

	.nav-title {
		font-size: 40rpx;
		font-weight: 700;
		color: var(--text);
	}

	.nav-sub {
		margin-left: 16rpx;
		font-size: 24rpx;
		color: var(--muted);
		white-space: nowrap;
	}

	.nav-acts {
		flex-shrink: 0;
		display: flex;
		align-items: center;
	}

	/* 搜索：外层 88rpx = 44px 热区（拇指够得到），内层是和「我的」同高的胶囊 */
	.nav-search {
		width: 88rpx;
		height: 88rpx;
		margin-right: 12rpx;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.nav-search-pill {
		width: 64rpx;
		height: 64rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* 「我的」胶囊：外层 88rpx = 44px 触控目标，内层跟微信胶囊等高 */
	.nav-mine {
		flex-shrink: 0;
		height: 88rpx;
		display: flex;
		align-items: center;
	}

	.nav-mine-pill {
		height: 64rpx;
		padding: 0 24rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.nav-mine-text {
		font-size: 24rpx;
		color: var(--text-2);
	}

	.body {
		flex: 1;
		height: 0;
	}

	.wrap {
		padding: 8rpx 32rpx 0;
	}

	/* ===== 今天 ===== */
	.today {
		margin-top: 8rpx;
		padding: 32rpx;
	}

	.today-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.today-left {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.today-label-row {
		display: flex;
		align-items: center;
	}

	.today-label {
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
		letter-spacing: 2rpx;
	}

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

	.today-date {
		margin-top: 8rpx;
		font-size: 24rpx;
		color: var(--muted);
	}

	.today-num-row {
		display: flex;
		align-items: baseline;
	}

	.today-num {
		font-size: 60rpx;
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
		margin-top: 24rpx;
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

	.today-done {
		border-color: var(--accent);
	}

	.today-done .today-sub {
		color: var(--accent);
	}

	/* ===== 分组 ===== */
	.group {
		margin-top: 32rpx;
	}

	.g-head {
		display: flex;
		align-items: center;
		margin-bottom: 16rpx;
	}

	.g-rail {
		width: 6rpx;
		height: 26rpx;
		margin-right: 12rpx;
		border-radius: 3rpx;
		background-color: var(--accent);
	}

	.g-label {
		font-size: 26rpx;
		font-weight: 600;
		color: var(--text-2);
	}

	.g-count {
		margin-left: 10rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	/* ===== 任务卡 ===== */
	.task {
		display: flex;
		align-items: center;
		margin-bottom: 16rpx;
		padding: 26rpx 28rpx;
	}

	.task-focus {
		border-color: var(--accent);
	}

	.t-icon {
		flex-shrink: 0;
		width: 64rpx;
		height: 64rpx;
		margin-right: 20rpx;
		border-radius: 16rpx;
		background-color: var(--surface-2);
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
		border: 2rpx solid var(--border);
		font-size: 20rpx;
		color: var(--muted);
	}

	.t-badge-today {
		border-color: var(--accent);
		color: var(--accent);
	}

	.t-meta {
		display: block;
		margin-top: 8rpx;
		font-size: 22rpx;
		color: var(--muted);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.t-bar {
		height: 6rpx;
		margin-top: 14rpx;
		border-radius: 999rpx;
		background-color: var(--surface-2, rgba(0, 0, 0, 0.06));
		overflow: hidden;
	}

	.t-bar-in {
		height: 100%;
		border-radius: 999rpx;
		background-color: var(--accent);
		transition: width 320ms cubic-bezier(0.2, 0.8, 0.2, 1);
	}

	.t-caret {
		flex-shrink: 0;
		margin-left: 12rpx;
		font-size: 36rpx;
		color: var(--muted);
	}

	/* ===== 空态 / 错误 / 未登录 ===== */
	.state,
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 64rpx 16rpx 32rpx;
	}

	.state-mark,
	.empty-mark {
		width: 96rpx;
		height: 96rpx;
		border-radius: 50%;
		background-color: var(--surface-2);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.state-title,
	.empty-title {
		margin-top: 24rpx;
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
		text-align: center;
	}

	.state-desc,
	.empty-desc {
		margin-top: 12rpx;
		font-size: 24rpx;
		line-height: 1.6;
		color: var(--muted);
		text-align: center;
	}

	.state-btn {
		margin-top: 28rpx;
		min-height: 88rpx;
		padding: 0 40rpx;
		border-radius: 999rpx;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* ===== 推荐卡 ===== */
	.rec {
		display: flex;
		align-items: center;
		width: 100%;
		box-sizing: border-box;
		margin-top: 16rpx;
		padding: 24rpx 24rpx;
		text-align: left;
	}

	.rec-icon {
		flex-shrink: 0;
		width: 64rpx;
		height: 64rpx;
		margin-right: 18rpx;
		border-radius: 16rpx;
		background-color: var(--surface-2);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.rec-body {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}

	.rec-title {
		font-size: 28rpx;
		font-weight: 600;
		color: var(--text);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.rec-tagline {
		margin-top: 4rpx;
		font-size: 22rpx;
		color: var(--text-2);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.rec-meta {
		margin-top: 6rpx;
		font-size: 20rpx;
		color: var(--muted);
	}

	.rec-add {
		flex-shrink: 0;
		margin-left: 12rpx;
		padding: 12rpx 20rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--accent);
	}

	.rec-add-text {
		font-size: 22rpx;
		color: var(--accent);
	}

	/* ===== 模板库入口 ===== */
	.lib-entry {
		display: flex;
		align-items: center;
		margin-top: 32rpx;
		padding: 26rpx 28rpx;
	}

	.lib-icon {
		flex-shrink: 0;
		width: 64rpx;
		height: 64rpx;
		margin-right: 20rpx;
		border-radius: 16rpx;
		background-color: var(--surface-2);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.lib-body {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}

	.lib-title {
		font-size: 28rpx;
		font-weight: 600;
		color: var(--text);
	}

	.lib-sub {
		margin-top: 6rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	.lib-caret {
		flex-shrink: 0;
		font-size: 34rpx;
		color: var(--muted);
	}

	.safe-bottom {
		height: calc(48rpx + env(safe-area-inset-bottom));
	}

	/* ===== 骨架 ===== */
	.sk-line {
		height: 16rpx;
		margin-top: 12rpx;
		border-radius: 8rpx;
		background-color: var(--surface-2);
	}

	.sk-line-lg {
		width: 50%;
		height: 22rpx;
		margin-top: 0;
	}

	/* ===== 网页版：内容居中、字号放大一档（≥768px） ===== */
	@media (min-width: 768px) {
		.wrap {
			max-width: 820px;
			margin: 0 auto;
			padding-top: 16px;
			box-sizing: border-box;
		}

		.nav-inner {
			max-width: 820px;
			margin: 0 auto;
			padding: 0 8px;
		}

		.nav-title {
			font-size: 22px;
		}

		.nav-sub {
			font-size: 13px;
		}

		.today {
			padding: 22px;
		}

		.today-num {
			font-size: 34px;
		}

		.t-title {
			font-size: 15px;
		}

		.rec-title,
		.lib-title {
			font-size: 15px;
		}
	}
</style>
