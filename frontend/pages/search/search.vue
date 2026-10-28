<template>
	<view class="page">
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">搜索</text>
				<view class="nav-btn nav-btn-ghost"></view>
			</view>
		</view>

		<!-- 搜索框：钉在导航下面（滚结果时还能改词），输入即联想 -->
		<view class="sbar">
			<view class="sbar-inner">
				<view class="sbox">
					<app-icon class="s-ico" name="magnifying-glass" :size="17" tone="muted" />
					<input
						class="s-input"
						v-model="keyword"
						type="text"
						:focus="autoFocus"
						confirm-type="search"
						placeholder="今天想做点什么？"
						placeholder-class="s-ph"
						@input="onInput"
						@confirm="doSearch()"
					/>
					<app-icon v-if="keyword" class="s-clear" name="x" :size="16" tone="muted" @click="clearKeyword" />
					<view class="s-go" hover-class="hover-dim" @click="doSearch()"><text class="s-go-text">搜索</text></view>
				</view>
				<view v-if="suggests.length" class="sugs theme-card">
					<view v-for="(t, i) in suggests" :key="i" class="sug" hover-class="hover-dim" @click="doSearch(t)">
						<app-icon class="sug-ico" name="magnifying-glass-plus" :size="14" tone="muted" />
						<text class="sug-text">{{ t }}</text>
					</view>
				</view>
			</view>
		</view>

		<scroll-view class="body" scroll-y>
			<!-- ===== 还没搜：最近搜索 + 热门词 ===== -->
			<block v-if="!query">
				<view v-if="history.length" class="sec">
					<view class="sec-head">
						<text class="sec-title">最近搜索</text>
						<text class="sec-act" hover-class="hover-dim" @click="clearHistory">清空</text>
					</view>
					<view class="chips">
						<view v-for="(h, i) in history" :key="'h' + i" class="chip" hover-class="hover-dim" @click="doSearch(h)">
							<text class="chip-text">{{ h }}</text>
						</view>
					</view>
				</view>

				<view v-if="hotWords.length" class="sec">
					<view class="sec-head"><text class="sec-title">大家在搜</text></view>
					<view class="chips">
						<view v-for="(w, i) in hotWords" :key="'w' + i" class="chip" hover-class="hover-dim" @click="doSearch(w)">
							<text class="chip-text">{{ w }}</text>
						</view>
					</view>
				</view>

				<view v-if="!history.length && !hotWords.length" class="empty">
					<view class="empty-mark"><app-icon name="magnifying-glass" :size="28" tone="muted" /></view>
					<text class="empty-title">想做什么，直接搜</text>
					<text class="empty-desc">比如「出门」「交接」「搬家」；打错字、只打一半也认</text>
				</view>
			</block>

			<block v-else>
				<!-- ===== 搜过了：标签行 + 结果 ===== -->
				<!-- 标签行：命中的分类（点一下只看这类）+ 结果里的关键词（点一下换词重搜） -->
				<view v-if="tags.length" class="tagrow">
					<view
						v-for="(t, i) in tags"
						:key="'t' + i"
						class="chip"
						:class="{ 'chip-on': t.kind === 'category' && activeCategory === t.key }"
						hover-class="hover-dim"
						@click="applyTag(t)"
					>
						<text class="chip-text">{{ t.label }}</text>
						<text class="chip-num">{{ t.count }}</text>
					</view>
				</view>

				<view class="statusrow">
					<text class="st-text">{{ statusText }}</text>
					<view v-if="enableUgc" class="st-act" hover-class="hover-dim" @click="toggleMulti">
						<text class="st-act-text">{{ multi ? '退出多选' : '多选合并' }}</text>
					</view>
				</view>

				<!-- #082：刚加入的任务给一条"去看看"的回头路（别让用户以为点丢了） -->
				<view v-if="addedBanner" class="added">
					<app-icon class="added-ico" name="check-circle" :size="15" tone="accent" />
					<text class="added-text">已加入「{{ addedBanner }}」，去今日任务看看</text>
					<text class="added-go" hover-class="hover-dim" @click="goTasks">去看看 ›</text>
					<text class="added-x" hover-class="hover-dim" @click="addedBanner = ''">✕</text>
				</view>

				<view v-if="loading" class="empty">
					<view class="empty-mark"><app-icon name="circle-notch" :size="28" tone="muted" /></view>
					<text class="empty-title">搜索中…</text>
				</view>

				<view v-else-if="error" class="empty">
					<view class="empty-mark"><app-icon name="cloud-slash" :size="28" tone="muted" /></view>
					<text class="empty-title">没能连上服务器</text>
					<text v-if="errorMsg" class="empty-err">（错误详情：{{ errorMsg }}）</text>
					<view class="empty-btn btn-accent" hover-class="hover-dim" @click="fetchResults"><text>重试</text></view>
				</view>

				<view v-else-if="results.length" class="s-list">
					<view
						v-for="item in results"
						:key="item.id"
						class="s-card theme-card"
						:class="{ 's-card-pick': multi, 's-card-on': isPicked(item.id) }"
						@click="onCard(item)"
					>
						<view v-if="multi" class="pick" :class="{ 'pick-on': isPicked(item.id) }">
							<app-icon v-if="isPicked(item.id)" name="check" :size="13" tone="inverse" />
						</view>
						<view class="s-card-icon">
							<app-icon v-if="item.icon_key" :name="item.icon_key" :size="26" tone="accent" />
							<text v-else class="s-card-emoji">{{ item.icon || '🧠' }}</text>
						</view>
						<view class="s-card-main">
							<text class="s-card-title">{{ item.title }}</text>
							<text v-if="item.tagline" class="s-card-tagline">{{ item.tagline }}</text>
							<view class="s-card-meta">
								<app-icon name="star" :size="13" tone="accent" />
								<text class="meta-star">{{ ratingText(item) }}</text>
								<text class="meta-dot">·</text>
								<text class="meta-text">{{ item.step_count }} 步</text>
								<text class="meta-dot">·</text>
								<text class="meta-text">{{ item.usage_count }} 人用过</text>
							</view>
							<view class="s-card-tags">
								<text class="tag tag-cat">{{ item.category }}</text>
								<text v-if="item.is_favorited" class="tag">已收藏</text>
							</view>
							<!-- ⑥ 直接执行：不进详情也能开干；多选模式下藏起来（避免误点） -->
							<view v-if="!multi" class="ops">
								<view class="op op-run" hover-class="hover-dim" @click.stop="goExecute(item)">
									<text class="op-text">▶ 直接执行</text>
								</view>
								<!-- #082：搜到就能变成日程 —— 点开面板选频率/时段，直接建任务（不用先进详情） -->
								<view class="op op-add" hover-class="hover-dim" @click.stop="openAddTask(item)">
									<app-icon class="op-add-ico" name="list-checks" :size="13" tone="muted" />
									<text class="op-add-text">加入任务</text>
								</view>
							</view>
						</view>
					</view>
				</view>

				<!-- 搜不到：给标签建议（spec ②），点一下接着搜 -->
				<view v-else class="empty">
					<view class="empty-mark"><app-icon name="tray" :size="28" tone="muted" /></view>
					<text class="empty-title">没找到「{{ query }}」</text>
					<text class="empty-desc">{{ activeCategory ? '这类里没有，换个标签或去掉分类' : '换个说法，或者点下面的标签' }}</text>
					<view v-if="tags.length" class="chips chips-center">
						<view v-for="(t, i) in tags" :key="'e' + i" class="chip" hover-class="hover-dim" @click="applyTag(t)">
							<text class="chip-text">{{ t.label }}</text>
						</view>
					</view>
					<view v-if="enableUgc" class="empty-btn btn-accent" hover-class="hover-dim" @click="goCreate">
						<text>＋ 没有就自己做一个</text>
					</view>
				</view>
			</block>

			<view class="safe-bottom" :class="{ 'safe-bottom-merge': multi }"></view>
		</scroll-view>

		<!-- #082：加入任务面板（复用 #079 的 task-sheet，mode=pattern；未登录时面板里先 requireLogin） -->
		<task-sheet
			:visible="taskSheetVisible"
			mode="pattern"
			:pattern-id="taskSheetPatternId"
			:hint="taskSheetHint"
			@close="taskSheetVisible = false"
			@done="onTaskAdded"
		/>

		<!-- ⑦ 多选合并：底部操作条 -->
		<view v-if="multi" class="mergebar">
			<text class="merge-text">已选 {{ picked.length }} 个</text>
			<view class="merge-btn btn-ghost" hover-class="hover-dim" @click="toggleMulti"><text>取消</text></view>
			<view
				class="merge-btn btn-accent"
				:class="{ 'merge-off': picked.length < 2 || merging }"
				hover-class="hover-dim"
				@click="onMerge"
			>
				<text>{{ merging ? '合并中…' : '合并导入' }}</text>
			</view>
		</view>
	</view>
</template>

<script>
	import { get, post, errText } from '@/api/request.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { ENABLE_UGC, IS_H5 } from '@/utils/config.js'
	import { ensureLogin } from '@/utils/token.js'
	// #073：结构图标统一走 app-icon（矢量，替代 emoji）
	import AppIcon from '@/components/app-icon/app-icon.vue'
	// #082：加入任务面板（复用 #079 的组件，不重造）
	import TaskSheet from '@/components/task-sheet/task-sheet.vue'

	// 最近搜索：本地存，最多留 8 条（spec 通用要求里的"可选"项，做了）
	const HISTORY_KEY = 'search_history'
	const HISTORY_MAX = 8
	const MAX_PICK = 5

	export default {
		components: { AppIcon, TaskSheet },
		data() {
			return {
				statusBarHeight: 20,
				nav: {},
				// 输入框里的字
				keyword: '',
				// 已经提交搜索的词（和 keyword 分开：输入过程中不改结果，点搜索/回车才搜）
				query: '',
				activeCategory: '',
				results: [],
				total: 0,
				tags: [],
				suggests: [],
				history: [],
				hotWords: [],
				loading: false,
				error: false,
				errorMsg: '',
				// 多选合并
				multi: false,
				picked: [],
				merging: false,
				enableUgc: ENABLE_UGC,
				// 进页面自动聚焦（回到本页时不再抢焦点，别把键盘顶出来）
				autoFocus: false,
				suggestTimer: null,
				// #082：加入任务（复用 task-sheet；addedBanner 是刚加入的那张卡的标题）
				taskSheetVisible: false,
				taskSheetPatternId: '',
				taskSheetHint: '',
				addedBanner: ''
			}
		},
		computed: {
			statusText() {
				const cat = this.activeCategoryLabel
				if (!this.total) return cat ? `「${this.query}」· ${cat}：0 条` : `「${this.query}」：没找到`
				return cat ? `「${this.query}」· ${cat} 共 ${this.total} 条` : `「${this.query}」共 ${this.total} 条`
			},
			activeCategoryLabel() {
				const t = this.tags.find((x) => x.kind === 'category' && x.key === this.activeCategory)
				return t ? t.label : ''
			}
		},
		onLoad(options) {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
			this.history = this.loadHistory()
			this.fetchHotWords()
			// 带 q 进来（网页刷新 / 从详情返回 / 分享链接）→ 直接把词恢复出来重搜。
			// 两端对 q 的解码行为不一致（H5 已解、部分端是原文），解一次并兜住异常
			let q = (options && options.q) || ''
			if (q) {
				try {
					q = decodeURIComponent(q)
				} catch (e) {}
				this.keyword = q
				this.doSearch(q)
			}
		},
		onReady() {
			if (!this.query) this.autoFocus = true
		},
		onUnload() {
			if (this.suggestTimer) clearTimeout(this.suggestTimer)
		},
		methods: {
			goBack() {
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
			},

			// ===== 输入 / 联想 =====
			onInput(e) {
				this.keyword = e.detail.value
				if (this.suggestTimer) clearTimeout(this.suggestTimer)
				const kw = (this.keyword || '').trim()
				if (!kw) {
					this.suggests = []
					return
				}
				// 防抖：停顿 250ms 才请求联想词
				this.suggestTimer = setTimeout(() => this.fetchSuggest(kw), 250)
			},
			async fetchSuggest(q) {
				// 回来时输入已经变了就丢弃，避免联想词和输入框对不上
				if (!q || q !== (this.keyword || '').trim()) return
				try {
					const data = await get('/quick/suggest/', { q: q }, { silent: true })
					this.suggests = Array.isArray(data) ? data.slice(0, 6) : []
				} catch (e) {
					this.suggests = []
				}
			},

			// ===== 搜索 =====
			doSearch(term) {
				const q = (typeof term === 'string' ? term : this.keyword || '').trim()
				if (!q) return
				this.keyword = q
				this.query = q
				// 打字后立刻点搜索/回车：把还在排队（250ms 防抖）的联想请求掐掉，
				// 否则它晚一步回来又把下拉撑开，压在结果上面
				if (this.suggestTimer) {
					clearTimeout(this.suggestTimer)
					this.suggestTimer = null
				}
				this.suggests = []
				this.activeCategory = ''
				this.autoFocus = false
				// 换了一次搜索，"刚加入"的那条横幅就翻篇了（别挂着上一张卡的名字）
				this.addedBanner = ''
				this.saveHistory(q)
				this.syncUrl(q)
				this.fetchResults()
			},
			async fetchResults() {
				if (!this.query) return
				this.loading = true
				this.error = false
				this.errorMsg = ''
				try {
					const data = await get('/quick/', {
						q: this.query,
						category: this.activeCategory,
						page: 1,
						page_size: 50
					}, { silent: true })
					this.results = (data && data.results) || []
					this.total = (data && data.total) || 0
					this.tags = (data && data.tags) || []
					// 选中的模板可能已经不在结果里了（换了词/点了分类），去掉避免"选了看不见的"
					const ids = this.results.map((r) => r.id)
					this.picked = this.picked.filter((id) => ids.indexOf(id) >= 0)
				} catch (e) {
					this.error = true
					this.errorMsg = errText(e, '未知错误')
					this.results = []
					this.total = 0
					this.tags = []
				} finally {
					this.loading = false
				}
			},
			// 点标签：分类 = 只看这一类（再点一次取消）；关键词 = 换成它重搜
			applyTag(t) {
				if (t.kind === 'category') {
					this.activeCategory = this.activeCategory === t.key ? '' : t.key
					this.fetchResults()
					return
				}
				this.doSearch(t.label)
			},
			clearKeyword() {
				this.keyword = ''
				this.suggests = []
			},
			async fetchHotWords() {
				try {
					const data = await get('/quick/tags/', null, { silent: true })
					this.hotWords = Array.isArray(data) ? data.slice(0, 10) : []
				} catch (e) {
					this.hotWords = []
				}
			},

			// ===== 结果卡片 =====
			onCard(item) {
				if (this.multi) {
					this.togglePick(item.id)
					return
				}
				this.goDetail(item)
			},

			// ===== #082：搜到就能加入任务 =====
			openAddTask(item) {
				// 多选时列表只用于合并，别让两个语义混在一起（按钮此时也是隐藏的）
				if (this.multi) return
				this.taskSheetPatternId = item.id
				this.taskSheetHint = '把「' + item.title + '」整条加进我的任务，步骤会复制一份（以后改模板不影响你这条）。'
				this.taskSheetVisible = true
			},
			onTaskAdded(task) {
				// 面板自己已经 toast 过了，这里只留一条"去看看"的入口；任务页数据是实时拉的，不用手动通知
				if (task && task.title) this.addedBanner = task.title
			},
			goTasks() {
				uni.navigateTo({ url: '/pages/tasks/tasks' })
			},
			goDetail(item) {
				// 带上 from=search + 词：详情页返回时能回到搜索页（#072④⑤）
				uni.navigateTo({
					url: '/pages/detail/detail?id=' + item.id
						+ '&from=search&q=' + encodeURIComponent(this.query || '')
				})
			},
			goExecute(item) {
				uni.navigateTo({ url: '/pages/execute/execute?id=' + item.id })
			},
			goCreate() {
				uni.navigateTo({ url: '/pages/create/create' })
			},
			ratingText(item) {
				return item.rating_count > 0 ? Number(item.avg_rating).toFixed(1) : '暂无评分'
			},

			// ===== 多选合并 =====
			toggleMulti() {
				this.multi = !this.multi
				if (!this.multi) this.picked = []
			},
			isPicked(id) {
				return this.picked.indexOf(id) >= 0
			},
			togglePick(id) {
				const i = this.picked.indexOf(id)
				if (i >= 0) {
					this.picked.splice(i, 1)
					return
				}
				if (this.picked.length >= MAX_PICK) {
					uni.showToast({ title: `最多选 ${MAX_PICK} 个`, icon: 'none' })
					return
				}
				this.picked.push(id)
			},
			async onMerge() {
				if (this.merging) return
				if (this.picked.length < 2) {
					uni.showToast({ title: '至少选两张才能合并', icon: 'none' })
					return
				}
				this.merging = true
				try {
					// 合并要在服务端建草稿（步骤拼接 + 归属校验都在那边一套口径），所以先确保登录
					await ensureLogin()
					const np = await post('/quick/merge/', { ids: this.picked }, { silent: true })
					this.multi = false
					this.picked = []
					uni.showToast({ title: '合好了，看看再发', icon: 'none' })
					// 直接进编辑页（预填合并后的步骤），在那儿改成自己的模板
					uni.navigateTo({ url: '/pages/create/create?id=' + np.id })
				} catch (e) {
					uni.showToast({ title: errText(e, '合并失败'), icon: 'none' })
				} finally {
					this.merging = false
				}
			},

			// ===== 最近搜索（本地） =====
			loadHistory() {
				try {
					const raw = uni.getStorageSync(HISTORY_KEY)
					return Array.isArray(raw) ? raw.filter((x) => typeof x === 'string').slice(0, HISTORY_MAX) : []
				} catch (e) {
					return []
				}
			},
			saveHistory(q) {
				const next = [q].concat(this.history.filter((x) => x !== q)).slice(0, HISTORY_MAX)
				this.history = next
				try {
					uni.setStorageSync(HISTORY_KEY, next)
				} catch (e) {
					// 存不进去（隐私模式/配额）不影响搜索本身
				}
			},
			clearHistory() {
				this.history = []
				try {
					uni.removeStorageSync(HISTORY_KEY)
				} catch (e) {}
			},

			// #072⑤：网页版把搜索词写进地址栏 —— 刷新/浏览器后退回到这一页时词还在
			syncUrl(q) {
				// #ifdef H5
				if (typeof window !== 'undefined' && window.history && window.history.replaceState) {
					const url = window.location.pathname + '?q=' + encodeURIComponent(q)
					window.history.replaceState(null, '', url)
				}
				// #endif
			}
		}
	}
</script>

<style>
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

	/* ===== 搜索框 ===== */
	.sbar {
		position: relative;
		flex-shrink: 0;
		padding: 16rpx 24rpx 0;
		background-color: var(--bg);
		z-index: 20;
	}

	/* 联想词要贴着搜索框，所以两者放同一个定位容器里 */
	.sbar-inner {
		position: relative;
	}

	.sbox {
		display: flex;
		align-items: center;
		height: 88rpx;
		padding: 0 24rpx;
		border-radius: 999rpx;
		background-color: var(--card);
		border: 2rpx solid var(--border);
	}

	.s-ico {
		margin-right: 12rpx;
		font-size: 30rpx;
		line-height: 1;
	}

	.s-input {
		flex: 1;
		min-width: 0;
		height: 88rpx;
		font-size: 28rpx;
		color: var(--text);
	}

	.s-ph {
		color: var(--muted);
	}

	.s-clear {
		padding-left: 16rpx;
	}

	/* 搜索按钮：手机上键盘也有"搜索"键，但电脑端没有 —— 两端都给一个明确的提交入口 */
	.s-go {
		flex-shrink: 0;
		margin-left: 12rpx;
		padding: 0 20rpx;
		height: 64rpx;
		display: flex;
		align-items: center;
		border-radius: 999rpx;
		background-color: var(--accent-soft);
	}

	.s-go-text {
		font-size: 26rpx;
		font-weight: 600;
		color: var(--accent);
	}

	/* 联想词：贴在搜索框下方（相对 .sbar-inner，所以左右跟着搜索框走） */
	.sugs {
		position: absolute;
		left: 0;
		right: 0;
		top: calc(88rpx + 8rpx);
		overflow: hidden;
		z-index: 30;
	}

	.sug {
		display: flex;
		align-items: center;
		height: 80rpx;
		padding: 0 24rpx;
		border-bottom: 2rpx solid var(--border);
	}

	.sug:last-child {
		border-bottom: none;
	}

	.sug-ico {
		margin-right: 12rpx;
	}

	.sug-text {
		font-size: 28rpx;
		color: var(--text);
	}

	.body {
		flex: 1;
		height: 0;
	}

	/* ===== 分区（最近搜索 / 大家在搜） ===== */
	.sec {
		padding: 24rpx 0 0;
	}

	.sec-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 24rpx;
	}

	.sec-title {
		font-size: 26rpx;
		font-weight: 600;
		color: var(--muted);
	}

	.sec-act {
		font-size: 26rpx;
		color: var(--accent);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		padding: 16rpx 24rpx 0;
	}

	.chips-center {
		justify-content: center;
	}

	/* 标签/词条：跟全站 .tag 同一套（次级面 + --r-chip 圆角） */
	.chip {
		display: flex;
		align-items: center;
		height: 64rpx;
		padding: 0 24rpx;
		margin: 0 16rpx 16rpx 0;
		border-radius: 999rpx;
		background-color: var(--card);
		border: 2rpx solid var(--border);
	}

	.chip-on {
		background-color: var(--accent-soft);
		border-color: var(--accent);
	}

	.chip-text {
		font-size: 26rpx;
		color: var(--text);
	}

	.chip-on .chip-text {
		color: var(--accent);
		font-weight: 600;
	}

	.chip-num {
		margin-left: 10rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	.tagrow {
		display: flex;
		flex-wrap: wrap;
		padding: 20rpx 24rpx 0;
	}

	.statusrow {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16rpx 24rpx 0;
	}

	.st-text {
		font-size: 26rpx;
		color: var(--muted);
	}

	.st-act-text {
		font-size: 26rpx;
		color: var(--accent);
	}

	/* ===== 结果列表 ===== */
	.s-list {
		padding: 24rpx;
	}

	.s-card {
		display: flex;
		padding: 24rpx;
		margin-bottom: 20rpx;
	}

	.s-card-on {
		border-color: var(--accent);
	}

	.s-card-icon {
		flex-shrink: 0;
		width: 96rpx;
		height: 96rpx;
		margin-right: 20rpx;
		border-radius: 24rpx;
		background-color: var(--bg);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.s-card-emoji {
		font-size: 48rpx;
	}

	.s-card-main {
		flex: 1;
		min-width: 0;
	}

	.s-card-title {
		display: block;
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text);
	}

	.s-card-tagline {
		display: block;
		margin-top: 8rpx;
		font-size: 26rpx;
		color: var(--muted);
	}

	.s-card-meta {
		display: flex;
		align-items: center;
		margin-top: 16rpx;
	}

	.meta-star {
		margin-left: 6rpx;
		font-size: 24rpx;
		color: var(--accent);
	}

	.meta-dot {
		margin: 0 10rpx;
		font-size: 24rpx;
		color: var(--border);
	}

	.meta-text {
		font-size: 24rpx;
		color: var(--muted);
	}

	.s-card-tags {
		display: flex;
		align-items: center;
		margin-top: 16rpx;
	}

	.s-card-tags .tag {
		margin-right: 12rpx;
	}

	/* ⑥ 直接执行：卡片上的主操作（触控目标 ≥ 44px） */
	.ops {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		margin-top: 16rpx;
	}

	.op {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 64rpx;
		padding: 0 28rpx;
		margin-right: 12rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
	}

	.op-run {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	/* #082：加入任务 —— 次要动作，描边比"直接执行"弱一档，不抢主操作 */
	.op-add {
		padding: 0 22rpx;
	}

	.op-add-ico {
		margin-right: 8rpx;
	}

	.op-add-text {
		font-size: 25rpx;
		color: var(--text-2);
	}

	.op-text {
		font-size: 26rpx;
		color: var(--accent);
		font-weight: 600;
	}

	/* #082：刚加入任务后的"去看看"提示条（只在本次搜索里挂一条，换词就消失） */
	.added {
		display: flex;
		align-items: center;
		margin: 0 0 10rpx;
		padding: 18rpx 20rpx;
		border-radius: var(--r-btn);
		border: 2rpx solid var(--accent-soft);
		background-color: var(--accent-soft);
	}

	.added-ico {
		flex-shrink: 0;
		margin-right: 10rpx;
	}

	.added-text {
		flex: 1;
		min-width: 0;
		font-size: 24rpx;
		color: var(--text);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.added-go {
		flex-shrink: 0;
		margin-left: 12rpx;
		font-size: 24rpx;
		color: var(--accent);
		font-weight: 600;
	}

	.added-x {
		flex-shrink: 0;
		width: 48rpx;
		text-align: center;
		font-size: 22rpx;
		color: var(--muted);
	}

	/* ===== 多选勾选框 ===== */
	.pick {
		flex-shrink: 0;
		width: 44rpx;
		height: 44rpx;
		margin: 24rpx 16rpx 0 0;
		border-radius: 50%;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.pick-on {
		background-color: var(--accent);
		border-color: var(--accent);
	}

	

	/* ===== 底部多选操作条 ===== */
	.mergebar {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		display: flex;
		align-items: center;
		padding: 16rpx 24rpx;
		padding-bottom: calc(16rpx + constant(safe-area-inset-bottom));
		padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
		background-color: var(--card);
		border-top: 2rpx solid var(--border);
		z-index: 40;
	}

	.merge-text {
		flex: 1;
		font-size: 28rpx;
		color: var(--text);
	}

	.merge-btn {
		margin-left: 16rpx;
		padding: 0 32rpx;
	}

	.merge-off {
		opacity: 0.45;
	}

	/* ===== 空态 / 加载 ===== */
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 100rpx 64rpx;
	}

	.empty-mark {
		width: 112rpx;
		height: 112rpx;
		border-radius: 50%;
		background-color: var(--card);
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.empty-title {
		margin-top: 24rpx;
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text);
	}

	.empty-desc {
		margin-top: 12rpx;
		font-size: 26rpx;
		color: var(--muted);
		text-align: center;
	}

	.empty-err {
		margin-top: 12rpx;
		font-size: 22rpx;
		line-height: 1.6;
		color: var(--muted);
		text-align: center;
		word-break: break-all;
	}

	.empty-btn {
		margin-top: 40rpx;
		padding: 0 48rpx;
	}

	.safe-bottom {
		height: calc(32rpx + constant(safe-area-inset-bottom));
		height: calc(32rpx + env(safe-area-inset-bottom));
	}

	/* 多选时给底部操作条让位，否则最后一张卡被压住 */
	.safe-bottom-merge {
		height: calc(160rpx + constant(safe-area-inset-bottom));
		height: calc(160rpx + env(safe-area-inset-bottom));
	}

	/* ===== 网页版（H5）：跟首页/我的同一套内容列与卡片规范 ===== */
	/* #ifdef H5 */
	.sbar {
		padding: 0 0 12px;
	}

	/* 搜索框跟内容列对齐（.body 是同一套限宽，见 App.vue 全局规则） */
	.sbar-inner {
		box-sizing: border-box;
		max-width: var(--content-w);
		margin: 0 auto;
		padding: 0 var(--content-pad);
	}

	.sbox {
		height: 48px;
		padding: 0 16px;
		border-width: 1px;
		border-radius: var(--r-btn);
		background-color: var(--surface-2);
	}

	.s-ico {
		margin-right: 8px;
	}

	.s-input {
		height: 48px;
		font-size: 15px;
	}

	.s-clear {
		padding-left: 12px;
		cursor: pointer;
	}

	.s-go {
		height: 36px;
		padding: 0 16px;
		margin-left: 8px;
		border-radius: var(--r-btn);
		cursor: pointer;
	}

	.s-go-text {
		font-size: 14px;
	}

	.sugs {
		left: var(--content-pad);
		right: var(--content-pad);
		top: 56px;
		border: 1px solid var(--border);
		border-radius: var(--r-card);
	}

	.sug {
		height: 44px;
		padding: 0 16px;
		border-bottom-width: 1px;
	}

	.sug:hover {
		background-color: var(--surface-2);
	}

	.sug-text {
		font-size: 14px;
	}

	.sec {
		padding: 20px 0 0;
	}

	.sec-title,
	.sec-act {
		font-size: 13px;
	}

	.sec-title {
		color: var(--text-2);
	}

	.chips {
		padding: 12px 0 0;
	}

	.chip {
		height: 36px;
		padding: 0 14px;
		margin: 0 8px 8px 0;
		border-radius: var(--r-chip);
		background-color: var(--surface-2);
		border-width: 1px;
	}

	.chip-text {
		font-size: 13px;
		color: var(--text-2);
	}

	.chip-num {
		font-size: 12px;
	}

	.tagrow {
		padding: 16px 0 0;
	}

	.statusrow {
		padding: 12px 0 0;
	}

	.st-text,
	.st-act-text {
		font-size: 13px;
	}

	.st-act {
		cursor: pointer;
	}

	.s-list {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 16px;
		padding: 20px 0 8px;
	}

	@media (min-width: 768px) {
		.s-list {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 20px;
		}
	}

	@media (min-width: 1024px) {
		.s-list {
			grid-template-columns: repeat(3, minmax(0, 1fr));
			gap: 24px;
			padding: 28px 0 8px;
		}
	}

	.s-card {
		margin-bottom: 0;
		padding: 20px;
		border-width: 1px;
	}

	@media (hover: hover) {
		.s-card {
			transition: transform 200ms ease, border-color 200ms ease;
		}
		.s-card:hover {
			transform: translateY(-2px);
			border-color: var(--accent-soft);
		}
	}

	.s-card-pick {
		cursor: pointer;
	}

	.s-card-icon {
		width: 48px;
		height: 48px;
		margin-right: 14px;
		border-radius: var(--r-btn);
	}

	.s-card-emoji {
		font-size: 24px;
	}

	.s-card-title {
		font-size: 16px;
	}

	.s-card-tagline {
		font-size: 13px;
	}

	.meta-star,
	.meta-text,
	.meta-dot {
		font-size: 12px;
	}

	.op {
		height: 32px;
		padding: 0 14px;
		border-radius: var(--r-btn);
		border-width: 1px;
		cursor: pointer;
	}

	.op-text {
		font-size: 13px;
	}

	/* #082：电脑端两个按钮同一行、高度一致 */
	.op-add {
		padding: 0 12px;
	}

	.op-add-text {
		font-size: 13px;
	}

	.added {
		padding: 12px 14px;
		margin-bottom: 10px;
		border-radius: var(--r-btn);
		border-width: 1px;
	}

	.added-text,
	.added-go {
		font-size: 13px;
	}

	.added-go {
		cursor: pointer;
	}

	.added-x {
		cursor: pointer;
	}

	.pick {
		width: 22px;
		height: 22px;
		margin: 4px 12px 0 0;
		border-width: 1px;
	}

	

	/* 电脑端：内容列居中，操作条也收进内容列宽度 */
	.mergebar {
		box-sizing: border-box;
		width: 100%;
		max-width: var(--content-w);
		left: 50%;
		right: auto;
		transform: translateX(-50%);
		padding: 12px 0;
		border-top-width: 1px;
		background-color: var(--card);
		border-radius: var(--r-card) var(--r-card) 0 0;
	}

	.merge-text {
		font-size: 14px;
	}

	.merge-btn {
		height: 44px;
		min-width: 96px;
		padding: 0 18px;
		font-size: 14px;
		cursor: pointer;
	}

	.empty {
		padding: 60px 24px;
	}

	.empty-mark {
		width: 60px;
		height: 60px;
		border-width: 1px;
	}

	.empty-title {
		margin-top: 12px;
		font-size: 16px;
	}

	.empty-desc {
		margin-top: 6px;
		font-size: 13px;
	}

	.empty-err {
		font-size: 12px;
	}

	.empty-btn {
		margin-top: 20px;
		min-width: 160px;
		padding: 0 20px;
		cursor: pointer;
	}

	.safe-bottom,
	.safe-bottom-merge {
		height: 24px;
	}

	.safe-bottom-merge {
		height: 92px;
	}
	/* #endif */
</style>
