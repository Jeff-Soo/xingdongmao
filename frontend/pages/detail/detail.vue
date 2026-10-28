<template>
	<view class="page">
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">模板详情</text>
				<view class="nav-btn nav-btn-ghost"></view>
			</view>
		</view>

		<scroll-view v-if="detail" class="body" scroll-y>
			<view class="hero theme-card">
				<view class="hero-icon">
					<app-icon v-if="detail.icon_key" :name="detail.icon_key" :size="34" tone="accent" />
					<text v-else class="hero-emoji">{{ detail.icon || '🧠' }}</text>
				</view>
				<text class="hero-title">{{ detail.title }}</text>
				<text v-if="detail.tagline" class="hero-tagline">{{ detail.tagline }}</text>
				<view class="hero-tags">
					<text class="tag tag-cat">{{ detail.category }}</text>
					<text v-if="detail.is_official" class="tag">官方</text>
				</view>

				<!-- 收藏 + 分享：详情页的两个次要动作，放头部，不和底部"开始引导"抢位置 -->
				<view class="hero-acts">
					<!-- 收藏要身份，网页版第一版没有登录，先隐藏（canLogin=false） -->
					<view
						v-if="canLogin"
						class="hero-fav"
						:class="{ 'hero-fav-on': detail.is_favorited }"
						hover-class="hover-dim"
						@click="onToggleFavorite"
					>
						<app-icon class="hero-fav-ico" :name="detail.is_favorited ? 'star' : 'star-half'" :size="15" :tone="detail.is_favorited ? 'accent' : 'muted'" />
						<text class="hero-fav-text">{{ detail.is_favorited ? '已收藏' : '收藏' }}</text>
					</view>
					<view class="hero-fav" hover-class="hover-dim" @click="openShare">
						<app-icon class="hero-fav-ico" name="export" :size="15" tone="muted" />
						<text class="hero-fav-text">分享</text>
					</view>
				</view>

				<view class="hero-stats">
					<view class="stat">
						<text class="stat-num">{{ ratingText }}</text>
						<view class="stat-label-row">
							<app-icon name="star" :size="12" tone="accent" />
							<text class="stat-label">评分{{ detail.rating_count ? '（' + detail.rating_count + '）' : '' }}</text>
						</view>
						<text v-if="detail.my_rating" class="stat-mine">你已评 {{ detail.my_rating }} 星</text>
					</view>
					<view class="stat-line"></view>
					<view class="stat">
						<text class="stat-num">{{ detail.usage_count }}</text>
						<text class="stat-label">人用过</text>
					</view>
					<view class="stat-line"></view>
					<view class="stat">
						<text class="stat-num">{{ totalMinutes }}</text>
						<text class="stat-label">分钟</text>
					</view>
				</view>
			</view>

			<view v-if="detail.description" class="block theme-card">
				<text class="block-title">什么时候用</text>
				<text class="block-text">{{ detail.description }}</text>
			</view>

			<view class="block theme-card">
				<view class="block-head">
					<text class="block-title">步骤预览</text>
					<text class="block-extra">共 {{ steps.length }} 步</text>
				</view>
				<view v-for="(s, i) in steps" :key="s.order" class="step">
					<view class="step-idx"><text class="step-idx-text">{{ i + 1 }}</text></view>
					<view class="step-main">
						<view class="step-head">
							<text class="step-title">{{ s.title }}</text>
							<text v-if="s.is_timed" class="step-dur">{{ formatDuration(s.duration_seconds) }}</text>
						</view>
						<text v-if="s.instruction" class="step-instruction">{{ s.instruction }}</text>
						<!-- #079：把这一步单独拆成一件小事（原子化进日程）；网页版未登录也先允许点，登录由 requireLogin 引导 -->
						<view class="step-add" hover-class="hover-dim" @click.stop="openStepTask(s, i)">
							<app-icon name="list-checks" :size="12" tone="muted" />
							<text class="step-add-text">加入任务</text>
						</view>
					</view>
				</view>
			</view>

			<!-- 作者：UGC 关掉时统一显示「官方」，不暴露用户昵称（ENABLE_UGC=true 时恢复真实作者） -->
			<view class="author-row">
				<text class="author-text">作者：{{ enableUgc ? (detail.author_name || '官方') : '官方' }}</text>
				<text v-if="enableUgc && detail.is_author" class="author-badge">你是作者</text>
			</view>

			<!-- #ifdef H5 -->
			<!-- 网页版：电脑端右栏（粘性）—— 来源/作者/评分 + 开始引导都收在这里；
			     手机端由 CSS 隐藏，继续用底部那条悬浮操作栏 -->
			<view class="h5-aside">
				<view class="h5-aside-card theme-card">
					<text class="h5-aside-head">开始行动</text>
					<view class="h5-aside-row">
						<text class="h5-aside-k">来源</text>
						<text class="h5-aside-v">官方模板库</text>
					</view>
					<view class="h5-aside-row">
						<text class="h5-aside-k">作者</text>
						<text class="h5-aside-v">{{ enableUgc ? (detail.author_name || '官方') : '官方' }}</text>
					</view>
					<view class="h5-aside-row">
						<text class="h5-aside-k">评分</text>
						<text class="h5-aside-v">{{ ratingText }}{{ detail.rating_count ? '（' + detail.rating_count + '）' : '' }}</text>
					</view>
					<view class="h5-aside-row">
						<text class="h5-aside-k">用时</text>
						<text class="h5-aside-v">{{ totalMinutes }} 分钟</text>
					</view>
					<view class="h5-aside-btn btn-accent" hover-class="hover-dim" @click="onStart"><text>开始引导</text></view>
					<!-- #079：加入我的任务（电脑端入口；与手机端底部操作栏同一个面板） -->
					<view class="h5-aside-btn btn-ghost" hover-class="hover-dim" @click="openPatternTask"><text>加入我的任务</text></view>
					<view class="h5-aside-btn btn-ghost" hover-class="hover-dim" @click="openShare"><text>分享这个模板</text></view>
					<!-- 桌面端底部操作栏是隐藏的，作者视角的编辑入口放这里（次按钮样式） -->
					<view v-if="enableUgc && detail.is_author" class="h5-aside-btn btn-ghost" hover-class="hover-dim" @click="onEdit">
						<text>编辑 / 发布</text>
					</view>
				</view>
			</view>
			<!-- #endif -->
			<view class="bar-space"></view>
		</scroll-view>

		<view v-else-if="loading" class="state">
			<view class="state-mark"><app-icon name="circle-notch" :size="28" tone="muted" /></view>
			<text class="state-title">加载中…</text>
		</view>

		<view v-else class="state">
			<view class="state-mark"><app-icon name="cloud-slash" :size="28" tone="muted" /></view>
			<text class="state-title">没能打开这个模板</text>
			<text class="state-desc">{{ errorMsg }}</text>
			<view class="state-btn btn-accent" @click="fetchDetail"><text>重试</text></view>
			<view class="state-btn btn-ghost" @click="goBack"><text>返回列表</text></view>
		</view>

		<view v-if="detail" class="action-bar">
			<!-- UGC 入口：ENABLE_UGC=false 时隐藏「编辑 / 发布」，onEdit 代码保留（utils/config.js） -->
			<view v-if="enableUgc && detail.is_author" class="btn-ghost action-secondary" @click="onEdit">
				<text>编辑 / 发布</text>
			</view>
			<!-- #079：加入我的任务（手机端入口） -->
			<view class="btn-ghost action-secondary action-task" hover-class="hover-dim" @click="openPatternTask">
				<text>加入任务</text>
			</view>
			<view class="btn-accent action-primary" @click="onStart">
				<text>开始引导</text>
			</view>
		</view>

		<!-- #079：加入我的任务 / 单步骤加入（同一面板，模式不同） -->
		<task-sheet
			:visible="taskSheetVisible"
			:mode="taskSheetMode"
			:pattern-id="id"
			:step-id="taskStepId"
			:hint="taskSheetHint"
			@close="taskSheetVisible = false"
			@done="onTaskAdded"
		/>

		<share-sheet :visible="shareVisible" :pattern-id="id" @close="shareVisible = false" />
	</view>
</template>

<script>
	import { get, post, errText } from '@/api/request.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { ENABLE_UGC, CAN_LOGIN } from '@/utils/config.js'
	// #073：结构图标统一走 app-icon（矢量，替代 emoji）
	import AppIcon from '@/components/app-icon/app-icon.vue'
	import { toStepList, formatDuration, SOURCE_QUICK } from '@/utils/adapter.js'
	import { ensureLogin } from '@/utils/token.js'
	import ShareSheet from '@/components/share-sheet/share-sheet.vue'
	import TaskSheet from '@/components/task-sheet/task-sheet.vue'

	export default {
		components: { ShareSheet, AppIcon, TaskSheet },
		data() {
			return {
				statusBarHeight: 20,
				// 导航栏尺寸（对齐微信胶囊），onLoad 里用 getNavBarMetrics() 填
				nav: {},
				// UGC 开关：控制「编辑 / 发布」入口与作者显示（utils/config.js）
				enableUgc: ENABLE_UGC,
				// 网页版第一版不做登录：收藏这类要身份的入口先隐藏（utils/config.js）
				canLogin: CAN_LOGIN,
				id: '',
				// #072⑤：来源（'search' = 从搜索页点进来的）+ 当时的搜索词，返回时用得上
				from: '',
				fromQuery: '',
				detail: null,
				loading: false,
				errorMsg: '',
				favSubmitting: false,
				shareVisible: false,
				// #079：加入我的任务面板（pattern=整条加入 / step=单步骤拆开）
				taskSheetVisible: false,
				taskSheetMode: 'pattern',
				taskStepId: '',
				taskSheetHint: ''
			}
		},
		computed: {
			// 走适配器归一成 step_data，下一阶段执行页拿到的就是同一份结构
			steps() {
				return this.detail ? toStepList(this.detail.steps, SOURCE_QUICK) : []
			},
			ratingText() {
				if (!this.detail) return '—'
				return this.detail.rating_count > 0 ? Number(this.detail.avg_rating).toFixed(1) : '暂无'
			},
			totalMinutes() {
				const total = this.steps.reduce((sum, s) => sum + (s.duration_seconds || 0), 0)
				return total ? Math.max(1, Math.round(total / 60)) : '—'
			}
		},
		onLoad(options) {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
			this.id = (options && options.id) || ''
			// #072⑤：记下来源，返回键据此回搜索页（并带上原搜索词）。
			// 两端对 q 的解码行为不一致（H5 已解、部分端是原文），这里解一次并兜住异常
			this.from = (options && options.from) || ''
			this.fromQuery = ''
			if (options && options.q) {
				try {
					this.fromQuery = decodeURIComponent(options.q)
				} catch (e) {
					this.fromQuery = options.q
				}
			}
			if (!this.id) {
				this.errorMsg = '缺少模板 id，请从列表进入'
				return
			}
			this.fetchDetail()
		},
		onShow() {
			// 从执行页回来时评分/收藏可能刚变过，重拉一次让状态收敛（首次进页面 detail 还是 null，不会重复请求）
			if (this.detail) this.fetchDetail()
		},
		// 转发卡片：好友点开直达这个模板详情
		onShareAppMessage() {
			const d = this.detail || {}
			const title = d.title ? d.title + (d.tagline ? ' · ' + d.tagline : '') : '行动锚 · 现在就能做的一件小事'
			return {
				title: title,
				path: '/pages/detail/detail?id=' + this.id
			}
		},
		methods: {
			formatDuration,

			// ===== #079：加入我的任务 =====
			openPatternTask() {
				this.taskSheetMode = 'pattern'
				this.taskStepId = ''
				this.taskSheetHint = '把「' + (this.detail ? this.detail.title : '这个模板') + '」整条加进我的任务，步骤会原样复制一份（模板以后改了不影响你这条）。'
				this.taskSheetVisible = true
			},
			openStepTask(step, index) {
				// 用模板里这一步的原始 id：后端 from-step 要的是 QuickStep 主键
				const raw = (this.detail && this.detail.steps) || []
				const source = raw[index] || {}
				this.taskSheetMode = 'step'
				this.taskStepId = source.id || ''
				this.taskSheetHint = '只把「' + (step.title || '这一步') + '」拆成一件独立的小事。'
				this.taskSheetVisible = true
			},
			onTaskAdded(task) {
				if (!task) return
				uni.showToast({ title: '加好了，去「我的任务」看看', icon: 'none' })
			},

			async fetchDetail() {
				if (!this.id || this.loading) return
				this.loading = true
				this.errorMsg = ''
				try {
					this.detail = await get('/quick/' + this.id + '/', null, { silent: true })
				} catch (e) {
					this.detail = null
					// 网络层失败只有 errMsg（没有 data.error），用 errText 统一取值，别把真实原因吞掉
					this.errorMsg = errText(e, '请求失败，检查后端是否启动、网络是否可达')
				} finally {
					this.loading = false
				}
			},

			goBack() {
				// #058③：分三种情况，按"真有上一页"来判断，别让返回键变成隐藏的"回首页"。
				// 1) 页面栈里有上一页（正常从列表点进来）→ navigateBack
				if (getCurrentPages().length > 1) {
					uni.navigateBack()
					return
				}
				// #072⑤：从搜索页进来但页面栈已经没了（网页版刷新过）→ 回到搜索页，
				// 并把搜索词带上（搜索页 onLoad 会拿 q 重搜），而不是回首页
				// #ifdef H5
				if (this.from === 'search') {
					uni.redirectTo({ url: '/pages/search/search?q=' + encodeURIComponent(this.fromQuery) })
					return
				}
				// #endif
				// #ifdef H5
				// 2) 网页版：页面栈只有 1，但浏览器历史里确实有上一页
				//    （分享链接点进来又刷新过、或从别处跳进来）→ 用浏览器返回，回到用户来的地方。
				//    以前这里直接 reLaunch 首页，"点了没回到刚才那页"就是这么来的。
				if (typeof window !== 'undefined' && window.history && window.history.length > 1) {
					window.history.back()
					return
				}
				// #endif
				// 3) 真的没有上一页（新标签直接打开详情）→ 回首页兜底
				uni.reLaunch({ url: '/pages/library/library' })
			},

			onStart() {
				// 执行页只有滚轴式一种形态（D1），不再传 mode
				uni.navigateTo({ url: '/pages/execute/execute?id=' + this.id })
			},

			onEdit() {
				// 编辑/发布要身份：先静默登录，再进创建页的编辑模式
				ensureLogin()
					.then(() => uni.navigateTo({ url: '/pages/create/create?id=' + this.id }))
					.catch(() => uni.showToast({ title: '登录没成，再试一次', icon: 'none' }))
			},

			openShare() {
				this.shareVisible = true
			},

			onToggleFavorite() {
				if (this.favSubmitting || !this.detail) return
				this.favSubmitting = true
				const next = !this.detail.is_favorited
				ensureLogin()
					.then(() => post('/quick/' + this.id + '/' + (next ? 'favorite' : 'unfavorite') + '/', {}, { silent: true }))
					.then((d) => {
						this.detail.is_favorited = !!(d && d.favorited)
						uni.showToast({ title: this.detail.is_favorited ? '已收藏' : '已取消收藏', icon: 'none' })
					})
					.catch((e) => {
						// 未登录时 requireLogin 会把人带去登录页，这里只提示一句，别说成"失败"
						if (e && e.needLogin) {
							uni.showToast({ title: '登录一下就好', icon: 'none' })
							return
						}
						uni.showToast({ title: '没成功，再点一次', icon: 'none' })
					})
					.then(() => {
						this.favSubmitting = false
					})
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
		border-bottom: 2rpx solid var(--border);
	}

	/* 高度/上边距以微信胶囊为准，由 nav.navInnerStyle 注入；
	   下面这组静态值 = 拿不到胶囊数据时的兜底。右侧没有可见内容，所以不用给胶囊留白 */
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

	.body {
		flex: 1;
		height: 0;
	}

	/* ===== 头部信息 ===== */
	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		margin: 24rpx;
		padding: 48rpx 32rpx 32rpx;
	}

	.hero-icon {
		width: 128rpx;
		height: 128rpx;
		border-radius: 32rpx;
		background-color: var(--bg);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.hero-emoji {
		font-size: 64rpx;
	}

	.hero-title {
		margin-top: 24rpx;
		font-size: 40rpx;
		font-weight: 700;
		color: var(--text);
		text-align: center;
	}

	.hero-tagline {
		margin-top: 12rpx;
		font-size: 28rpx;
		color: var(--muted);
		text-align: center;
	}

	.hero-tags {
		display: flex;
		align-items: center;
		margin-top: 20rpx;
	}

	.hero-tags .tag {
		margin: 0 8rpx;
	}

	/* 收藏 / 分享两个胶囊并排 */
	.hero-acts {
		display: flex;
		align-items: center;
		margin-top: 20rpx;
	}

	/* 88rpx = 44px，满足触控目标标准 */
	.hero-fav {
		margin: 0 8rpx;
		height: 88rpx;
		padding: 0 40rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
	}

	.hero-fav-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	.hero-fav-ico {
		margin-right: 10rpx;
	}

	.hero-fav-text {
		font-size: 26rpx;
		color: var(--muted);
	}

	.hero-fav-on .hero-fav-text {
		color: var(--accent);
		font-weight: 600;
	}

	.hero-stats {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100%;
		margin-top: 40rpx;
		padding-top: 32rpx;
		border-top: 2rpx solid var(--border);
	}

	.stat {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.stat-num {
		font-size: 36rpx;
		font-weight: 700;
		color: var(--text);
	}

	.stat-label-row {
		display: flex;
		align-items: center;
		margin-top: 8rpx;
	}

	.stat-label {
		margin-left: 6rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	.stat-mine {
		margin-top: 6rpx;
		font-size: 20rpx;
		color: var(--accent);
	}

	.stat-line {
		width: 2rpx;
		height: 48rpx;
		background-color: var(--border);
	}

	/* ===== 内容块 ===== */
	.block {
		margin: 0 24rpx 24rpx;
		padding: 32rpx;
	}

	.block-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}

	.block-title {
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
	}

	.block-extra {
		font-size: 24rpx;
		color: var(--muted);
	}

	.block-text {
		display: block;
		margin-top: 16rpx;
		font-size: 28rpx;
		color: var(--text);
		line-height: 1.7;
	}

	/* ===== 步骤 ===== */
	.step {
		display: flex;
		margin-top: 32rpx;
	}

	.step-idx {
		flex-shrink: 0;
		width: 48rpx;
		height: 48rpx;
		margin-right: 20rpx;
		border-radius: 24rpx;
		background-color: var(--accent-soft);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.step-idx-text {
		font-size: 24rpx;
		font-weight: 600;
		color: var(--accent);
	}

	.step-main {
		flex: 1;
		min-width: 0;
	}

	.step-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.step-title {
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
	}

	.step-dur {
		flex-shrink: 0;
		margin-left: 16rpx;
		font-size: 24rpx;
		color: var(--accent);
	}

	.step-instruction {
		display: block;
		margin-top: 8rpx;
		font-size: 26rpx;
		color: var(--muted);
		line-height: 1.6;
	}

	/* #079：把单步拆成小事的入口，弱化成一行小字，不跟步骤正文抢注意力 */
	.step-add {
		display: inline-flex;
		align-items: center;
		margin-top: 12rpx;
		padding: 8rpx 16rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
	}

	.step-add-text {
		margin-left: 8rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	/* ===== 作者 ===== */
	.author-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 8rpx 40rpx 0;
	}

	.author-text {
		font-size: 24rpx;
		color: var(--muted);
	}

	.author-badge {
		font-size: 24rpx;
		color: var(--accent);
	}

	/* ===== 状态页 ===== */
	.state {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 0 64rpx;
	}

	.state-mark {
		width: 112rpx;
		height: 112rpx;
		border-radius: 50%;
		background-color: var(--card);
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.state-title {
		margin-top: 24rpx;
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text);
	}

	.state-desc {
		margin-top: 12rpx;
		font-size: 26rpx;
		color: var(--muted);
		text-align: center;
	}

	.state-btn {
		margin-top: 24rpx;
		padding: 0 64rpx;
	}

	/* ===== 底部操作栏 ===== */
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

	.action-secondary {
		flex-shrink: 0;
		width: 240rpx;
		margin-right: 20rpx;
	}

	.action-primary {
		flex: 1;
	}

	/* #079：底部栏多了一个「加入任务」，跟着主按钮分剩下的宽度（作者还有「编辑/发布」，别把按钮挤扁） */
	.action-task {
		flex: 1;
		width: auto;
		min-width: 0;
	}

	.bar-space {
		height: 40rpx;
	}
	/* ===== 网页版（H5）：电脑端左右分栏 + 粘性侧栏（设计规范 §7.2） ===== */
	/* #ifdef H5 */
	/* 手机/平板不显示右栏，继续用底部那条操作栏 */
	.h5-aside {
		display: none;
	}

	/* uni-app H5 的 scroll-view 真实结构：
	   uni-scroll-view > div.uni-scroll-view > div.uni-scroll-view(滚动容器, overflow-y:auto) > div.uni-scroll-view-content
	   页面内容挂在 .uni-scroll-view-content 上——它是 uni 的内部元素，没有页面的 data-v 属性，
	   所以必须用 :deep() 穿透作用域，否则选择器根本匹配不上（格子加不上去）。 */
	@media (min-width: 1024px) {
		.body :deep(.uni-scroll-view-content) {
			display: grid;
			grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
			column-gap: 32px;
			align-content: start;
			box-sizing: border-box;
			padding: 28px var(--content-pad) 40px;
		}
		.body :deep(.uni-scroll-view-content) > .hero,
		.body :deep(.uni-scroll-view-content) > .block {
			grid-column: 1;
		}
		/* 作者信息移进右栏，正文里不再重复 */
		.body :deep(.uni-scroll-view-content) > .author-row,
		.body :deep(.uni-scroll-view-content) > .bar-space {
			display: none;
		}
		.h5-aside {
			display: block;
			grid-column: 2;
			grid-row: 1 / span 6;   /* 跨满左栏所有行，sticky 才能一路跟着滚 */
			align-self: start;
			position: sticky;
			top: 24px;
		}
		/* 桌面端用右栏的「开始引导」，不要底部条 */
		.action-bar {
			display: none;
		}
		.hero-title {
			font-size: 26px;
		}
	}

	.h5-aside-card {
		padding: 20px;
	}
	.h5-aside-head {
		display: block;
		font-size: 16px;
		font-weight: 600;
		color: var(--text);
	}
	.h5-aside-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: 14px;
	}
	.h5-aside-k {
		font-size: 13px;
		color: var(--muted);
	}
	.h5-aside-v {
		font-size: 13px;
		color: var(--text);
	}
	.h5-aside-btn {
		margin-top: 16px;
		height: 44px;
		border-radius: var(--r-btn);
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 15px;
	}
	/* #035 ④：详情页大图标底 32rpx（手机上≈21px）收小一档，跟卡片同一套 */
	.hero-icon {
		border-radius: var(--r-btn);
	}
	/* #endif */
	/* ===== 网页版（H5）：贴底操作栏（#030 ⑤） ===== */
	/* #ifdef H5 */
	/* 操作栏本来就是页面 flex 的最后一格，但手机地址栏展开时 100vh > 可视高度，
	   它会跟着被推到屏幕外。改成 fixed 钉在可视视口底部，并留 iPhone 底部横条的安全区；
	   正文末尾补足高度，别让最后一行被操作栏压住。 */
	@media (max-width: 1023px) {
		.action-bar {
			position: fixed;
			left: 0;
			right: 0;
			bottom: 0;
			z-index: 20;
		}
		.bar-space {
			height: 120px;
		}
	}
	/* #endif */
</style>
