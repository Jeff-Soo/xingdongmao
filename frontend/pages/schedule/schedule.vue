<template>
	<view class="page">
		<!-- 导航 -->
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">日程</text>
				<view class="nav-btn nav-btn-ghost" hover-class="hover-dim" @click="goToday">
					<text class="nav-today">今天</text>
				</view>
			</view>
		</view>

		<!-- 尺度：日 / 周 / 月 / 季（#085：默认"周"） -->
		<view class="scales">
			<view class="scales-inner">
				<view
					v-for="s in scales"
					:key="s.key"
					class="scale"
					:class="{ 'scale-on': scale === s.key }"
					hover-class="hover-dim"
					@click="switchScale(s.key)"
				>
					<text class="scale-text">{{ s.label }}</text>
				</view>
				<view class="scale-hint">
					<text class="scale-hint-text">{{ rangeHint }}</text>
				</view>
			</view>
		</view>

		<!-- 横向滚轴：一格 = 一天/一周/一月/一季 -->
		<view class="rail-wrap">
			<view v-if="W >= 768" class="rail-arrow rail-prev" hover-class="hover-dim" @click="scrollBy(-1)">
				<text class="rail-arrow-text">‹</text>
			</view>
			<scroll-view
				class="rail"
				scroll-x
				:scroll-left="railScroll"
				:scroll-with-animation="true"
				show-scrollbar="false"
				@scroll="onRailScroll"
			>
				<view class="rail-inner">
					<view
						v-for="c in cells"
						:key="c.key"
						class="cell"
						:class="{ 'cell-on': selectedKey === c.key, 'cell-today': c.isToday, 'cell-empty': !c.count }"
						hover-class="hover-dim"
						@click="selectCell(c)"
					>
						<text class="cell-title">{{ c.title }}</text>
						<text class="cell-sub">{{ c.sub }}</text>
						<view class="cell-bar">
							<view class="cell-bar-in" :style="{ width: c.pct + '%' }"></view>
						</view>
						<text class="cell-count">{{ c.count ? c.done + '/' + c.count : '空着' }}</text>
					</view>
				</view>
			</scroll-view>
			<view v-if="W >= 768" class="rail-arrow rail-next" hover-class="hover-dim" @click="scrollBy(1)">
				<text class="rail-arrow-text">›</text>
			</view>
		</view>

		<scroll-view class="body" scroll-y>
			<view class="wrap">
				<!-- 选中的那一格展开：这天的任务（按时段分组） -->
				<view class="panel">
					<view class="panel-head">
						<text class="panel-title">{{ panelTitle }}</text>
						<text class="panel-sub">{{ panelSub }}</text>
					</view>

					<view v-if="loading" class="state">
						<view class="state-mark"><app-icon name="circle-notch" :size="26" tone="muted" /></view>
						<text class="state-title">正在翻日程…</text>
					</view>

					<view v-else-if="error" class="state">
						<view class="state-mark"><app-icon name="cloud-slash" :size="26" tone="muted" /></view>
						<text class="state-title">没连上</text>
						<view class="state-btn btn-accent" hover-class="hover-dim" @click="load(true)"><text>再试一次</text></view>
					</view>

					<view v-else-if="!panelGroups.length" class="state">
						<view class="state-mark"><app-icon name="calendar" :size="26" tone="muted" /></view>
						<text class="state-title">{{ emptyTitle }}</text>
						<text class="state-desc">挑一件小事放进来就好，三十秒也算。下面「还没排期」里的，点一下就能排进来。</text>
						<view class="state-btn btn-accent" hover-class="hover-dim" @click="goLibrary"><text>去挑一件小事</text></view>
					</view>

					<view v-for="g in panelGroups" v-else :key="g.key" class="group">
						<view class="g-head">
							<view class="g-rail"></view>
							<text class="g-label">{{ g.label }}</text>
							<text class="g-count">{{ g.tasks.length }}</text>
						</view>
						<view
							v-for="t in g.tasks"
							:key="t.id"
							class="t-row theme-card"
							:class="{ 't-done': isDone(t) }"
							hover-class="hover-dim"
							@click="openTask(t)"
						>
							<view class="t-main">
								<text class="t-title">{{ t.title }}</text>
								<view class="t-bar"><view class="t-bar-in" :style="{ width: pctOf(t) + '%' }"></view></view>
							</view>
							<text class="t-pct">{{ pctOf(t) }}%</text>
							<text v-if="isDone(t)" class="t-badge">已完成</text>
						</view>
					</view>
				</view>

				<!-- 未排期：plan_date 空的任务，点一下排到某天（#085 ④ 点选） -->
				<view class="unsched">
					<view class="unsched-head" hover-class="hover-dim" @click="toggleUnsched">
						<text class="unsched-title">还没排期</text>
						<text class="unsched-count">{{ unscheduled.length ? unscheduled.length + ' 件' : '' }}</text>
						<text v-if="unscheduled.length" class="unsched-act">{{ unschedOpen ? '收起' : '排一下' }}</text>
					</view>
					<text v-if="!unscheduled.length" class="unsched-none">都排好了，没有落下的</text>
					<view v-else-if="unschedOpen" class="unsched-list">
						<view
							v-for="t in unscheduled"
							:key="t.id"
							class="unsched-item"
							hover-class="hover-dim"
							@click="openAssign(t)"
						>
							<text class="unsched-item-title">{{ t.title }}</text>
							<text class="unsched-item-act">排到某天 ›</text>
						</view>
					</view>
				</view>

				<!-- 季档：当季推荐（接口先留位，没数据就不显示） -->
				<view v-if="scale === 'season' && seasonSuggestions.length" class="season">
					<view class="season-head">
						<text class="season-title">{{ seasonTitle }}可以试试</text>
					</view>
					<view
						v-for="p in seasonSuggestions"
						:key="p.id"
						class="season-item theme-card"
						hover-class="hover-dim"
						@click="goPattern(p)"
					>
						<text class="season-item-title">{{ p.title }}</text>
						<text class="season-item-tag">{{ p.step_count }} 步</text>
					</view>
				</view>

				<view class="bar-space"></view>
			</view>
		</scroll-view>

		<!-- 排期面板：点选某天（今天/明天/…/自己选） -->
		<view v-if="assignVisible" class="mask" @click="closeAssign">
			<view class="sheet" @click.stop>
				<view class="sheet-head">
					<text class="sheet-title">排到哪天</text>
					<text class="sheet-close" hover-class="hover-dim" @click="closeAssign">✕</text>
				</view>
				<text class="sheet-hint">「{{ assignTask && assignTask.title }}」——挑一天，那天就能看见它。</text>
				<view class="chips">
					<view
						v-for="(d, i) in dayChips"
						:key="d.key"
						class="chip"
						:class="{ 'chip-on': assignPick === d.key }"
						hover-class="hover-dim"
						@click="assignPick = d.key"
					>
						<text class="chip-text">{{ d.label }}</text>
					</view>
				</view>
				<view class="assign-more">
					<picker mode="date" :value="assignPick || todayKey" @change="onPickDate">
						<text class="assign-more-text">自己选一天 ›</text>
					</picker>
				</view>
				<view class="sheet-acts">
					<view class="btn-ghost sheet-act" hover-class="hover-dim" @click="closeAssign"><text>再想想</text></view>
					<view class="btn-accent sheet-act sheet-act-main" hover-class="hover-dim" @click="confirmAssign">
						<text>{{ submitting ? '排着呢…' : '就这天' }}</text>
					</view>
				</view>
			</view>
		</view>
	</view>
</template>

<script>
	import { get, request, errText } from '@/api/request.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { requireLogin } from '@/utils/token.js'
	import {
		SEASONS, addDays, dateKey, parseDateKey, seasonOf, seasonKeyOf, seasonLabel,
		shiftSeason, fetchSeasonSuggestions
	} from '@/utils/season.js'
	import AppIcon from '@/components/app-icon/app-icon.vue'

	const WEEK_CN = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
	// 与后端 tasks.models.TIMESLOT_ORDER 一致
	const SLOT_ORDER = ['morning', 'noon', 'afternoon', 'evening', 'night']
	const SLOT_LABELS = {
		morning: '早上', noon: '中午', afternoon: '下午', evening: '晚上', night: '睡前'
	}

	function mondayOf(d) {
		const x = new Date(d.getFullYear(), d.getMonth(), d.getDate())
		const w = (x.getDay() + 6) % 7 // 周一 = 0
		return addDays(x, -w)
	}

	export default {
		components: { AppIcon },
		data() {
			return {
				statusBarHeight: 20,
				nav: {},
				W: 375,
				// #085 ①：日/周/月/季 四档，默认"周"
				scale: 'week',
				scales: [
					{ key: 'day', label: '日' },
					{ key: 'week', label: '周' },
					{ key: 'month', label: '月' },
					{ key: 'season', label: '季' }
				],
				tasks: [],
				loading: false,
				error: '',
				selectedKey: '',
				railScroll: 0,
				railOffset: 0,
				railDraggedAt: 0,
				unschedOpen: false,
				assignVisible: false,
				assignTask: null,
				assignPick: '',
				dayChips: [],
				submitting: false,
				seasonSuggestions: [],
				seasonTitle: ''
			}
		},
		computed: {
			today() {
				return new Date()
			},
			todayKey() {
				return dateKey(this.today)
			},
			// 有排期的任务，按天归档：{ 'YYYY-MM-DD': [task, ...] }
			byDay() {
				const map = {}
				this.tasks.forEach((t) => {
					if (!t.plan_date) return
					const k = String(t.plan_date).slice(0, 10)
					if (!map[k]) map[k] = []
					map[k].push(t)
				})
				return map
			},
			unscheduled() {
				return this.tasks.filter((t) => !t.plan_date)
			},
			// 滚轴上的格子（日/周/月/季四种粒度）
			cells() {
				const out = []
				const today = this.today
				if (this.scale === 'day') {
					// 今天往前 2 天、往后 11 天：够看"昨天今天明天"，也不会一进来就是一屏空白
					// 注意：基准日必须先归零到当天 0 点 —— today 带当前时分秒，
					// 直接拿它当 start/end 会把"当天 00:00"的任务排到区间外（格子显示空着、面板却有）
					const base = this.atMidnight(today)
					for (let i = -2; i <= 11; i++) {
						const d = addDays(base, i)
						out.push(this.makeDayCell(d))
					}
					return out
				}
				if (this.scale === 'week') {
					const base = mondayOf(today)
					for (let i = -1; i <= 6; i++) {
						out.push(this.makeWeekCell(addDays(base, i * 7), i))
					}
					return out
				}
				if (this.scale === 'month') {
					for (let i = -2; i <= 5; i++) {
						const d = new Date(today.getFullYear(), today.getMonth() + i, 1)
						out.push(this.makeMonthCell(d, i))
					}
					return out
				}
				// 季：当前季往前 1 季、往后 5 季
				for (let i = -1; i <= 5; i++) {
					const s = shiftSeason(today, i)
					out.push(this.makeSeasonCell(s, i))
				}
				return out
			},
			// 选中格子的时间范围
			selectedRange() {
				const key = this.selectedKey
				if (!key) return null
				if (this.scale === 'day') {
					const d = parseDateKey(key.split('|')[1])
					return d ? { start: d, end: d } : null
				}
				if (this.scale === 'week') {
					const s = parseDateKey(key.split('|')[1])
					return s ? { start: s, end: addDays(s, 6) } : null
				}
				if (this.scale === 'month') {
					const p = key.split('|')[1].split('-')
					const start = new Date(Number(p[0]), Number(p[1]) - 1, 1)
					const end = new Date(Number(p[0]), Number(p[1]), 0)
					return { start, end }
				}
				const s = parseDateKey(key.split('|')[1] + '-01')
				if (!s) return null
				const season = seasonOf(s)
				return { start: season.start, end: season.end }
			},
			// 选中范围里的任务，按"日/时段/周/月"分组
			panelGroups() {
				const r = this.selectedRange
				if (!r) return []
				const inRange = this.tasks.filter((t) => {
					if (!t.plan_date) return false
					const d = parseDateKey(t.plan_date)
					if (!d) return false
					return d >= r.start && d <= r.end
				})
				if (!inRange.length) return []
				const groups = {}
				const order = []
				const push = (key, label, t) => {
					if (!groups[key]) {
						groups[key] = { key, label, tasks: [] }
						order.push(key)
					}
					groups[key].tasks.push(t)
				}
				inRange.forEach((t) => {
					if (this.scale === 'day') {
						const slot = t.timeslot || ''
						const label = SLOT_LABELS[slot] || slot || '不按时段'
						push('s|' + slot, label, t)
					} else if (this.scale === 'week') {
						const d = parseDateKey(t.plan_date)
						const k = dateKey(d)
						push('d|' + k, WEEK_CN[d.getDay()] + ' ' + (d.getMonth() + 1) + '/' + d.getDate(), t)
					} else if (this.scale === 'month') {
						const d = parseDateKey(t.plan_date)
						const week = Math.floor((d.getDate() - 1) / 7) + 1
						push('w|' + week, '第 ' + week + ' 周', t)
					} else {
						const d = parseDateKey(t.plan_date)
						push('m|' + (d.getMonth() + 1), (d.getMonth() + 1) + ' 月', t)
					}
				})
				// 日档按时段顺序排，其它按 key 排
				if (this.scale === 'day') {
					const rank = (k) => {
						const slot = k.split('|')[1]
						const i = SLOT_ORDER.indexOf(slot)
						return i < 0 ? 99 : i
					}
					order.sort((a, b) => rank(a) - rank(b))
				} else {
					order.sort()
				}
				return order.map((k) => groups[k])
			},
			rangeHint() {
				if (this.scale === 'day') return '左右滑，一天一格'
				if (this.scale === 'week') return '一周一格，看这一阵'
				if (this.scale === 'month') return '一月一格，看长一点'
				return '一年四季，慢慢来'
			},
			panelTitle() {
				const c = this.cells.find((x) => x.key === this.selectedKey)
				return c ? c.panelLabel : ''
			},
			panelSub() {
				const r = this.selectedRange
				if (!r) return ''
				const all = this.tasks.filter((t) => {
					if (!t.plan_date) return false
					const d = parseDateKey(t.plan_date)
					return d >= r.start && d <= r.end
				})
				if (!all.length) return ''
				const done = all.filter((t) => this.isDone(t)).length
				if (done === all.length) return '都做完了 🎉'
				return done + '/' + all.length + ' 件做完 · 还有 ' + (all.length - done) + ' 件'
			},
			emptyTitle() {
				if (this.scale === 'season') return '这一季还空着'
				if (this.scale === 'month') return '这个月还空着'
				if (this.scale === 'week') return '这周还空着'
				return '这天还空着'
			}
		},
		onLoad() {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
			try {
				const info = uni.getSystemInfoSync()
				this.W = info.windowWidth || 375
			} catch (e) {
				this.W = 375
			}
			this.pickDefaultCell()
			this.load()
		},
		onShow() {
			// 从任务页/详情页回来，排期可能变了 → 静默重拉
			if (this.tasks.length) this.load(false)
		},
		mounted() {
			// #ifdef H5
			// 滚轮和鼠标拖拽只能用原生事件挂（uni 的 scroll-view 没这层封装）。
			// 手指滑动是浏览器原生的，不用管。
			this.bindRailInput()
			// #endif
		},
		methods: {
			// 归零到当天 0 点：统计"某天的任务"时拿带时分秒的 Date 当边界会漏掉 00:00 的任务
			atMidnight(d) {
				return new Date(d.getFullYear(), d.getMonth(), d.getDate())
			},
			// ===== 数据 =====
			async load(showLoading) {
				if (showLoading) this.loading = true
				this.error = ''
				try {
					await requireLogin()
					// 一次拿全部（含归档以外都在），本地按天分组：切档位不用再请求，翻起来是瞬时的。
					// 任务量真上去了，可以换成 /tasks/?from=&to=（接口 #085 已经支持）。
					const data = await get('/tasks/', { status: 'all' }, { silent: true })
					// #089：日程是"计划"视图 —— 归档 = 用户自己收起来了，不该继续占着某天的格子。
					// 已完成（once 做完）的保留：那天确实发生过，翻回去看得见才像日记。
					this.tasks = ((data && data.items) || []).filter((t) => t.status !== 'archived')
					if (!this.selectedKey) this.pickDefaultCell()
					if (this.scale === 'season') this.loadSeasonSuggestions()
				} catch (e) {
					if (e && e.needLogin) return
					this.error = errText(e, '没连上')
				} finally {
					this.loading = false
				}
			},
			async loadSeasonSuggestions() {
				// 接口先留位：返回空数组时就整块不显示
				const s = seasonOf(this.today)
				this.seasonTitle = s.year + ' 年 ' + s.label + '季'
				try {
					this.seasonSuggestions = (await fetchSeasonSuggestions(s.key, s.year)) || []
				} catch (e) {
					this.seasonSuggestions = []
				}
			},
			// ===== 格子 =====
			statOf(start, end) {
				let count = 0
				let done = 0
				this.tasks.forEach((t) => {
					if (!t.plan_date) return
					const d = parseDateKey(t.plan_date)
					if (!d || d < start || d > end) return
					count += 1
					if (this.isDone(t)) done += 1
				})
				return { count, done, pct: count ? Math.round((done / count) * 100) : 0 }
			},
			makeDayCell(d) {
				const key = dateKey(d)
				const st = this.statOf(d, d)
				const isToday = key === this.todayKey
				const title = isToday ? '今天' : WEEK_CN[d.getDay()]
				const sub = (d.getMonth() + 1) + '/' + d.getDate()
				return {
					key: 'd|' + key,
					title,
					sub,
					panelLabel: title + ' ' + sub,
					count: st.count,
					done: st.done,
					pct: st.pct,
					isToday
				}
			},
			makeWeekCell(monday, offset) {
				const key = dateKey(monday)
				const end = addDays(monday, 6)
				const st = this.statOf(monday, end)
				const isThis = key === dateKey(mondayOf(this.today))
				let title = (monday.getMonth() + 1) + '/' + monday.getDate()
				if (isThis) title = '本周'
				else if (offset === 1) title = '下周'
				else if (offset === -1) title = '上周'
				const md = (x) => (x.getMonth() + 1) + '/' + x.getDate()
				return {
					key: 'w|' + key,
					title,
					sub: md(monday) + '–' + md(end),
					panelLabel: title + ' ' + md(monday) + '–' + md(end),
					count: st.count,
					done: st.done,
					pct: st.pct,
					isToday: isThis
				}
			},
			makeMonthCell(d, offset) {
				const start = new Date(d.getFullYear(), d.getMonth(), 1)
				const end = new Date(d.getFullYear(), d.getMonth() + 1, 0)
				const st = this.statOf(start, end)
				const isThis = start.getFullYear() === this.today.getFullYear() && start.getMonth() === this.today.getMonth()
				let title = d.getMonth() + 1 + ' 月'
				if (isThis) title = '本月'
				else if (offset === 1) title = '下月'
				return {
					key: 'm|' + d.getFullYear() + '-' + (d.getMonth() + 1 < 10 ? '0' : '') + (d.getMonth() + 1),
					title,
					sub: d.getFullYear() + '',
					panelLabel: d.getFullYear() + ' 年 ' + (d.getMonth() + 1) + ' 月',
					count: st.count,
					done: st.done,
					pct: st.pct,
					isToday: isThis
				}
			},
			makeSeasonCell(s, offset) {
				const st = this.statOf(s.start, s.end)
				const cur = seasonOf(this.today)
				const isThis = s.key === cur.key && s.year === cur.year
				return {
					key: 's|' + s.year + '-' + (s.key === 'winter' ? 12 : SEASONS.find((x) => x.key === s.key).monthList[0]),
					title: seasonLabel(s),
					sub: s.months,
					panelLabel: s.year + ' 年' + seasonLabel(s),
					count: st.count,
					done: st.done,
					pct: st.pct,
					isToday: isThis
				}
			},
			pickDefaultCell() {
				// 默认选"今天所在的这一格"（周档 = 本周）
				const t = this.today
				if (this.scale === 'day') this.selectedKey = 'd|' + this.todayKey
				else if (this.scale === 'week') this.selectedKey = 'w|' + dateKey(mondayOf(t))
				else if (this.scale === 'month') {
					this.selectedKey = 'm|' + t.getFullYear() + '-' + (t.getMonth() + 1 < 10 ? '0' : '') + (t.getMonth() + 1)
				} else {
					const s = seasonOf(t)
					this.selectedKey = 's|' + s.year + '-' + (s.key === 'winter' ? 12 : SEASONS.find((x) => x.key === s.key).monthList[0])
				}
			},
			switchScale(key) {
				if (this.scale === key) return
				this.scale = key
				this.pickDefaultCell()
				// 换档后回到最左：不然上一档滑到一半的位置会留着，用户看不到刚选中的那一格
				this.$nextTick(() => this.applyRailScroll(0))
				if (key === 'season') this.loadSeasonSuggestions()
			},
			selectCell(c) {
				// 刚拖完松手会补一个 click，别顺手把格子选了
				if (Date.now() - (this.railDraggedAt || 0) < 300) return
				this.selectedKey = c.key
			},
			// H5 下 uni 的 scroll-view 会套两层 .uni-scroll-view，真正能滚的是里面那层
			railEl() {
				// #ifdef H5
				const nodes = document.querySelectorAll('.rail .uni-scroll-view')
				return nodes.length > 1 ? nodes[1] : nodes[0] || null
				// #endif
				// #ifndef H5
				return null
				// #endif
			},
			bindRailInput() {
				// #ifdef H5
				const el = this.railEl()
				if (!el || el.__railBound) return
				el.__railBound = true
				// 滚轮：鼠标没有横滑手势，竖向滚动映射成横向；触控板本来给 deltaX，交给浏览器
				el.addEventListener(
					'wheel',
					(e) => {
						if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return
						e.preventDefault()
						el.scrollLeft += e.deltaY
					},
					{ passive: false }
				)
				// 鼠标拖拽：按住能拖，松手交给 scroll-snap 吸到最近一格
				let startX = 0
				let startLeft = 0
				let moved = 0
				el.addEventListener('pointerdown', (e) => {
					if (e.pointerType !== 'mouse') return // 手指/笔走原生惯性，别抢
					startX = e.clientX
					startLeft = el.scrollLeft
					moved = 0
					// 拖的时候先关吸附，否则每挪一点都被"拽"回整格，手感发涩
					el.style.scrollSnapType = 'none'
					el.style.cursor = 'grabbing'
					el.style.userSelect = 'none'
				})
				el.addEventListener('pointermove', (e) => {
					if (!startX) return
					const dx = e.clientX - startX
					if (Math.abs(dx) > moved) moved = Math.abs(dx)
					el.scrollLeft = startLeft - dx
				})
				const end = () => {
					if (!startX) return
					startX = 0
					el.style.cursor = ''
					el.style.userSelect = ''
					el.style.scrollSnapType = '' // 清掉内联值 = 恢复吸附，浏览器自己吸到最近一格
					if (moved > 6) this.railDraggedAt = Date.now()
				}
				el.addEventListener('pointerup', end)
				el.addEventListener('pointercancel', end)
				el.addEventListener('pointerleave', end)
				// #endif
			},
			scrollBy(dir) {
				// 电脑端没有手指横滑，给两个箭头（一次挪一格多点）
				const step = this.scale === 'day' ? 140 : 240
				this.applyRailScroll(this.railOffset + dir * step)
			},
			// 把滚轴挪到某个位置。uni 的 scroll-left 属性在 H5 上对嵌套滚动容器不稳定
			// （实测点了不动），所以 H5 直接写真实滚动容器的 scrollLeft，小程序端靠 scroll-left。
			applyRailScroll(x) {
				const target = Math.max(0, x)
				this.railOffset = target
				this.railScroll = target
				// #ifdef H5
				try {
					const el = this.railEl()
					if (el) {
						el.scrollLeft = target
						// 读回真实值：赋值会被浏览器钳到最大值，别让 railOffset 漂到钳制后的假目标
						this.railOffset = el.scrollLeft
						this.railScroll = el.scrollLeft
					}
				} catch (e) {
					// 取不到就交给 scroll-left
				}
				// #endif
			},
			onRailScroll(e) {
				this.railOffset = (e.detail && e.detail.scrollLeft) || 0
			},
			goToday() {
				this.pickDefaultCell()
				this.$nextTick(() => this.applyRailScroll(0))
			},
			// ===== 任务行 =====
			// #087：日程里的进度同样是"今天"的 —— 昨天做完的不会显示成 100%
			isDone(t) {
				if (t.status === 'done') return true
				return t.steps_total > 0 && (!!t.done_today || t.steps_done >= t.steps_total)
			},
			pctOf(t) {
				if (!t.steps_total) return t.status === 'done' ? 100 : 0
				return Math.round((t.steps_done / t.steps_total) * 100)
			},
			openTask(t) {
				// 打勾仍在「我的任务」（清单式）；这里只负责"看排布"
				uni.navigateTo({ url: '/pages/tasks/tasks' })
				void t
			},
			goPattern(p) {
				uni.navigateTo({ url: '/pages/detail/detail?id=' + p.id })
			},
			goLibrary() {
				uni.navigateTo({ url: '/pages/search/search' })
			},
			goBack() {
				if (getCurrentPages().length > 1) {
					uni.navigateBack()
					return
				}
				uni.reLaunch({ url: '/pages/index/index' })
			},
			// ===== 未排期 → 排到某天（点选）=====
			toggleUnsched() {
				if (!this.unscheduled.length) return
				this.unschedOpen = !this.unschedOpen
			},
			openAssign(t) {
				this.assignTask = t
				this.assignPick = ''
				this.dayChips = []
				for (let i = 0; i < 8; i++) {
					const d = addDays(this.today, i)
					let label = WEEK_CN[d.getDay()]
					if (i === 0) label = '今天'
					else if (i === 1) label = '明天'
					else if (i === 2) label = '后天'
					this.dayChips.push({ key: dateKey(d), label: label, md: (d.getMonth() + 1) + '/' + d.getDate() })
				}
				this.assignVisible = true
			},
			closeAssign() {
				if (this.submitting) return
				this.assignVisible = false
			},
			onPickDate(e) {
				this.assignPick = e.detail.value
			},
			async confirmAssign() {
				if (this.submitting) return
				if (!this.assignPick) {
					uni.showToast({ title: '先挑一天', icon: 'none' })
					return
				}
				const task = this.assignTask
				this.submitting = true
				try {
					await requireLogin()
					const res = await request('/tasks/' + task.id + '/', 'PATCH', { plan_date: this.assignPick })
					const i = this.tasks.findIndex((t) => t.id === task.id)
					if (i >= 0) this.tasks.splice(i, 1, res)
					uni.showToast({ title: '排好了，' + this.friendly(this.assignPick), icon: 'none' })
					this.assignVisible = false
					this.unschedOpen = false
					// 排完视图跳到那一天，让用户看见"它真的进去"
					this.scale = 'day'
					this.selectedKey = 'd|' + this.assignPick
				} catch (e) {
					if (!(e && e.needLogin)) uni.showToast({ title: errText(e, '没排上，再试一次'), icon: 'none' })
				} finally {
					this.submitting = false
				}
			},
			friendly(key) {
				const d = parseDateKey(key)
				if (!d) return key
				return (d.getMonth() + 1) + ' 月 ' + d.getDate() + ' 日 ' + WEEK_CN[d.getDay()]
			}
		}
	}
</script>

<style scoped>
	/* 页面骨架：和 tasks/mine 一致（导航 + 滚轴 + 撑满的滚动体） */
	.page {
		display: flex;
		flex-direction: column;
		height: 100vh;
		background-color: var(--bg);
		box-sizing: border-box;
	}

	.nav {
		flex-shrink: 0;
	}

	.nav-inner {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.nav-today {
		font-size: 26rpx;
		color: var(--accent);
		font-weight: 600;
	}

	/* ===== 尺度切换 ===== */
	.scales {
		flex-shrink: 0;
		padding: 0 24rpx;
	}

	.scales-inner {
		display: flex;
		align-items: center;
	}

	.scale {
		min-height: 64rpx;
		padding: 0 26rpx;
		margin-right: 12rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.scale-text {
		font-size: 26rpx;
		color: var(--text-2);
	}

	.scale-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	.scale-on .scale-text {
		color: var(--accent);
		font-weight: 600;
	}

	.scale-hint {
		flex: 1;
		display: flex;
		justify-content: flex-end;
	}

	.scale-hint-text {
		font-size: 22rpx;
		color: var(--muted);
	}

	/* ===== 横向滚轴 ===== */
	.rail-wrap {
		flex-shrink: 0;
		position: relative;
		margin-top: 16rpx;
		padding: 0 24rpx;
		display: flex;
		align-items: center;
	}

	.rail {
		flex: 1;
		width: 0;
		white-space: nowrap;
		cursor: grab;
	}

	/* H5：吸附写在真正的滚动容器上（uni 自带那层），停在整格、
	   不越界回弹，滚动条藏起来（滑动本身已经是提示） */
	.rail :deep(.uni-scroll-view) {
		scroll-snap-type: x mandatory;
		overscroll-behavior-x: contain;
		-webkit-overflow-scrolling: touch;
		scrollbar-width: none;
	}

	.rail :deep(.uni-scroll-view::-webkit-scrollbar) {
		display: none;
		width: 0;
		height: 0;
	}

	.rail-inner {
		display: inline-flex;
		padding: 4rpx 0 8rpx;
	}

	.cell {
		flex-shrink: 0;
		scroll-snap-align: start;
		box-sizing: border-box;
		width: 176rpx;
		min-height: 176rpx;
		margin-right: 12rpx;
		padding: 16rpx 16rpx 14rpx;
		border-radius: var(--r-card, 16rpx);
		border: 2rpx solid var(--border);
		background-color: var(--card);
		display: flex;
		flex-direction: column;
	}

	.cell-title {
		font-size: 26rpx;
		font-weight: 600;
		color: var(--text);
	}

	.cell-sub {
		margin-top: 4rpx;
		font-size: 20rpx;
		color: var(--muted);
	}

	.cell-bar {
		height: 6rpx;
		margin-top: 14rpx;
		border-radius: 999rpx;
		background-color: var(--surface-2, rgba(255, 255, 255, 0.08));
		overflow: hidden;
	}

	.cell-bar-in {
		height: 100%;
		border-radius: 999rpx;
		background-color: var(--accent);
		transition: width 260ms ease;
	}

	.cell-count {
		margin-top: 10rpx;
		font-size: 20rpx;
		color: var(--muted);
	}

	.cell-empty .cell-title {
		color: var(--text-2);
	}

	.cell-today {
		border-color: var(--accent);
	}

	.cell-on {
		background-color: var(--accent-soft);
		border-color: var(--accent);
	}

	.cell-on .cell-title,
	.cell-on .cell-count {
		color: var(--accent);
	}

	/* 电脑端：滚轴换成两个箭头（鼠标横滑不方便） */
	.rail-arrow {
		flex-shrink: 0;
		width: 56rpx;
		height: 56rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		border: 2rpx solid var(--border);
		cursor: pointer;
	}

	.rail-prev {
		margin-right: 10rpx;
	}

	.rail-next {
		margin-left: 10rpx;
	}

	.rail-arrow-text {
		font-size: 30rpx;
		color: var(--muted);
	}

	/* ===== 主体 ===== */
	.body {
		flex: 1;
		height: 0;
	}

	.wrap {
		padding: 20rpx 24rpx 0;
	}

	.panel {
		margin-top: 8rpx;
	}

	.panel-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		margin-bottom: 12rpx;
	}

	.panel-title {
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
	}

	.panel-sub {
		font-size: 22rpx;
		color: var(--muted);
	}

	.group {
		margin-top: 20rpx;
	}

	.g-head {
		display: flex;
		align-items: center;
		margin-bottom: 12rpx;
	}

	.g-rail {
		width: 6rpx;
		height: 26rpx;
		margin-right: 12rpx;
		border-radius: 999rpx;
		background-color: var(--accent);
	}

	.g-label {
		font-size: 24rpx;
		color: var(--text-2);
	}

	.g-count {
		margin-left: 10rpx;
		font-size: 20rpx;
		color: var(--muted);
	}

	/* 任务行：左名字 + 右进度条（#085 要求） */
	.t-row {
		display: flex;
		align-items: center;
		padding: 22rpx 24rpx;
		margin-bottom: 12rpx;
	}

	.t-main {
		flex: 1;
		min-width: 0;
	}

	.t-title {
		font-size: 27rpx;
		color: var(--text);
	}

	.t-bar {
		height: 8rpx;
		margin-top: 12rpx;
		border-radius: 999rpx;
		background-color: var(--surface-2, rgba(255, 255, 255, 0.08));
		overflow: hidden;
	}

	.t-bar-in {
		height: 100%;
		border-radius: 999rpx;
		background-color: var(--accent);
		transition: width 260ms ease;
	}

	.t-pct {
		margin-left: 18rpx;
		font-size: 24rpx;
		font-weight: 600;
		color: var(--accent);
	}

	.t-badge {
		margin-left: 12rpx;
		padding: 2rpx 12rpx;
		border-radius: 999rpx;
		font-size: 20rpx;
		color: var(--success, #3f8f5f);
		border: 2rpx solid var(--success, #3f8f5f);
	}

	.t-done .t-title {
		color: var(--text-2);
	}

	/* ===== 未排期 ===== */
	.unsched {
		margin-top: 28rpx;
		padding: 20rpx 22rpx;
		border-radius: var(--r-card, 16rpx);
		border: 2rpx dashed var(--border);
	}

	.unsched-head {
		display: flex;
		align-items: center;
	}

	.unsched-title {
		font-size: 25rpx;
		color: var(--text-2);
	}

	.unsched-count {
		flex: 1;
		margin-left: 10rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	.unsched-act {
		font-size: 24rpx;
		color: var(--accent);
		font-weight: 600;
	}

	.unsched-none {
		display: block;
		margin-top: 10rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	.unsched-list {
		margin-top: 14rpx;
	}

	.unsched-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-height: 76rpx;
		border-top: 2rpx solid var(--border);
	}

	.unsched-item-title {
		flex: 1;
		min-width: 0;
		margin-right: 14rpx;
		font-size: 26rpx;
		color: var(--text);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.unsched-item-act {
		font-size: 22rpx;
		color: var(--accent);
	}

	/* ===== 季节推荐（接口留位，有数据才显示） ===== */
	.season {
		margin-top: 28rpx;
	}

	.season-head {
		margin-bottom: 12rpx;
	}

	.season-title {
		font-size: 25rpx;
		color: var(--text-2);
	}

	.season-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 22rpx 24rpx;
		margin-bottom: 12rpx;
	}

	.season-item-title {
		font-size: 27rpx;
		color: var(--text);
	}

	.season-item-tag {
		font-size: 22rpx;
		color: var(--muted);
	}

	/* ===== 空态 / 状态 ===== */
	.state {
		padding: 48rpx 24rpx;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.state-mark {
		width: 96rpx;
		height: 96rpx;
		margin-bottom: 20rpx;
		border-radius: 50%;
		background-color: var(--surface-2, rgba(255, 255, 255, 0.06));
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.state-title {
		font-size: 28rpx;
		font-weight: 600;
		color: var(--text);
	}

	.state-desc {
		margin-top: 12rpx;
		font-size: 24rpx;
		color: var(--muted);
		line-height: 1.6;
		text-align: center;
	}

	.state-btn {
		margin-top: 26rpx;
		min-height: 76rpx;
		padding: 0 34rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 999rpx;
		font-size: 26rpx;
	}

	.bar-space {
		height: 60rpx;
	}

	/* ===== 排期面板 ===== */
	.mask {
		position: fixed;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		z-index: 30;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		background-color: rgba(0, 0, 0, 0.45);
	}

	.sheet {
		box-sizing: border-box;
		width: 100%;
		max-height: 84vh;
		padding: 28rpx 28rpx 36rpx;
		border-radius: 28rpx 28rpx 0 0;
		background-color: var(--card);
		display: flex;
		flex-direction: column;
	}

	.sheet-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.sheet-title {
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
	}

	.sheet-close {
		font-size: 26rpx;
		color: var(--muted);
	}

	.sheet-hint {
		display: block;
		margin-top: 10rpx;
		font-size: 24rpx;
		color: var(--muted);
		line-height: 1.5;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		margin-top: 20rpx;
	}

	.chip {
		box-sizing: border-box;
		min-height: 76rpx;
		padding: 0 24rpx;
		margin: 0 12rpx 12rpx 0;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
	}

	.chip-text {
		font-size: 25rpx;
		color: var(--text-2);
	}

	.chip-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	.chip-on .chip-text {
		color: var(--accent);
		font-weight: 600;
	}

	.assign-more {
		margin-top: 6rpx;
	}

	.assign-more-text {
		font-size: 24rpx;
		color: var(--accent);
	}

	.sheet-acts {
		display: flex;
		margin-top: 22rpx;
	}

	.sheet-act {
		flex: 1;
		height: 84rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 999rpx;
		font-size: 28rpx;
	}

	.sheet-act-main {
		margin-left: 16rpx;
	}

	/* ===== 电脑端 ===== */
	@media (min-width: 768px) {
		.scales-inner,
		.wrap {
			max-width: 960px;
			margin-left: auto;
			margin-right: auto;
		}

		/* 注意：.rail-wrap 是 .page（flex 列）的直接子项，只写 margin:auto 会让它在交叉轴上
		   收缩到内容宽度（两个箭头 ≈ 94px），滚轴跟着塌成 0 宽、格子整排看不见。
		   所以这里必须显式 width:100% + border-box。 */
		.rail-wrap {
			box-sizing: border-box;
			width: 100%;
			max-width: 960px;
			margin-left: auto;
			margin-right: auto;
		}

		.cell {
			width: 118px;
			min-height: 118px;
			padding: 12px 12px 10px;
			margin-right: 8px;
			border-width: 1px;
			border-radius: var(--r-card);
		}

		.cell:hover {
			border-color: var(--accent);
		}

		.cell-title {
			font-size: 13px;
		}

		.cell-sub {
			font-size: 11px;
		}

		.cell-count {
			font-size: 11px;
		}

		.scale {
			min-height: 36px;
			padding: 0 18px;
			border-width: 1px;
			cursor: pointer;
		}

		.scale-text,
		.nav-today {
			font-size: 13px;
		}

		.t-row {
			padding: 14px 16px;
			border-width: 1px;
		}

		.t-row:hover {
			border-color: var(--accent);
		}

		.t-title,
		.season-item-title {
			font-size: 14px;
		}

		.t-pct,
		.t-badge,
		.g-label,
		.unsched-title,
		.season-title,
		.panel-title {
			font-size: 12px;
		}

		.panel-title {
			font-size: 16px;
		}

		.unsched-item {
			min-height: 40px;
		}

		.sheet {
			width: 520px;
			max-height: 80vh;
			padding: 24px;
			border-radius: 16px;
			margin-bottom: 40px;
			box-shadow: 0 18px 48px rgba(0, 0, 0, 0.35);
		}

		.mask {
			align-items: center;
		}

		.sheet-act {
			height: 44px;
			font-size: 14px;
			border-radius: var(--r-btn);
			cursor: pointer;
		}

		.chip {
			min-height: 36px;
			padding: 0 14px;
			border-width: 1px;
			cursor: pointer;
		}

		.chip-text,
		.sheet-hint {
			font-size: 13px;
		}

		.state-btn {
			min-height: 40px;
			font-size: 13px;
			border-radius: var(--r-btn);
			cursor: pointer;
		}
	}
</style>
