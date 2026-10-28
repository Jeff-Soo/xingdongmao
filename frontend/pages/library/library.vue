<template>
	<view class="page">
		<!-- pages.json 里 navigationStyle=custom，标题栏要自己画（执行页要全屏沉浸，提前统一） -->
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<!-- #090：模板库从主页搬出来，成了独立一页 —— 左边给返回，标题写清这是哪儿 -->
				<view class="nav-left">
					<view class="nav-btn" hover-class="hover-dim" @click="goBack">
						<text class="nav-btn-icon">‹</text>
					</view>
					<view class="nav-brand">
						<text class="nav-title">模板库</text>
						<text class="nav-sub">挑一件，今天就有事做</text>
					</view>
				</view>
				<!-- #058⑥：电脑端把"创建"放到导航里（右下角悬浮按钮在宽屏上离视线太远，
				     第一次进来的人找不到写东西的入口）。手机端由 CSS 隐藏，继续用悬浮按钮 -->
				<view v-if="enableUgc" class="nav-create" hover-class="hover-dim" @click="goCreate">
					<view class="nav-create-pill"><text class="nav-create-text">＋ 创建模板</text></view>
				</view>
			</view>
		</view>

		<scroll-view
			class="body"
			scroll-y
			:refresher-enabled="true"
			:refresher-triggered="refreshing"
			refresher-background="transparent"
			:lower-threshold="120"
			@refresherrefresh="onRefresh"
			@scrolltolower="onLoadMore"
			@scroll="onBodyScroll"
		>
			<!-- 搜索（#072①）：这里只当"入口"，点了进独立搜索页；
			     候选词/结果/标签行/多选合并都在 pages/search/search 里做 -->
			<view class="search-wrap">
				<view class="search-box search-box-link" hover-class="hover-dim" @click="goSearch">
					<app-icon class="search-icon" name="magnifying-glass" :size="17" tone="muted" />
					<text class="search-placeholder">今天想做点什么？</text>
				</view>
				<!-- #080： 「我的」胶囊从标题模块搬到这里（原「任务」胶囊的位置），大小不变；
				     首页不再有任务入口（任务入口在「我的」页里） -->
				<view class="search-mine" hover-class="hover-dim" @click="goMine">
					<view class="search-mine-pill" :style="pillStyle"><text class="search-mine-text">我的</text></view>
				</view>
			</view>

			<!-- #072①：首页不再原地筛（搜索搬到独立页），所以这里永远显示筛选条 -->
			<view>
				<!-- #ifdef H5 -->
				<!-- 网页版：筛选默认收起，只留一行"图标 + 当前筛选 + 结果数"，点这一行展开/收起 -->
				<view class="filter-bar" @click="filterExpanded = !filterExpanded">
					<app-icon class="filter-ico" name="funnel-simple" :size="16" tone="muted" />
					<text class="filter-cur">{{ activeCategoryLabel }}</text>
					<text class="filter-count">共 {{ total }} 个</text>
					<text class="filter-caret">{{ filterExpanded ? '⌃' : '⌄' }}</text>
				</view>
				<!-- #endif -->

				<view class="filters" :class="{ 'filters-collapsed': !filterExpanded }">
					<scroll-view class="cats" scroll-x :show-scrollbar="false">
						<view class="cats-inner">
							<view
								v-for="c in categories"
								:key="c.key"
								class="cat"
								:class="{ 'cat-on': activeCategory === c.key }"
								@click="switchCategory(c.key)"
							>
								<text class="cat-text">{{ c.label }}</text>
							</view>
						</view>
					</scroll-view>

					<view class="sort-row">
						<view class="sort-group">
							<view
								v-for="s in sorts"
								:key="s.key"
								class="sort"
								:class="{ 'sort-on': sort === s.key }"
								@click="switchSort(s.key)"
							>
								<text class="sort-text">{{ s.label }}</text>
							</view>
						</view>
						<text class="sort-count">共 {{ total }} 个</text>
					</view>
				</view>
			</view>

			<!-- 首屏骨架 -->
			<view v-if="loading && !list.length" class="list">
				<view v-for="i in 3" :key="i" class="card theme-card">
					<view class="card-icon sk-block"></view>
					<view class="card-main">
						<view class="sk-line sk-line-lg"></view>
						<view class="sk-line"></view>
					</view>
				</view>
			</view>

			<view v-else-if="list.length" class="list">
				<view v-for="item in list" :key="item.id" class="card theme-card" @click="goDetail(item.id)">
					<view class="card-icon">
						<app-icon v-if="item.icon_key" :name="item.icon_key" :size="26" tone="accent" />
						<text v-else class="card-emoji">{{ item.icon || '🧠' }}</text>
					</view>
					<view class="card-main">
						<text class="card-title">{{ item.title }}</text>
						<text v-if="item.tagline" class="card-tagline">{{ item.tagline }}</text>
						<view class="card-meta">
							<app-icon name="star" :size="13" tone="accent" />
							<text class="meta-star">{{ ratingText(item) }}</text>
							<text class="meta-dot">·</text>
							<text class="meta-text">{{ item.step_count }} 步</text>
							<text class="meta-dot">·</text>
							<text class="meta-text">{{ item.usage_count }} 人用过</text>
						</view>
						<view class="card-tags">
							<text class="tag tag-cat">{{ item.category }}</text>
							<text v-if="item.is_official" class="tag">官方</text>
							<text v-if="item.is_favorited" class="tag">已收藏</text>
						</view>
					</view>
				</view>
			</view>

			<!-- 错误态：不白屏，给出可操作提示 + 真实错误详情（真机连不上时靠这一行定位） -->
			<view v-else-if="error" class="empty">
				<view class="empty-mark"><app-icon name="cloud-slash" :size="30" tone="muted" /></view>
				<text class="empty-title">没连上</text>
				<text v-if="errorMsg" class="empty-err">（错误详情：{{ errorMsg }}）</text>
				<text class="empty-desc">网络有点不顺；本地调试的话，看看后端起没起、开发者工具有没有勾「不校验合法域名」</text>
				<view class="empty-btn btn-accent" @click="retry"><text>重试</text></view>
			</view>

			<!-- 空态 -->
			<view v-else class="empty">
				<view class="empty-mark"><app-icon name="tray" :size="30" tone="muted" /></view>
				<text class="empty-title">这一类还空着</text>
				<text class="empty-desc">换个分类翻翻，或者直接搜你想做的那件事</text>
				<!-- #058⑥：空态里直接给创建入口 —— 第一次进来的人最容易停在这一屏 -->
				<view v-if="enableUgc" class="empty-btn btn-accent" @click="goCreate">
					<text>＋ 创建一个模板</text>
				</view>
				<view class="empty-btn btn-ghost" @click="goSearch">
					<text>去搜一下</text>
				</view>
				<view v-if="activeCategory" class="empty-btn btn-ghost" @click="resetFilters">
					<text>清空筛选</text>
				</view>
			</view>

			<view v-if="list.length" class="footer">
				<text v-if="loading" class="footer-text">加载中…</text>
				<text v-else-if="finished" class="footer-text">没有更多了</text>
				<!-- #064③：剩下的情况给一个【可点】的加载入口：
				     电脑端没有"上拉"这个手势，文案跟着平台走；请求失败时这一行就是重试按钮（呼应 #057"失败能重试"） -->
				<view v-else class="footer-btn" hover-class="hover-dim" @click="onLoadMore">
					<text class="footer-text">{{ error ? '加载失败，点这里重试' : (isWideScreen ? '点这里加载更多' : '上拉加载更多') }}</text>
				</view>
			</view>
			<!-- UGC 关掉时没有悬浮按钮，底部不留那 200rpx（见 .safe-bottom-no-fab） -->
			<view class="safe-bottom" :class="{ 'safe-bottom-no-fab': !enableUgc }"></view>
		</scroll-view>

		<!-- 创建入口：悬浮右下角（用 absolute 不用 fixed，页面本身不滚动，最稳）
		     UGC 入口：ENABLE_UGC=false 时隐藏，代码保留（utils/config.js） -->
		<view v-if="enableUgc" class="fab" hover-class="hover-dim" @click="goCreate">
			<text class="fab-plus">＋</text>
			<text class="fab-text">创建</text>
		</view>

		<!-- #040/#090：新手引导只挂在首页（它教的是"今天"那一屏），这页不再挂 -->
	</view>
</template>

<script>
	import { get, errText } from '@/api/request.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { ENABLE_UGC, IS_H5 } from '@/utils/config.js'
	// #073：结构图标统一走 app-icon（矢量，替代 emoji）
	import AppIcon from '@/components/app-icon/app-icon.vue'

	// 分类 key 必须用后端的 category_key（英文），label 只是显示文案
	const CATEGORIES = [
		{ key: '', label: '全部' },
		{ key: 'life_out', label: '出行准备' },
		{ key: 'life_home', label: '居家事务' },
		{ key: 'life_daily', label: '日常事务' },
		{ key: 'work_service', label: '服务行业' },
		{ key: 'work_office', label: '职场办公' },
		{ key: 'work_safety', label: '安全操作' },
		// #057⑪：后端 CATEGORY_CHOICES 里有 other，前端少了这一项 →
		// 归到"其他"的模板只能在「全部」里看到，切分类永远找不到
		{ key: 'other', label: '其他' }
	]

	const SORTS = [
		{ key: 'hot', label: '热门' },
		{ key: 'latest', label: '最新' }
	]

	export default {
		components: { AppIcon },
		data() {
			return {
				statusBarHeight: 20,
				// 导航栏尺寸（对齐微信胶囊），onLoad 里用 getNavBarMetrics() 填
				nav: {},
				// UGC 开关：控制「＋ 创建」入口是否显示（utils/config.js）
				enableUgc: ENABLE_UGC,
				categories: CATEGORIES,
				sorts: SORTS,
				// #072①：搜索整体搬到 pages/search/search，首页不再有搜索词/联想词状态
				activeCategory: '',
				sort: 'hot',
				list: [],
				total: 0,
				page: 1,
				pageSize: 10,
				loading: false,
				// #057⑫：请求在飞时被挡下的那次筛选（见 fetchList）
				pendingFetch: false,
				pendingReset: false,
				// #064：电脑端（≥768px）—— 底部提示文案/滚轮加载都按它走
				isWideScreen: false,
				// #064②：滚动监听节流用的时间戳（一次滚动会连发很多事件）
				scrollTickAt: 0,
				refreshing: false,
				finished: false,
				error: false,
				// 失败的真实原因（网络层 errMsg / 后端 error），渲染在错误态里给真机排查用
				errorMsg: '',
				// 网页版：筛选区（分类 + 排序）默认收起，只显示"图标 + 当前筛选 + 结果数"。
				// 小程序端没有这个交互，恒为 true = 永远展开（保持原样）。
				filterExpanded: !IS_H5
			}
		},
		onLoad() {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight)
			this.fetchList(true)
		},
		computed: {
			// 让"我的"胶囊和微信胶囊等高，不只是中心线对齐，上下边也齐
			pillStyle() {
				return this.nav && this.nav.capsuleHeight ? { height: this.nav.capsuleHeight + 'px' } : {}
			},
			// 网页版筛选收起后，要在那一行里显示"当前选中项"的文字
			activeCategoryLabel() {
				const hit = CATEGORIES.find((c) => c.key === this.activeCategory)
				return hit ? hit.label : '全部'
			}
		},
		// #058⑧：网页版给"分类行"接上鼠标滚轮 —— 它是横向 scroll-view，
		// 桌面上只有触摸板/拖拽能滚，鼠标滚轮压在它上面时页面不动、行也不动，很难用。
		// 把纵向 deltaY 转成横向滚动；行本身没溢出（芯片都装得下）时不拦截，让页面正常滚。
		mounted() {
			// #ifdef H5
			this.$nextTick(() => {
				const cats = document.querySelector('.cats')
				if (cats) {
					const all = cats.querySelectorAll('.uni-scroll-view')
					const scroller = all.length ? all[all.length - 1] : cats
					this.onCatsWheel = (e) => {
						if (!e.deltaY) return
						const max = scroller.scrollWidth - scroller.clientWidth
						if (max <= 4) return
						e.preventDefault()
						scroller.scrollLeft += e.deltaY
					}
					scroller.addEventListener('wheel', this.onCatsWheel, { passive: false })
				}
				// #064②：直接监听【滚动容器】的 scroll。不依赖 uni 的 scrolltolower 实现，
				// 距底 ≤200px 就加载；滚轮下滑带动滚动 → 到底即加载。
				this.bindBodyScroller()
			})
			this.onResizeScreen = () => this.syncWideScreen()
			window.addEventListener('resize', this.onResizeScreen)
			this.syncWideScreen()
			// #064②：挂载后再补一次检查（首屏渲染/视口定型的时间点不一定和 nextTick 对齐），
			// 内容不足一屏就直接补下一页 —— 电脑端高屏上就靠这一步跨过"滚不动"的坎。
			this.fillTimer = setTimeout(() => this.fillIfNeeded(), 400)
			// #endif
		},
		onUnload() {
			// #ifdef H5
			if (this.onCatsWheel) {
				const cats = document.querySelector('.cats')
				const all = cats ? cats.querySelectorAll('.uni-scroll-view') : []
				const scroller = all.length ? all[all.length - 1] : cats
				if (scroller) scroller.removeEventListener('wheel', this.onCatsWheel)
			}
			if (this.bodyScroller && this.onBodyScrollEvt) {
				this.bodyScroller.removeEventListener('scroll', this.onBodyScrollEvt)
			}
			if (this.onResizeScreen) window.removeEventListener('resize', this.onResizeScreen)
			if (this.fillTimer) clearTimeout(this.fillTimer)
			// #endif
		},
		methods: {
			// #090：这页是从首页点进来的二级页，左上角给返回；
			// 直接刷新/分享进来时没有上一页，回首页兜底（不然点了没反应）
			goBack() {
				const pages = getCurrentPages()
				if (pages.length > 1) uni.navigateBack()
				else uni.reLaunch({ url: '/pages/index/index' })
			},
			async fetchList(reset = false) {
				// #057⑫：请求还在飞的时候再点筛选/搜索，以前一句 `return` 就把这次筛选丢掉了，
				// 列表停在上一个筛选的结果上（看着像"点了没反应"，得再点一次）。
				// 现在记一个 pending，等当前请求在 finally 里收尾后按**最新**筛选重发一次。
				if (this.loading) {
					this.pendingFetch = true
					this.pendingReset = this.pendingReset || reset
					return true
				}
				if (reset) {
					this.page = 1
					this.finished = false
				}
				if (this.finished && !reset) return true

				let ok = true
				this.loading = true
				this.error = false
				this.errorMsg = ''
				try {
					const data = await get('/quick/', {
						category: this.activeCategory,
						sort: this.sort,
						page: this.page,
						page_size: this.pageSize
					}, { silent: true })
					const results = (data && data.results) || []
					this.total = (data && data.total) || 0
					this.list = reset ? results : this.list.concat(results)
					// total 是切片前的总数，所以「本页没拿满」或「已累计到总数」都算到底
					this.finished = results.length < this.pageSize || this.list.length >= this.total
				} catch (e) {
					ok = false
					this.error = true
					// 只写死"网络错误"定位不了问题（域名白名单？超时？证书？），把真实 errMsg 留在页面上
					this.errorMsg = errText(e, '未知错误')
					if (reset) {
						this.list = []
						this.total = 0
					}
				} finally {
					this.loading = false
					this.refreshing = false
					if (this.pendingFetch) {
						const again = this.pendingReset
						this.pendingFetch = false
						this.pendingReset = false
						// #057⑬：补发也失败时，把 onLoadMore 多推的那一页退回来
						this.fetchList(again).then((ok2) => {
							if (ok2 === false && !again && this.page > 1) this.page -= 1
						})
					} else if (ok && !reset) {
						// #064②：这一页装完还没填满一屏 → 继续补下一页（finished 会自然终止）
						this.$nextTick(() => this.fillIfNeeded())
					}
					if (reset) this.fillRounds = 0
				}
				return ok
			},

			// #072①：搜索框现在只是入口，点了进独立搜索页（原来那套"原地筛 + 联想词"的
			// onKeywordInput / fetchSuggest / onSearchConfirm / applySuggest / clearKeyword 已删除）
			goSearch() {
				uni.navigateTo({ url: '/pages/search/search' })
			},

			switchCategory(key) {
				if (this.activeCategory === key) return
				this.activeCategory = key
				this.fetchList(true)
			},

			switchSort(key) {
				if (this.sort === key) return
				this.sort = key
				this.fetchList(true)
			},

			resetFilters() {
				this.activeCategory = ''
				this.fetchList(true)
			},

			retry() {
				this.fetchList(true)
			},

			onRefresh() {
				// 正在请求时不重复发；refresher 要手动收回去，否则一直转圈
				if (this.loading) {
					this.refreshing = false
					return
				}
				this.refreshing = true
				this.fetchList(true)
			},

			async onLoadMore() {
				if (this.loading || this.finished) return
				// #057⑬：page 先加、请求失败就退回来。以前失败后 page 已经 +1，
				// 下次加载直接跳过一整页（那 10 条永远看不到了）。
				const prev = this.page
				this.page += 1
				const ok = await this.fetchList()
				if (ok === false) this.page = prev
			},

			// ===== #064 电脑端"加载更多" =====
			// 实测根因：触发靠 scroll-view 的 scrolltolower（+ lower-threshold=120），机制本身是通的；
			// 但电脑端第一页 10 张卡在 1920×1080 下距底只剩 9px（1440×1100 剩 137px）——
			// **几乎没有可滚空间**，用户的滚轮"滚不动"，也就永远等不到触底事件。
			// 所以补三条路：① 滚动监听（不依赖 uni 的 scrolltolower 实现）② 内容不足一屏自动补页
			// ③ 底部给一个可点的加载/重试入口。
			syncWideScreen() {
				// #ifdef H5
				this.isWideScreen = typeof window !== 'undefined' && window.innerWidth >= 768
				this.$nextTick(() => this.fillIfNeeded())
				// #endif
			},
			bindBodyScroller() {
				// #ifdef H5
				const body = document.querySelector('.body')
				if (!body) return
				const all = body.querySelectorAll('.uni-scroll-view')
				const scroller = all.length ? all[all.length - 1] : body
				this.bodyScroller = scroller
				this.onBodyScrollEvt = () => this.onBodyScroll()
				scroller.addEventListener('scroll', this.onBodyScrollEvt, { passive: true })
				// #endif
			},
			onBodyScroll() {
				// #ifdef H5
				// 节流 120ms：一次滚轮/惯性滚动会连发很多 scroll 事件（#064③ 防重复触发）
				const now = Date.now()
				if (now - this.scrollTickAt < 120) return
				this.scrollTickAt = now
				const s = this.bodyScroller
				if (!s) return
				const gap = s.scrollHeight - s.scrollTop - s.clientHeight
				// 距底 200px 内就加载（规格书定的阈值）
				if (gap <= 200) this.maybeLoadMore()
				// #endif
				// #ifndef H5
				// 小程序端维持原样：加载更多仍由 @scrolltolower 负责，这里什么都不做
				// #endif
			},
			maybeLoadMore() {
				// 加载中 / 已经到底 / 列表空 / 有被挡下的请求 → 都不重复触发
				if (this.loading || this.finished || !this.list.length || this.pendingFetch) return
				this.onLoadMore()
			},
			async fillIfNeeded() {
				// #ifdef H5
				// 内容撑不满一屏时自动补下一页（高屏上第一页几乎铺满 → 以前完全触发不了加载更多）
				if (!this.bodyScroller || this.loading || this.finished) return
				if (!this.list.length || this.pendingFetch) return
				if ((this.fillRounds || 0) >= 8) return   // 兜底：最多自动补 8 页，防意外连拉
				const s = this.bodyScroller
				if (s.scrollHeight - s.scrollTop - s.clientHeight > 200) return
				this.fillRounds = (this.fillRounds || 0) + 1
				const prev = this.page
				this.page += 1
				const ok = await this.fetchList()
				if (ok === false) {
					this.page = prev          // 失败退回页码，底部那行会变成"加载失败，点这里重试"
					this.fillRounds = 0
					return
				}
				this.$nextTick(() => this.fillIfNeeded())
				// #endif
			},

			goDetail(id) {
				uni.navigateTo({ url: '/pages/detail/detail?id=' + id })
			},

			goMine() {
				uni.navigateTo({ url: '/pages/mine/mine' })
			},

			goCreate() {
				uni.navigateTo({ url: '/pages/create/create' })
			},

			ratingText(item) {
				return item.rating_count > 0 ? Number(item.avg_rating).toFixed(1) : '暂无评分'
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
		background-color: var(--bg);
	}

	/* ===== 自定义导航栏 ===== */
	.nav {
		flex-shrink: 0;
		background-color: var(--card);
		border-bottom: 2rpx solid var(--border);
	}

	/* 高度/上边距/右侧留白都以微信胶囊为准，由 nav.navInnerStyle 注入；
	   下面这组静态值 = 开发者工具拿不到胶囊数据时的兜底，保证布局不崩 */
	.nav-inner {
		display: flex;
		align-items: baseline;
		height: 32px;
		margin-top: 6px;
		padding: 0 32rpx;
		padding-right: 98px;
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
	}

	/* 标题 + 副标题包成一组，两个字并排。
	   小程序端用 baseline（和改之前完全一样）；网页版在 H5 块里改成"整组居中 + 字底对齐"。 */
	.nav-brand {
		display: flex;
		align-items: baseline;
		min-width: 0;
	}

	/* #090：返回 + 标题横着排。88rpx = 44px 触控目标 */
	.nav-left {
		display: flex;
		align-items: center;
		min-width: 0;
	}
	.nav-btn {
		flex-shrink: 0;
		width: 72rpx;
		height: 72rpx;
		margin-right: 12rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		background: var(--surface-2);
	}
	.nav-btn-icon {
		font-size: 44rpx;
		line-height: 1;
		color: var(--text);
		margin-top: -6rpx;
	}

		/* #080： 「我的」胶囊（原在导航标题模块里，现在挪到搜索框右边）。
		   外层 88rpx = 44px 触控目标；内层胶囊高度跟微信胶囊对齐（pillStyle 注入），
		   大小与搬家前完全一致（32px 高、左右 24rpx、2rpx 描边、24rpx 灰字）。 */
	.search-mine {
		flex-shrink: 0;
		height: 88rpx;
		margin-left: 16rpx;
		display: flex;
		align-items: center;
	}

	.search-mine-pill {
		height: 32px;
		padding: 0 24rpx;
		border-radius: 999rpx;
		background-color: var(--card);
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
	}

	.search-mine-text {
		font-size: 24rpx;
		color: var(--muted);
	}

	.hover-dim {
		opacity: 0.6;
	}

	.body {
		flex: 1;
		height: 0;
	}

	/* ===== 搜索（#072①：只当入口，样式做成"看着像输入框"的可点区域） ===== */
	.search-wrap {
		position: relative;
		display: flex;
		align-items: center;
		padding: 20rpx 24rpx 0;
	}

	.search-box {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		height: 80rpx;
		padding: 0 24rpx;
		border-radius: 24rpx;
		background-color: var(--card);
	}

	.search-box-link {
		/* 触控目标 ≥ 44px：手机 80rpx≈40px，这里补到 88rpx 更稳 */
		height: 88rpx;
	}

	.search-icon {
		margin-right: 12rpx;
	}

	.search-placeholder {
		flex: 1;
		min-width: 0;
		font-size: 28rpx;
		color: var(--muted);
		/* #080：搜索框必须单行——旁边多一个胶囊时，长文案以前会折成两行把框撑高 */
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* ===== 分类 ===== */
	.cats {
		width: 100%;
		margin-top: 24rpx;
		white-space: nowrap;
	}

	.cats-inner {
		display: inline-flex;
		align-items: center;
		padding: 0 24rpx;
	}

	.cat {
		flex-shrink: 0;
		height: 64rpx;
		padding: 0 28rpx;
		margin-right: 16rpx;
		border-radius: 999rpx;
		background-color: var(--card);
		display: flex;
		align-items: center;
	}

	.cat-on {
		background-color: var(--accent);
	}

	.cat-text {
		font-size: 26rpx;
		color: var(--muted);
	}

	.cat-on .cat-text {
		color: #FFFFFF;
		font-weight: 600;
	}

	/* ===== 排序 ===== */
	.sort-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 24rpx 32rpx 0;
	}

	.sort-group {
		display: flex;
		align-items: center;
	}

	.sort {
		height: 56rpx;
		padding: 0 24rpx;
		margin-right: 12rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
	}

	.sort-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	.sort-text {
		font-size: 24rpx;
		color: var(--muted);
	}

	.sort-on .sort-text {
		color: var(--accent);
		font-weight: 600;
	}

	.sort-count {
		font-size: 24rpx;
		color: var(--muted);
	}

	/* ===== 列表 ===== */
	.list {
		padding: 24rpx;
	}

	.card {
		display: flex;
		padding: 24rpx;
		margin-bottom: 20rpx;
	}

	.card-icon {
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

	.card-emoji {
		font-size: 48rpx;
	}

	.card-main {
		flex: 1;
		min-width: 0;
	}

	.card-title {
		display: block;
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text);
	}

	.card-tagline {
		display: block;
		margin-top: 8rpx;
		font-size: 26rpx;
		color: var(--muted);
	}

	.card-meta {
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

	.card-tags {
		display: flex;
		align-items: center;
		margin-top: 16rpx;
	}

	.card-tags .tag {
		margin-right: 12rpx;
	}

	.sk-block {
		background-color: var(--border);
	}

	.sk-line {
		height: 28rpx;
		margin-bottom: 16rpx;
		border-radius: 8rpx;
		background-color: var(--border);
		width: 60%;
	}

	.sk-line-lg {
		height: 36rpx;
		width: 85%;
	}

	/* ===== 空态 / 错误态 ===== */
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 120rpx 64rpx;
	}

	/* 空态不再是 emoji，改成"圆底 + 线条图标"的小标记（#073） */
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

	/* 错误详情：errMsg 可能很长，允许折行、别截断；比正文更小更淡，不抢"重试"的注意力 */
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
		padding: 0 64rpx;
	}

	/* ===== 底部 ===== */
	.footer {
		display: flex;
		justify-content: center;
		padding: 16rpx 0 8rpx;
	}

	.footer-text {
		font-size: 24rpx;
		color: var(--muted);
	}

	/* 给右下角悬浮的「＋ 创建」留位，别让它压住最后一张卡 */
	.safe-bottom {
		height: calc(200rpx + constant(safe-area-inset-bottom));
		height: calc(200rpx + env(safe-area-inset-bottom));
	}

	/* UGC 关掉时没有悬浮按钮，就不需要那 200rpx 留白 */
	.safe-bottom-no-fab {
		height: calc(32rpx + constant(safe-area-inset-bottom));
		height: calc(32rpx + env(safe-area-inset-bottom));
	}

	/* ===== 创建悬浮按钮 ===== */
	.fab {
		position: absolute;
		right: 32rpx;
		bottom: calc(48rpx + constant(safe-area-inset-bottom));
		bottom: calc(48rpx + env(safe-area-inset-bottom));
		z-index: 10;
		height: 96rpx;
		padding: 0 36rpx;
		border-radius: 999rpx;
		background-color: var(--accent);
		box-shadow: 0 8rpx 28rpx rgba(226, 112, 58, 0.35);
		display: flex;
		align-items: center;
	}

	.fab-plus {
		margin-right: 8rpx;
		font-size: 34rpx;
		line-height: 1;
		color: #ffffff;
	}

	.fab-text {
		font-size: 28rpx;
		font-weight: 600;
		color: #ffffff;
	}
	/* ===== 网页版（H5）：响应式网格 + 卡片规范（设计规范 §三/§4.1） ===== */
	/* #ifdef H5 */
	/* 列数：手机 1 列、平板 2 列、电脑 3 列 */
	.list {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 16px;
		padding: 20px 0 8px;
	}

	@media (min-width: 768px) {
		.list {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 20px;
		}
	}

	@media (min-width: 1024px) {
		.list {
			grid-template-columns: repeat(3, minmax(0, 1fr));
			gap: 24px;
			padding: 28px 0 8px;
		}
	}

	/* 卡片：20px 内边距、12px 圆角、1px 细边框；电脑端 hover 微升起 */
	.card {
		margin-bottom: 0;
		padding: 20px;
	}
	@media (hover: hover) {
		.card {
			transition: transform 200ms ease, border-color 200ms ease;
		}
		.card:hover {
			transform: translateY(-2px);
			border-color: var(--accent-soft);
		}
	}
	.card-title {
		font-size: 16px;
	}
	.card-tagline {
		font-size: 13px;
	}
	.card-meta .meta-star,
	.card-meta .meta-text,
	.card-meta .meta-dot {
		font-size: 12px;
	}

	/* 搜索框 / 分类 / 排序：次级面 + 按钮级圆角（#035 起统一走 --r-btn / --r-chip） */
	.search-box {
		height: 48px;
		background-color: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: var(--r-btn);
	}

	/* #072①：入口式的"假搜索框" —— 鼠标要变手型，整块都能点 */
	.search-box-link {
		cursor: pointer;
	}

	.search-placeholder {
		font-size: 15px;
	}

	/* ===== 分类标签与"热门/最新"统一（#026 ①）=====
	   原来是实心暖棕金填充，太抢眼；现在跟排序按钮同一套：
	   未选中 = 透明底 + 细边框 + 次级文字；选中 = 淡标志色底 + 标志色边框/文字。 */
	.cat,
	.sort {
		height: 32px;
		padding: 0 14px;
		border-radius: var(--r-chip);
		background-color: transparent;
		border: 1px solid var(--border);
	}
	/* #035 ④：卡片里的图标块原来 24rpx（手机上≈16px），比卡片圆角还大，一起收小 */
	.card-icon {
		border-radius: var(--r-btn);
	}
	.cat-text,
	.sort-text {
		font-size: 13px;
		color: var(--text-2);
	}
	.cat-on,
	.sort-on {
		background-color: var(--accent-soft);
		border-color: var(--accent);
	}
	.cat-on .cat-text,
	.sort-on .sort-text {
		color: var(--accent);
		font-weight: 600;
	}
	/* 分类行/排序行跟内容列对齐（去掉原来那点额外缩进） */
	.cats {
		margin-top: 12px;
	}
	.cats-inner {
		padding: 0;
	}
	.sort-row {
		padding: 12px 0 0;
	}
	.sort-count {
		font-size: 12px;
	}

	/* ===== 筛选收起行（#026 ②）===== */
	.filter-bar {
		display: flex;
		align-items: center;
		margin-top: 16px;
		height: 36px;
		cursor: pointer;
		user-select: none;
	}
	.filter-ico {
		margin-right: 8px;
		line-height: 1;
	}
	.filter-cur {
		font-size: 13px;
		font-weight: 600;
		color: var(--text);
	}
	.filter-count {
		margin-left: 8px;
		font-size: 12px;
		color: var(--muted);
	}
	.filter-caret {
		margin-left: auto;
		font-size: 16px;
		line-height: 1;
		color: var(--text-2);
	}
	/* 收起状态：把分类行 + 排序行整体藏起来 */
	.filters-collapsed {
		display: none;
	}

	/* 骨架屏用灰块，不用转圈（设计规范 §五） */
	.sk-block,
	.sk-line {
		background-color: var(--surface-2);
	}

	/* 空态/错误态：图标 + 低调文案 */
	.empty-mark {
		width: 60px;
		height: 60px;
		border-width: 1px;
	}
	.empty-title {
		font-size: 16px;
	}
	.empty-desc,
	.empty-err {
		font-size: 13px;
	}

	/* 网页版没有状态栏/胶囊，底部留白收一收 */
	.safe-bottom,
	.safe-bottom-no-fab {
		height: 24px;
	}
	.footer-text {
		font-size: 12px;
	}
	/* #064③：底部"点这里加载更多 / 加载失败点这里重试"做成可点区域（≥44px 触控目标） */
	.footer {
		padding: 8px 0;
	}
	.footer-btn {
		box-sizing: border-box;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 44px;
		padding: 0 16px;
		border: 1px solid var(--border);
		border-radius: var(--r-btn);
	}
	@media (hover: hover) {
		.footer-btn {
			cursor: pointer;
		}
	}
	/* #endif */
	/* ===== 网页版（H5）：悬浮按钮定位（#030 ④⑤） ===== */
	/* #ifdef H5 */
	/* ④ 诊断结论：不是 v-if 的问题——显示条件只有 enableUgc，H5 下编译出来恒为 true，
	   没有第二个条件、也不受列表状态或滚动影响。真正的原因是**定位**：
	   原来是 position:absolute，挂在 height:100vh 的 .page 上；手机浏览器地址栏展开时，
	   可视高度比 100vh 小，贴着"100vh 底部"的按钮就被推到可视区之外，
	   地址栏一收（或页面一动）又露出来 → 表现成"有时出现、有时不出现"。
	   改成 fixed：相对可视视口定位，永远贴在右下角。
	   ⑤ 顺带把安全区补上：bottom 加 env(safe-area-inset-bottom)，躲开 iPhone 底部横条。 */
	.fab {
		position: fixed;
		right: var(--content-pad);
		bottom: calc(24px + env(safe-area-inset-bottom));
		z-index: 30;
	}
	/* #endif */
	/* ===== 网页版（H5）：标题 + 副标题的位置（#036 起标题块 44px） ===== */
	/* #ifdef H5 */
	.nav-inner {
		align-items: center;
	}
	.nav-brand {
		display: flex;
		align-items: flex-end;
		/* #038②：品牌名跟其他页标题同一个字号变量（App.vue 的 .nav-title，42px），
		   行盒 = 块高 44px，整组自然占满块高；min-height 只是兜底。 */
		min-height: 30px;
	}
	/* #038②：副标题跟着放大到 13px——42px 的品牌名旁边，11px 会读不出来（保持 #033 的底对齐） */
	.nav-sub {
		font-size: 13px;
		line-height: 20px;
	}
	/* #endif */
	/* ===== #058：电脑端适配（手机端不受影响：全部关在 min-width: 768px / 1024px 里） ===== */
	/* #ifdef H5 */
	/* ⑥ 导航里的"＋ 创建模板"：手机端隐藏（那里有右下角悬浮按钮，导航再塞一个会挤） */
	.nav-create {
		display: none;
		flex-shrink: 0;
		margin-left: 8px;
		cursor: pointer;
	}
	.nav-create-pill {
		height: 30px;
		padding: 0 14px;
		border-radius: 999px;
		background-color: var(--accent);
		display: flex;
		align-items: center;
	}
	.nav-create-text {
		font-size: 13px;
		font-weight: 600;
		color: var(--accent-text);
	}

	@media (min-width: 768px) {
		.nav-create {
			display: block;
		}
		/* ① 电脑端品牌标题再"重"一点：800 字重 + 一点字距，看着像 logo 而不是普通标题 */
		.nav-brand .nav-title {
			font-weight: 800;
			letter-spacing: 0.06em;
		}
		.nav-sub {
			font-size: 14px;
		}
	}

	/* ⑫ 列表多列：1024 起 2 列、1440 起 3 列，宽屏不再只有中间一列。
	   卡片可以宽（信息自成一格），正文块另有易读宽度（详情页单独限宽）。 */
	@media (min-width: 1024px) {
		.list {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 16px;
		}
		.list > .card {
			margin-top: 0 !important;
		}
	}
	@media (min-width: 1440px) {
		.list {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
		/* ⑫c 字号跟着屏幕走一点（大屏上 14px 的正文字会显小） */
		.card-title {
			font-size: 18px;
		}
		.card-tagline {
			font-size: 14px;
		}
	}

	/* ⑧ 分类行：给了滚轮监听，光标提示"这里能滚" */
	@media (hover: hover) {
		.cats {
			cursor: grab;
		}
	}
	/* #endif */
</style>