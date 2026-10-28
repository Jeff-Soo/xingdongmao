<template>
	<view class="page">
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">我的</text>
				<view class="nav-btn nav-btn-ghost"></view>
			</view>
		</view>

		<view class="tabs">
			<view
				v-for="t in tabs"
				:key="t.key"
				class="tab"
				:class="{ 'tab-on': tab === t.key }"
				hover-class="hover-dim"
				@click="switchTab(t.key)"
			>
				<text class="tab-text">{{ t.label }}</text>
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
			<!-- #ifdef H5 -->
			<!-- 网页版登录后：账号（邮箱）+ 退出登录 -->
			<view v-if="email" class="account-row">
				<text class="account-email">{{ email }}</text>
				<text class="account-out" hover-class="hover-dim" @click="onLogout">退出登录</text>
			</view>

			<!-- #058⑩ 的资料卡， #071 起【手机端也显示】并升级成"资料区"：
			     头像 + 用户名（昵称优先，兜底「行动锚用户」，不露机器号）+ 编辑 + 退出。 -->
			<view class="mine-profile">
				<view class="mp-head">
					<image v-if="profile.avatar_url" class="mp-avatar-img" :src="profile.avatar_url" mode="aspectFill" />
					<view v-else class="mp-avatar"><text class="mp-avatar-text">{{ avatarLetter }}</text></view>
					<view class="mp-id">
						<text class="mp-name">{{ loggedIn ? profile.display_name : '未登录' }}</text>
						<text class="mp-sub">{{ loggedIn ? '已登录 · 可改昵称/头像' : (canLogin ? '登录后可以收藏、评分、写反思' : '网页版暂不支持登录') }}</text>
					</view>
					<view v-if="canLogin && loggedIn" class="mp-act btn-ghost" hover-class="hover-dim" @click="openProfileEdit">
						<text>编辑资料</text>
					</view>
					<view v-if="canLogin" class="mp-act mp-act-plain" hover-class="hover-dim" @click="loggedIn ? onLogout() : onLogin()">
						<text>{{ loggedIn ? '退出' : '登录 / 注册' }}</text>
					</view>
				</view>

				<view class="mp-stats">
					<view class="mp-stat" hover-class="hover-dim" @click="switchTab('created')">
						<text class="mp-num">{{ countText('created') }}</text>
						<text class="mp-label">我创建的</text>
					</view>
					<view class="mp-stat" hover-class="hover-dim" @click="switchTab('favorites')">
						<text class="mp-num">{{ countText('favorites') }}</text>
						<text class="mp-label">我的收藏</text>
					</view>
					<view class="mp-stat" hover-class="hover-dim" @click="switchTab('notes')">
						<text class="mp-num">{{ countText('notes') }}</text>
						<text class="mp-label">我的笔记</text>
					</view>
				</view>

				<view class="mp-actions">
					<view v-if="enableUgc" class="mp-btn btn-accent" hover-class="hover-dim" @click="goCreate"><text>＋ 创建模板</text></view>
					<view class="mp-btn btn-ghost" hover-class="hover-dim" @click="replayOnboarding"><text>再看教程</text></view>
				</view>

				<!-- #079：我的任务入口（资料卡里，登录/未登录都能看到；未登录点进去会引导登录） -->
				<view class="mp-task" hover-class="hover-dim" @click="goTasks">
					<app-icon name="list-checks" :size="16" tone="accent" />
					<text class="mp-task-text">我的任务</text>
					<text class="mp-task-sub">今日安排 · 打勾进度</text>
					<text class="mp-task-arrow">›</text>
				</view>

				<view class="mp-how">
					<text class="mp-how-title">怎么用</text>
					<text class="mp-how-text">① 挑一个模板 → ② 照着卡片一步步做 → ③ 做完写一句「以后我会怎么做」</text>
				</view>
			</view>
			<!-- #endif -->

			<view v-if="loading && !list.length" class="state">
				<view class="state-mark"><app-icon name="circle-notch" :size="28" tone="muted" /></view>
				<text class="state-title">加载中…</text>
			</view>

			<!-- 未登录：不弹登录墙，给一个明确入口（浏览路径仍然零门槛）
			     网页版没有微信登录，这里换成"去小程序看"的说明 -->
			<view v-else-if="needLogin" class="state">
				<view class="state-mark"><app-icon :name="canLogin ? 'key' : 'globe-hemisphere-west'" :size="28" tone="muted" /></view>
				<text class="state-title">{{ canLogin ? '登录一下，收藏和笔记才存得住' : '网页版暂不支持登录' }}</text>
				<text class="state-desc">{{ canLogin ? accountDesc : '收藏和笔记在小程序「行动锚」里看；网页版可以随便翻、随便执行' }}</text>
				<view v-if="canLogin" class="state-btn btn-accent" hover-class="hover-dim" @click="onLogin"><text>{{ isH5 ? '登录 / 注册' : '登录' }}</text></view>
			</view>

			<view v-else-if="!list.length" class="state">
				<view class="state-mark"><app-icon :name="emptyIcon" :size="28" tone="muted" /></view>
				<text class="state-title">{{ emptyTitle }}</text>
				<text class="state-desc">{{ emptyDesc }}</text>
			</view>

			<view v-else class="list">
				<!-- 我创建的：顶部放创建入口（UGC 关掉后连这个 tab 都不显示，这里再兜一层） -->
				<view v-if="enableUgc && tab === 'created'" class="create-row">
					<view class="create-btn" hover-class="hover-dim" @click="goCreate"><text class="create-text">＋ 创建模板</text></view>
				</view>

				<!-- #071 草稿管理：一眼看出有几篇草稿，点一下只看草稿（编辑/发布/删除都在卡片上） -->
				<view v-if="tab === 'created'" class="draft-chips">
					<view class="draft-chip" :class="{ 'draft-chip-on': draftFilter === 'all' }" hover-class="hover-dim" @click="draftFilter = 'all'">
						<text>全部 {{ draftCounts.all }}</text>
					</view>
					<view class="draft-chip" :class="{ 'draft-chip-on': draftFilter === 'draft' }" hover-class="hover-dim" @click="draftFilter = 'draft'">
						<text>草稿 {{ draftCounts.draft }}</text>
					</view>
					<view class="draft-chip" :class="{ 'draft-chip-on': draftFilter === 'listed' }" hover-class="hover-dim" @click="draftFilter = 'listed'">
						<text>已上架 {{ draftCounts.listed }}</text>
					</view>
				</view>

				<!-- #071 草稿箱空态提示 -->
				<view v-if="tab === 'created' && !shownList.length && list.length" class="draft-empty">
					<text>{{ draftFilter === 'draft' ? '没有草稿了，都发布出去了' : '这个筛选下还空着' }}</text>
				</view>

				<view v-for="item in shownList" :key="item.key" class="card theme-card" @click="goDetail(item.patternId)">
					<view class="card-icon">
						<app-icon v-if="item.iconKey" :name="item.iconKey" :size="26" tone="accent" />
						<text v-else class="card-emoji">{{ item.icon || '🧠' }}</text>
					</view>
					<view class="card-main">
						<view class="card-title-row">
							<text class="card-title">{{ item.title }}</text>
							<text v-if="item.statusLabel" class="status" :class="item.statusClass">{{ item.statusLabel }}</text>
						</view>
						<text v-if="item.body" class="card-body">{{ item.body }}</text>
						<text v-else-if="item.subtitle" class="card-sub">{{ item.subtitle }}</text>
						<text v-if="item.meta" class="card-meta">{{ item.meta }}</text>

						<!-- 我创建的：管理操作（.stop 防止冒泡到卡片的"看详情"） -->
						<view v-if="tab === 'created'" class="ops">
							<view class="op" hover-class="hover-dim" @click.stop="goEdit(item.patternId)"><text>编辑</text></view>
							<view v-if="item.canPublish" class="op op-main" hover-class="hover-dim" @click.stop="onPublish(item)"><text>发布</text></view>
							<view class="op op-del" hover-class="hover-dim" @click.stop="onDelete(item)"><text>删除</text></view>
						</view>
					</view>
				</view>
			</view>

			<!-- #ifdef H5 -->
			<!-- #040：重看新手引导（先全屏引导，看完回首页继续蒙层高亮） -->
			<view class="tutorial-row" hover-class="hover-dim" @click="replayOnboarding">
				<text class="tutorial-text">再看教程</text>
				<text class="tutorial-arrow">›</text>
			</view>
			<!-- #endif -->

			<!-- 粤ICP备2026144076号：法规 + 微信审核要求必须在显著位置展示。
			     放在滚动区末尾而不是某个分支里，保证加载 / 未登录 / 空列表 / 有列表四种状态都看得到 -->
			<view class="beian" hover-class="hover-dim" @click="copyBeian">
				<text class="beian-text">{{ beian }}</text>
			</view>

			<view class="safe-bottom"></view>
		</scroll-view>

		<!-- #ifdef H5 -->
		<!-- #040：全屏引导（"再看教程"时在本页重放） -->
		<!-- #071 编辑资料弹层：改昵称 / 换头像 -->
		<view v-if="editVisible" class="mask" @click="editVisible = false">
			<view class="sheet" @click.stop>
				<view class="sheet-head">
					<text class="sheet-title">编辑资料</text>
					<text class="sheet-close" hover-class="hover-dim" @click="editVisible = false">✕</text>
				</view>
				<view class="pf-row">
					<image v-if="profile.avatar_url" class="pf-avatar" :src="profile.avatar_url" mode="aspectFill" />
					<view v-else class="pf-avatar pf-avatar-empty"><text>{{ avatarLetter }}</text></view>
					<view class="pf-btn btn-ghost" hover-class="hover-dim" @click="chooseAvatar">
						<text>{{ uploadingAvatar ? '上传中…' : '换头像' }}</text>
					</view>
				</view>
				<view class="pf-field">
					<text class="pf-label">昵称（2-30 字，不能是纯数字）</text>
					<input class="pf-input" v-model="editNickname" :maxlength="30" placeholder="比如：小北" placeholder-class="ph" />
				</view>
				<text class="pf-hint">昵称会显示在模板作者名和分享图上；留空则显示「行动锚用户」</text>
				<view class="pf-actions">
					<view class="btn-ghost pf-act" hover-class="hover-dim" @click="editVisible = false"><text>取消</text></view>
					<view class="btn-accent pf-act" hover-class="hover-dim" @click="saveProfile"><text>{{ savingProfile ? '保存中…' : '保存' }}</text></view>
				</view>
			</view>
		</view>
		<onboarding-intro :visible="introVisible" @done="onIntroDone" />
		<!-- #endif -->
	</view>
</template>

<script>
	import { get, post, request, BASE_URL, errText } from '@/api/request.js'
	import { ensureLogin, isLoggedIn, getEmail, clearToken } from '@/utils/token.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { ENABLE_UGC, CAN_LOGIN, IS_H5 } from '@/utils/config.js'
	// #073：结构图标统一走 app-icon（矢量，替代 emoji）
	import AppIcon from '@/components/app-icon/app-icon.vue'
	// #057⑮：这个组件只在 H5 用（模板里已经包在条件编译里），import 和注册也一起加条件，
	// 否则小程序包里会打进去一份用 document/window 的死代码
	// #ifdef H5
	import OnboardingIntro from '@/components/onboarding-intro/onboarding-intro.vue'
	// #endif
	import { resetOnboarding, markIntroDone } from '@/utils/onboarding.js'

	const TABS = [
		{ key: 'favorites', label: '我的收藏' },
		{ key: 'notes', label: '我的笔记' },
		{ key: 'created', label: '我创建的' },
		// #071：浏览记录（后端记的，只记公开模板）
		{ key: 'history', label: '浏览记录' }
	]

	const PATHS = {
		favorites: '/quick/my-favorites/',
		notes: '/quick/my-notes/',
		created: '/quick/me/',
		history: '/quick/history/'
	}

	// 后端 status 枚举 → 标签文案
	const STATUS_LABELS = {
		draft: '草稿',
		published: '已发布',
		verified: '社区推荐',
		// #057⑩：被举报/被下架的模板要能看出"待复核"。以前没有这个标签，
		// 作者只会看到"草稿"，以为是自己没发布
		reported: '待复核'
	}

	export default {
		// #ifdef H5
		components: { OnboardingIntro, AppIcon },
		// #endif
		// #ifndef H5
		components: { AppIcon },
		// #endif
		data() {
			return {
				statusBarHeight: 20,
				// #040：点"再看教程"后在本页重放全屏引导
				introVisible: false,
				// 导航栏尺寸（对齐微信胶囊），onLoad 里用 getNavBarMetrics() 填
				nav: {},
				// UGC 关掉时「我创建的」tab 不渲染；TABS 常量保留，改开关即可恢复
				tabs: ENABLE_UGC ? TABS : TABS.filter((t) => t.key !== 'created'),
				enableUgc: ENABLE_UGC,
				// 网页版可以邮箱登录了（#027）：两边都能登录 → 收藏/笔记/评分全开
				canLogin: CAN_LOGIN,
				isH5: IS_H5,
				// 网页版登录后显示账号邮箱（登录页写进 storage 的）
				email: '',
				// 登录墙文案里也不该出现已隐藏的功能名
				accountDesc: ENABLE_UGC ? '收藏、笔记、我创建的都挂在账号上' : '收藏、笔记都挂在账号上',
				tab: 'favorites',
				list: [],
				loading: false,
				refreshing: false,
				// #058⑩：资料卡上的三个计数（null = 还不知道，界面显示 —）
				counts: { created: null, favorites: null, notes: null },
				needLogin: false,
				// 备案号：展示与复制共用一处，避免两处文案走偏
				beian: '粤ICP备2026144076号',
				// 首屏拉过一次之后，onShow 才需要重拉（避免进页面拉两次）
				loaded: false,
				// #071 资料区：昵称/头像（后端 /me/profile/）
				profile: {},
				// #071 编辑资料弹层
				editVisible: false,
				editNickname: '',
				savingProfile: false,
				uploadingAvatar: false,
				// #071 我创建的：草稿筛选（all / draft / listed）
				draftFilter: 'all'
			}
		},
		computed: {
			// #071：登录态看 token（网页邮箱登录或小程序静默登录都算）
			loggedIn() {
				return !!this.email || isLoggedIn()
			},
			// 头像兜底：优先昵称首字，其次「锚」
			avatarLetter() {
				const n = (this.profile && this.profile.display_name) || ''
				return n && n !== '行动锚用户' ? n.slice(0, 1) : '锚'
			},
			// #071 草稿管理：我创建的里按 is_listed 分类，chip 上显示条数
			draftCounts() {
				if (this.tab !== 'created') return { all: 0, draft: 0, listed: 0 }
				const draft = this.list.filter((x) => !x.isListed).length
				return { all: this.list.length, draft: draft, listed: this.list.length - draft }
			},
			// 列表渲染用这个（只有"我创建的"会按 chip 过滤）
			shownList() {
				if (this.tab !== 'created' || this.draftFilter === 'all') return this.list
				const wantDraft = this.draftFilter === 'draft'
				return this.list.filter((x) => (!x.isListed) === wantDraft)
			},
			emptyIcon() {
				// #073：空态不再用 emoji（📝/🍃），改成同一套线条图标
				return this.tab === 'notes' ? 'note-blank' : 'tray'
			},
			emptyTitle() {
				if (this.tab === 'notes') return '还没写过笔记'
				if (this.tab === 'created') return '还没自己做过卡'
				return '还没收藏过'
			},
			emptyDesc() {
				if (this.tab === 'notes') return '做完一件事，顺手写一句「下次我会怎么做」，就存在这'
				if (this.tab === 'created') return '上面那个「＋ 创建模板」，把你自己的做法写下来'
				return '看到有用的点★收起来，都在这'
			}
		},
		onLoad(options) {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
			// 支持 /pages/mine/mine?tab=created 直达某个分区（创建完草稿会跳这里）
			// 只认当前可见的分区：UGC 关掉后 ?tab=created 也不能再切进去
			const want = options && options.tab
			if (want && PATHS[want] && this.tabs.some((t) => t.key === want)) this.tab = want
			this.fetchList()
			// #058⑩：资料卡的三个计数（登录了才拉；静默失败不影响主流程）
			this.fetchCounts()
				this.fetchProfile()
		},
		onShow() {
			// 从创建页/登录页返回时列表和账号都可能变了，重拉一次；首屏这次由 onLoad 负责，不重复
			this.email = getEmail()
			if (this.loaded) {
				this.fetchList()
				this.fetchCounts()
				this.fetchProfile()
			}
		},
		methods: {
			// #058⑩：资料卡上的三个计数。只拉第 1 页数据来数（静默、失败就当未知），
			// 不新增后端接口；打开对应 tab 后本地就知道准确条数。
			async fetchCounts() {
				if (!isLoggedIn()) return
				// #ifdef H5
				const keys = ['created', 'favorites', 'notes']
				await Promise.all(keys.map(async (k) => {
					try {
						const data = await get(PATHS[k], null, { silent: true })
						this.counts[k] = Array.isArray(data) ? data.length : 0
					} catch (e) {
						// 静默失败：保持 null，界面上显示 —
					}
				}))
				// #endif
			},
			countText(key) {
				const n = this.counts[key]
				// 没登录时不给数字（避免"0 个"误导），显示 —
				if (n === null || n === undefined) return '—'
				return String(n)
			},

			// ===== #071 资料区：昵称 / 头像 =====
			async fetchProfile() {
				if (!isLoggedIn()) { this.profile = {}; return }
				try {
					this.profile = await get('/me/profile/', null, { silent: true })
				} catch (e) {
					this.profile = {}
				}
			},
			openProfileEdit() {
				this.editNickname = (this.profile && this.profile.nickname) || ''
				this.editVisible = true
			},
			async saveProfile() {
				if (this.savingProfile) return
				const nickname = (this.editNickname || '').trim()
				if (nickname && /^\d+$/.test(nickname)) {
					uni.showToast({ title: '昵称里加点别的吧，纯数字认不出你', icon: 'none' })
					return
				}
				this.savingProfile = true
				try {
					this.profile = await request('/me/profile/', 'PUT', { nickname: nickname }, { silent: true })
					uni.showToast({ title: '存好了', icon: 'none' })
					this.editVisible = false
					this.fetchList()
				} catch (e) {
					uni.showToast({ title: errText(e, '保存失败'), icon: 'none' })
				} finally {
					this.savingProfile = false
				}
			},
			chooseAvatar() {
				if (this.uploadingAvatar) return
				uni.chooseImage({
					count: 1,
					sizeType: ['compressed'],
					sourceType: ['album', 'camera'],
					success: (res) => {
						const path = (res.tempFilePaths || [])[0]
						if (!path) return
						this.uploadingAvatar = true
						uni.uploadFile({
							url: BASE_URL + '/me/avatar/',
							filePath: path,
							name: 'avatar',
							header: { Authorization: 'Token ' + (uni.getStorageSync('token') || '') },
							success: (up) => {
								let data = {}
								try { data = JSON.parse(up.data || '{}') } catch (e) { data = {} }
								if (up.statusCode === 200 && data.ok) {
									this.profile = data.data
									uni.showToast({ title: '头像换好了', icon: 'none' })
								} else {
									uni.showToast({ title: (data.data && data.data.error) || '没传上去，再试一次', icon: 'none' })
								}
							},
							fail: () => uni.showToast({ title: '没传上去，检查一下网络', icon: 'none' }),
							complete: () => { this.uploadingAvatar = false }
						})
					}
				})
			},
			// #040：重看教程 —— 先清掉两个标记（回到"首次打开"的状态），在本页放全屏引导；
			// 引导看完再回首页，首页会接着弹蒙层高亮（tour 标记也是清的）
			replayOnboarding() {
				resetOnboarding()
				this.introVisible = true
			},
			onIntroDone() {
				this.introVisible = false
				markIntroDone()
				uni.reLaunch({ url: '/pages/index/index' })
			},
			async fetchList() {
				if (this.loading) return
				this.needLogin = false

				// 进"我的"要看自己的内容，没登录就展示登录入口。
				// 这里只用被动的 isLoggedIn()，不调 requireLogin()——否则一进页面就被弹去登录页。
				// 小程序端维持"静默 wx.login"：能拿到 token 就当已登录，拿不到才走登录墙。
				if (!isLoggedIn()) {
					// #ifndef H5
					try {
						await ensureLogin()
					} catch (e) {
						this.needLogin = true
					}
					// #endif
					// #ifdef H5
					this.needLogin = true
					// #endif
					if (this.needLogin) {
						this.list = []
						this.refreshing = false
						this.loaded = true
						return
					}
				}
				this.email = getEmail()

				this.loading = true
				try {
					const data = await get(PATHS[this.tab], null, { silent: true })
					const rows = Array.isArray(data) ? data : []
					this.list = rows.map((r) => this.normalize(this.tab, r))
					// #058⑩：这次拉到的就是权威条数，顺手更新资料卡上的计数
					this.counts[this.tab] = rows.length
				} catch (e) {
					this.list = []
					const msg = (e && e.data && e.data.error) || ''
					if (msg.indexOf('认证') >= 0) this.needLogin = true
				} finally {
					this.loading = false
					this.refreshing = false
					this.loaded = true
				}
			},

			// 三个接口返回结构不同，统一成一份展示结构，模板只写一遍
			normalize(tab, raw) {
				if (tab === 'notes') {
					return {
						key: 'n' + raw.id,
						patternId: raw.pattern_id,
						icon: raw.pattern_icon,
						// #073：后端同时下发 icon_key（slug），优先用它渲染矢量图标，emoji 只做回退
						iconKey: raw.pattern_icon_key || '',
						title: raw.pattern_title || '模板已删除',
						subtitle: '',
						body: raw.content,
						meta: this.formatTime(raw.created_at),
						status: '',
						statusLabel: '',
						statusClass: ''
					}
				}
				// #057⑩：状态标签改用后端新下发的三个布尔（is_listed/is_verified/is_reported）
				// 派生，不再依赖老的 status —— 下架(reported) 以前会被显示成"草稿"。
				// 老版本后端没这三个字段时回退到 status（兼容旧部署）。
				const flagKey = this.statusKeyOf(raw)
				return {
					key: tab.charAt(0) + raw.id,
					patternId: raw.id,
					icon: raw.icon,
					iconKey: raw.icon_key || '',
					title: raw.title,
					subtitle: raw.tagline || '',
					body: '',
					// #071 浏览记录：显示「看过的时间」，其它 tab 还是原来的 meta
					meta: tab === 'history' ? ('看过 · ' + this.formatTime(raw.viewed_at)) : this.metaOf(tab, raw),
					status: raw.status || '',
					// 只有"我创建的"需要状态标签（收藏/笔记 tab 不显示）
					statusLabel: tab === 'created' ? (STATUS_LABELS[flagKey] || '') : '',
					statusClass: tab === 'created' ? 'status-' + flagKey : '',
					// #071：草稿筛选要用它（我创建的 tab）
					isListed: raw.is_listed === true,
					// 发布入口按布尔判断：只有真·草稿（未上架/未推荐/未被处置）才给"发布"；
					// 被下架(reported) 的不能自己重新上架（后端也拦，返回 403）
					canPublish: tab === 'created' && flagKey === 'draft'
				}
			},

			// 后端三个布尔 → 标签 key（没有布尔字段的老接口回退到 status）
			statusKeyOf(raw) {
				if ('is_listed' in raw || 'is_reported' in raw || 'is_verified' in raw) {
					if (raw.is_reported) return 'reported'
					if (raw.is_verified) return 'verified'
					if (raw.is_listed) return 'published'
					return 'draft'
				}
				return raw.status || 'draft'
			},

			metaOf(tab, raw) {
				const parts = []
				if (tab === 'created' && raw.is_fork) parts.push('Fork')
				parts.push(raw.step_count + ' 步')
				parts.push(raw.rating_count > 0 ? '★ ' + Number(raw.avg_rating).toFixed(1) + '（' + raw.rating_count + '）' : '暂无评分')
				parts.push(raw.usage_count + ' 人用过')
				return parts.join(' · ')
			},

			formatTime(iso) {
				if (!iso) return ''
				const d = new Date(iso)
				if (isNaN(d.getTime())) return ''
				const p = (n) => (n < 10 ? '0' + n : '' + n)
				return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
			},

			switchTab(key) {
				if (this.tab === key) return
				this.tab = key
				this.list = []
				this.fetchList()
			},

			onLogin() {
				// #ifdef H5
				// 网页版：去登录/注册页；登录完返回本页，onShow 会自动重拉
				uni.navigateTo({ url: '/pages/login/login' })
				// #endif
				// #ifndef H5
				// 小程序：强制换一个 token 再静默登录（本地这个可能已被服务端判定失效，401 时 request.js 会清）
				clearToken()
				this.fetchList()
				// #endif
			},

			onLogout() {
				clearToken()
				this.list = []
				this.email = ''
				this.needLogin = true
				uni.showToast({ title: '退出了', icon: 'none' })
			},

			onRefresh() {
				if (this.loading) {
					this.refreshing = false
					return
				}
				this.refreshing = true
				this.fetchList()
			},

			goDetail(id) {
				if (!id) return
				uni.navigateTo({ url: '/pages/detail/detail?id=' + id })
			},

			// ===== 我创建的：创建 / 编辑 / 发布 / 删除 =====
			goCreate() {
				uni.navigateTo({ url: '/pages/create/create' })
			},

			// #079：我的任务（日常任务页）
			goTasks() {
				uni.navigateTo({ url: '/pages/tasks/tasks' })
			},

			goEdit(id) {
				if (!id) return
				uni.navigateTo({ url: '/pages/create/create?id=' + id })
			},

			onPublish(item) {
				if (!item || !item.patternId) return
				uni.showModal({
					title: '发布模板',
					content: '发布后所有人都能搜到「' + item.title + '」，确定发布？',
					success: (res) => {
						if (!res.confirm) return
						ensureLogin()
							.then(() => post('/quick/' + item.patternId + '/publish/', {}, { silent: true }))
							.then(() => {
								uni.showToast({ title: '发出去了', icon: 'none' })
								this.fetchList()
							})
							.catch((e) => uni.showToast({ title: (e && e.data && e.data.error) || '没发出去，再试一次', icon: 'none' }))
					}
				})
			},

			onDelete(item) {
				if (!item || !item.patternId) return
				uni.showModal({
					title: '删除模板',
					content: '删除后不可恢复（步骤、笔记、收藏关联都会一起删），确定删除「' + item.title + '」？',
					confirmText: '删除',
					confirmColor: '#c0392b',
					success: (res) => {
						if (!res.confirm) return
						ensureLogin()
							.then(() => request('/quick/' + item.patternId + '/delete/', 'DELETE', {}, { silent: true }))
							.then(() => {
								uni.showToast({ title: '删掉了', icon: 'none' })
								this.fetchList()
							})
							.catch((e) => uni.showToast({ title: (e && e.data && e.data.error) || '没删掉，再试一次', icon: 'none' }))
					}
				})
			},

			// 备案号只能复制、不能跳转（小程序除 web-view 外禁外链），复制后顺带告诉用户去哪查
			copyBeian() {
				uni.setClipboardData({
					data: this.beian,
					success: () => {
						// 微信自带的"内容已复制"提示会被这句顶掉，所以文案里带上查询入口
						uni.showToast({ title: '备案号已复制，可到 beian.miit.gov.cn 查询', icon: 'none' })
					},
					fail: () => uni.showToast({ title: '没复制上，长按选择复制', icon: 'none' })
				})
			},

			goBack() {
				// #058③：与详情/创建页同一套判断（页面栈 → 浏览器历史 → 首页兜底）
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
				uni.reLaunch({ url: '/pages/index/index' })
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

	/* ===== 三个分区 ===== */
	.tabs {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		background-color: var(--card);
		border-bottom: 2rpx solid var(--border);
	}

	.tab {
		flex: 1;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-bottom: 4rpx solid transparent;
	}

	.tab-on {
		border-bottom-color: var(--accent);
	}

	.tab-text {
		font-size: 28rpx;
		color: var(--muted);
	}

	.tab-on .tab-text {
		color: var(--accent);
		font-weight: 600;
	}

	.hover-dim {
		opacity: 0.6;
	}

	.body {
		flex: 1;
		height: 0;
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
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
	}

	.card-title-row {
		display: flex;
		align-items: center;
	}

	.card-title-row .card-title {
		flex: 1;
		min-width: 0;
	}

	/* #058⑩：电脑端资料卡。默认 display:none —— 手机端（含手机网页版）布局一个字都不改，
	   只有 ≥768px 才出现，把"我的"页从"三个 tab + 列表"补成有账号/计数/入口/说明的一页。 */
	.mine-profile {
		display: none;
	}
	@media (min-width: 768px) {
		.mine-profile {
			display: block;
			margin-bottom: 16px;
			padding: 20px 22px;
			border: 1px solid var(--border);
			border-radius: var(--r-card);
			background-color: var(--card);
		}
		.mp-head {
			display: flex;
			align-items: center;
		}
		.mp-avatar {
			flex-shrink: 0;
			width: 48px;
			height: 48px;
			border-radius: 50%;
			background-color: var(--accent-soft);
			display: flex;
			align-items: center;
			justify-content: center;
		}
		.mp-avatar-text {
			font-size: 20px;
			font-weight: 700;
			color: var(--accent);
		}
		.mp-id {
			flex: 1;
			min-width: 0;
			margin-left: 14px;
			display: flex;
			flex-direction: column;
		}
		.mp-name {
			font-size: 16px;
			font-weight: 600;
			color: var(--text);
			overflow: hidden;
			white-space: nowrap;
			text-overflow: ellipsis;
		}
		.mp-sub {
			margin-top: 4px;
			font-size: 12px;
			color: var(--muted);
		}
		.mp-act {
			flex-shrink: 0;
			min-height: 36px;
			padding: 0 14px;
			display: flex;
			align-items: center;
			font-size: 13px;
		}
		.mp-stats {
			display: flex;
			margin-top: 18px;
			padding-top: 16px;
			border-top: 1px solid var(--border);
		}
		.mp-stat {
			flex: 1;
			display: flex;
			flex-direction: column;
			align-items: center;
			cursor: pointer;
		}
		.mp-num {
			font-size: 22px;
			font-weight: 700;
			color: var(--text);
		}
		.mp-label {
			margin-top: 4px;
			font-size: 12px;
			color: var(--muted);
		}
		.mp-actions {
			display: flex;
			gap: 10px;
			margin-top: 16px;
		}
		.mp-btn {
			flex: 1;
			min-height: 40px;
			display: flex;
			align-items: center;
			justify-content: center;
			font-size: 14px;
			cursor: pointer;
		}
		.mp-how {
			margin-top: 16px;
			padding: 12px 14px;
			border-radius: var(--r-btn);
			background-color: var(--surface-2);
			display: flex;
			flex-direction: column;
		}
		.mp-how-title {
			font-size: 13px;
			font-weight: 600;
			color: var(--text);
		}
		.mp-how-text {
			margin-top: 6px;
			font-size: 12px;
			line-height: 1.7;
			color: var(--text-2);
		}
	}

	/* #058⑩：资料卡（规则见文件末尾的桌面覆盖） */

	/* 状态标签：草稿 / 已发布 / 社区推荐 */
	.status {
		flex-shrink: 0;
		margin-left: 12rpx;
		padding: 4rpx 16rpx;
		border-radius: 999rpx;
		font-size: 20rpx;
		background-color: rgba(0, 0, 0, 0.05);
		color: var(--muted);
	}

	.status-draft {
		background-color: rgba(0, 0, 0, 0.05);
		color: var(--muted);
	}

	.status-published {
		background-color: var(--accent-soft);
		color: var(--accent);
	}

	.status-verified {
		background-color: rgba(46, 139, 87, 0.12);
		color: #2e8b57;
	}

	/* #057⑩：被举报/被下架（待复核）—— 用暖红提示，和"草稿"灰、"已发布"主题色区分开 */
	.status-reported {
		background-color: rgba(186, 33, 33, 0.12);
		color: #ba2121;
	}

	/* ===== 我创建的：创建入口 + 管理操作 ===== */
	.create-row {
		margin-bottom: 20rpx;
	}

	.create-btn {
		height: 88rpx;
		border-radius: 24rpx;
		border: 2rpx dashed var(--accent);
		background-color: var(--accent-soft);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.create-text {
		font-size: 28rpx;
		font-weight: 600;
		color: var(--accent);
	}

	.ops {
		display: flex;
		align-items: center;
		margin-top: 20rpx;
	}

	.op {
		height: 64rpx;
		padding: 0 28rpx;
		margin-right: 16rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		font-size: 24rpx;
		color: var(--text);
	}

	.op-main {
		border-color: var(--accent);
		background-color: var(--accent-soft);
		color: var(--accent);
		font-weight: 600;
	}

	.op-del {
		margin-right: 0;
		margin-left: auto;
		border-color: rgba(192, 57, 43, 0.3);
		color: #c0392b;
	}

	.card-sub {
		display: block;
		margin-top: 8rpx;
		font-size: 26rpx;
		color: var(--muted);
	}

	/* 笔记正文：可能多行，给足行高 */
	.card-body {
		display: block;
		margin-top: 8rpx;
		font-size: 27rpx;
		line-height: 1.6;
		color: var(--text);
	}

	.card-meta {
		display: block;
		margin-top: 12rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	/* ===== 状态 ===== */
	.state {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 120rpx 64rpx;
	}

	/* #073：空态标记改成"圆底 + 线条图标"（原来是 emoji） */
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
		margin-top: 40rpx;
		padding: 0 64rpx;
	}

	/* ===== 备案号 ===== */
	.beian {
		display: flex;
		align-items: center;
		justify-content: center;
		/* 字只有 22rpx，靠上下内边距把点击区域撑到约 55px，既满足触控目标 ≥ 44px 又保持视觉低调 */
		padding: 32rpx 48rpx 48rpx;
	}

	.beian-text {
		font-size: 22rpx;
		color: var(--muted);
	}

	.safe-bottom {
		height: calc(32rpx + constant(safe-area-inset-bottom));
		height: calc(32rpx + env(safe-area-inset-bottom));
	}
	/* ===== 网页版（H5）：卡片与列表对齐同一套规范（设计规范 §4.1） ===== */
	/* #ifdef H5 */
	.list {
		padding: 20px 0 8px;
	}
	.card {
		margin-bottom: 12px;
		padding: 20px;
	}
	.card-title {
		font-size: 16px;
	}
	.card-body,
	.card-sub {
		font-size: 13px;
	}
	.card-meta {
		font-size: 12px;
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
	/* ===== #035：tab 栏跟导航拼成"一张卡片"（③ 方案 A 合并） =====
	   手机：导航浮卡只留上圆角、tab 容器接下圆角，两段拼成一个圆角容器——
	   原来"上面圆角卡片、下面直角通栏"就是 Jeff 说的风格割裂。
	   电脑：导航是通栏（规范 §4.4），没法跟内容列的 tab 合并，所以分开但共用同一套圆角与选中态（方案 B）。
	   选中态由"下划线"改成标志色淡底胶囊：圆角容器里画一条直线会被圆角切掉，
	   而胶囊正好对上规范 §4.2「激活态 = --accent-soft 底 + --accent 字」。 */
	.tabs {
		box-sizing: border-box;
		padding: 6px;
		border: 1px solid var(--border);
		/* #038③：tab 容器也做成两头全圆的胶囊（灵动岛式），跟导航卡片同一套语言 */
		border-radius: 999px;
		background-color: var(--card);
	}
	.tab {
		height: 44px; /* 触控目标 ≥ 44px（AGENTS.md） */
		margin-right: 4px;
		border-bottom: none; /* 去掉基类的下划线，改胶囊 */
		border-radius: 999px; /* #038③：选中态也是两头全圆 */
	}
	.tab:last-child {
		margin-right: 0;
	}
	.tab-on {
		background-color: var(--accent-soft);
	}
	.tab-text {
		font-size: 14px;
	}
	.tab-on .tab-text {
		color: var(--accent);
	}
	@media (max-width: 767px) {
		/* #036①：两个独立胶囊，中间 8px 间距。
		   #038③ 起圆角统一由 App.vue 的 999px 全圆给（导航卡片和 tab 容器都一样）。 */
		.tabs {
			margin: 8px var(--content-pad) 0;
		}
	}
	@media (min-width: 768px) {
		/* 电脑端：胶囊组贴着内容列左缘，宽度收紧到内容本身，不拉成一条空通栏 */
		.tabs {
			width: fit-content;
			margin: 12px 0 0 max(var(--content-pad), calc((100% - var(--content-w)) / 2 + var(--content-pad)));
		}
		.tab {
			flex: 0 0 auto;
			min-width: 120px;
			padding: 0 20px;
		}
	}
	.beian {
		padding: 20px 0 28px;
	}
	/* 登录后的账号行：邮箱 + 退出登录 */
	.account-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 0 4px;
	}
	.account-email {
		font-size: 13px;
		color: var(--text-2);
	}
	.account-out {
		font-size: 13px;
		color: var(--accent);
		cursor: pointer;
	}
	/* #040：重看新手引导的入口（卡片式一行，触控目标 ≥ 44px） */
	.tutorial-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-height: 48px;
		margin-top: 12px;
		padding: 0 16px;
		border: 1px solid var(--border);
		border-radius: var(--r-card);
		background-color: var(--card);
	}
	.tutorial-text {
		font-size: 14px;
		color: var(--text-2);
	}
	.tutorial-arrow {
		font-size: 18px;
		color: var(--muted);
	}
	/* #endif */

	/* ===== 「我创建的」按规范（#029 §4.3） ===== */
	/* #ifdef H5 */
	/* 状态标签：草稿 = 次级面；已发布 / 社区推荐 = 标志色淡底 */
	.status,
	.status-draft {
		background-color: var(--surface-2);
		color: var(--text-2);
	}
	.status-published,
	.status-verified {
		background-color: var(--accent-soft);
		color: var(--accent);
	}
	/* #057⑩：待复核（被举报/被下架）用危险色淡底，和上面两类区分 */
	.status-reported {
		background-color: rgba(186, 33, 33, 0.12);
		color: #ba2121;
	}
	/* 管理操作走次按钮；删除用危险色 */
	.op {
		height: 32px;
		border: 1px solid var(--border);
		border-radius: var(--r-btn);
		background-color: transparent;
		color: var(--text);
	}
	.op-main {
		border-color: var(--accent);
		background-color: var(--accent-soft);
		color: var(--accent);
	}
	.op-del {
		border-color: var(--danger);
		color: var(--danger);
	}
	/* 创建入口：虚线框 + 标志色 */
	.create-btn {
		border: 1px dashed var(--accent);
		background-color: var(--accent-soft);
		border-radius: var(--r-card);
	}
	/* #035 ④：卡片里的图标块原来 24rpx（手机上≈16px），比卡片圆角还大，一起收小 */
	.card-icon {
		border-radius: var(--r-btn);
	}
	/* #endif */
	/* #058⑩：电脑端资料卡里已经有"账号 / 退出登录 / 再看教程"，
	   桌面上就不再重复显示老的那两行（规则放文件末尾，否则被下面 H5 块里的
	   .tutorial-row / .account-row 同优先级覆盖）。手机端（<768px）不变。 */
	/* #071：资料区（资料卡）已经包含账号 / 退出 / 再看教程，旧的这两行全端都隐藏，别重复 */
	.account-row,
	.tutorial-row {
		display: none !important;
	}

	/* ===== #071：资料区（手机端也显示）/ 草稿 chips / 编辑资料弹层 =====
	   ⚠️ #058 那套 .mp-* 样式整块写在 @media (min-width:768px) 里，
	   所以资料区一旦在手机端显示、内部布局就是"没样式的裸元素"（实测塌成一行行文字）。
	   这里用【移动优先】重写一遍完整布局；本块在文件末尾，同优先级下压过 #058 那份。 */
	.mine-profile {
		display: block;
		box-sizing: border-box;
		max-width: 100%;
		overflow: hidden;
		margin-bottom: 14px;
		padding: 16px;
		border: 1px solid var(--border);
		border-radius: var(--r-card);
		background-color: var(--card);
	}
	.mp-head {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
	}
	.mp-avatar {
		flex-shrink: 0;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background-color: var(--accent-soft);
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.mp-avatar-text {
		font-size: 18px;
		font-weight: 700;
		color: var(--accent);
	}
	.mp-avatar-img {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		flex-shrink: 0;
		background-color: var(--surface-2);
	}	.mp-id {
		flex: 1;
		min-width: 0;
		margin-left: 12px;
		display: flex;
		flex-direction: column;
	}
	.mp-name {
		font-size: 16px;
		font-weight: 600;
		color: var(--text);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}
	.mp-sub {
		margin-top: 4px;
		font-size: 12px;
		line-height: 1.4;
		color: var(--muted);
		/* uni 的 <text> 在 H5 是 inline，长句子不会自己换行 → 会把卡片顶宽（实测溢出屏幕） */
		display: block;
		white-space: normal;
		word-break: break-all;
	}
	.mp-act {
		flex-shrink: 0;
		min-height: 36px;
		padding: 0 12px;
		display: flex;
		align-items: center;
		font-size: 13px;
		margin-left: 8px;
	}
	.mp-stats {
		display: flex;
		margin-top: 14px;
		padding-top: 14px;
		border-top: 1px solid var(--border);
	}
	.mp-stat {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	.mp-num {
		font-size: 20px;
		font-weight: 700;
		color: var(--text);
	}
	.mp-label {
		margin-top: 2px;
		font-size: 12px;
		color: var(--muted);
	}
	.mp-actions {
		display: flex;
		gap: 10px;
		margin-top: 14px;
	}
	.mp-btn {
		flex: 1;
		min-height: 40px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 14px;
	}
	/* #079：我的任务入口 —— 一行、带图标 + 箭头，比照"设置项"的样子 */
	.mp-task {
		display: flex;
		align-items: center;
		box-sizing: border-box;
		min-height: 44px;
		margin-top: 12px;
		padding: 0 12px;
		border-radius: var(--r-btn);
		border: 1px solid var(--border);
		background-color: var(--surface-2);
	}
	.mp-task-text {
		margin-left: 8px;
		font-size: 14px;
		color: var(--text);
	}
	.mp-task-sub {
		flex: 1;
		margin-left: 8px;
		font-size: 12px;
		color: var(--muted);
		text-align: right;
	}
	.mp-task-arrow {
		margin-left: 6px;
		font-size: 16px;
		color: var(--muted);
		line-height: 1;
	}
	.mp-how {
		margin-top: 14px;
		padding: 12px 14px;
		border-radius: var(--r-btn);
		background-color: var(--surface-2);
		display: flex;
		flex-direction: column;
	}
	.mp-how-title {
		font-size: 13px;
		font-weight: 600;
		color: var(--text);
	}
	.mp-how-text {
		margin-top: 6px;
		font-size: 12px;
		line-height: 1.7;
		color: var(--text-2);
	}
	@media (max-width: 480px) {
		.mp-id {
			flex: 1 1 auto;
		}
		.mp-act {
			flex: 1 1 40%;
			justify-content: center;
			margin: 10px 0 0;
		}
	}
	/* #071：tab 从 3 个变 4 个（多了「浏览记录」），窄屏上要能挤下 */
	.tabs {
		display: flex;
	}
	.tab {
		flex: 1;
		min-width: 0;
		padding: 0 6px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.tab-text {
		font-size: 13px;
		white-space: nowrap;
	}
	.mp-act-plain {
		border-color: transparent;
		background-color: transparent;
		color: var(--muted);
	}
	/* #071：手机端也显示资料区（#058 时只在 ≥768px 显示），所以这里压过上面的 display:none */
	.mine-profile {
		display: block;
		margin-bottom: 14px;
		padding: 16px;
	}
	.draft-chips {
		display: flex;
		gap: 8px;
		margin-bottom: 14px;
	}
	.draft-chip {
		padding: 6px 14px;
		border-radius: 999px;
		border: 1px solid var(--border);
		color: var(--text-2);
		font-size: 12px;
	}
	.draft-chip-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
		color: var(--accent);
		font-weight: 600;
	}
	.draft-empty {
		padding: 24px 0;
		text-align: center;
		color: var(--muted);
		font-size: 13px;
	}
	.mask {
		position: fixed;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		z-index: 40;
		background-color: rgba(0, 0, 0, 0.55);
		display: flex;
		align-items: flex-end;
	}
	.sheet {
		width: 100%;
		box-sizing: border-box;
		padding: 20px;
		border-radius: 20px 20px 0 0;
		background-color: var(--card);
	}
	.sheet-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 16px;
	}
	.sheet-title {
		font-size: 16px;
		font-weight: 600;
		color: var(--text);
	}
	.sheet-close {
		padding: 0 8px;
		color: var(--muted);
	}
	.pf-row {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 16px;
	}
	.pf-avatar {
		width: 56px;
		height: 56px;
		border-radius: 50%;
	}
	.pf-avatar-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		background-color: var(--accent-soft);
		color: var(--accent);
		font-size: 20px;
		font-weight: 700;
	}
	.pf-btn {
		padding: 0 16px;
		min-height: 40px;
		display: flex;
		align-items: center;
	}
	.pf-field {
		display: flex;
		flex-direction: column;
	}
	.pf-label {
		font-size: 12px;
		color: var(--muted);
		margin-bottom: 6px;
	}
	.pf-input {
		height: 44px;
		padding: 0 12px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background-color: var(--surface-2);
		color: var(--text);
		font-size: 15px;
	}
	.pf-hint {
		display: block;
		margin-top: 8px;
		font-size: 11px;
		line-height: 1.6;
		color: var(--muted);
	}
	.pf-actions {
		display: flex;
		gap: 10px;
		margin-top: 18px;
	}
	.pf-act {
		flex: 1;
	}
	@media (min-width: 768px) {
		.mp-avatar,
		.mp-avatar-img {
			width: 48px;
			height: 48px;
		}
		.mp-name {
			font-size: 17px;
		}
		.mp-num {
			font-size: 22px;
		}
		.tab-text {
			font-size: 14px;
		}
		.mask {
			align-items: center;
		}
		.sheet {
			max-width: 480px;
			margin: 0 auto;
			border-radius: 12px;
		}
		.mine-profile {
			padding: 20px 22px;
			margin-bottom: 16px;
		}
	}
</style>
