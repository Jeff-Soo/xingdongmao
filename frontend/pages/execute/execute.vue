<template>
	<view class="page">
		<!-- 顶栏：右上角退出引导胶囊（D6）+ 进度 -->
		<view class="topbar" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="topbar-inner" :style="nav.navInnerStyle">
				<view class="topbar-left">
					<!-- 第一步时它退化成"返回详情页"，所以永远可点、不再置灰 -->
					<view class="step-back" hover-class="hover-dim" @click="goPrev">
						<text class="step-back-icon">‹</text>
					</view>
					<text class="progress">{{ progressText }}</text>
				</view>
				<view class="exit" hover-class="hover-dim" @click="onExit">
					<view class="exit-pill" :style="pillStyle">
						<app-icon class="exit-ico" name="x" :size="15" tone="muted" />
						<text class="exit-label">退出引导</text>
					</view>
				</view>
			</view>
		</view>

		<view v-if="loading" class="state">
			<view class="state-mark"><app-icon name="circle-notch" :size="28" tone="muted" /></view>
			<text class="state-title">加载中…</text>
		</view>

		<view v-else-if="!steps.length" class="state">
			<!-- #057⑭：模板真的 0 步（加载成功）时 errorMsg 是空的，页面只剩一个空白错误态；
			     这里把"空模板"和"加载失败"分开说，别让用户以为是自己网络的问题 -->
			<view class="state-mark"><app-icon :name="errorMsg ? 'cloud-slash' : 'file-dashed'" :size="28" tone="muted" /></view>
			<text class="state-title">{{ errorMsg ? '没能打开这个模板' : '这个模板还没有步骤' }}</text>
			<text class="state-desc">{{ errorMsg || '作者还没填内容，换一个模板试试' }}</text>
			<view class="state-btn btn-accent" @click="fetchSteps"><text>重试</text></view>
			<view class="state-btn btn-ghost" @click="onExit"><text>退出</text></view>
		</view>

		<view v-else class="roller">
			<!-- 滚轴：竖向 swiper，当前卡居中放大，上下邻居缩小半透明 -->
			<swiper
				class="swiper"
				:vertical="true"
				:current="current"
				:duration="260"
				:previous-margin="edgeMargin"
				:next-margin="edgeMargin"
				@change="onSwiperChange"
			>
				<swiper-item v-for="(s, i) in steps" :key="'step-' + i">
					<view class="slot">
						<view class="card" :class="{ 'card-current': i === current }">
							<view class="card-top">
								<text class="card-order">{{ i + 1 }}</text>
								<text v-if="s.title && s.instruction" class="card-title">{{ s.title }}</text>
							</view>

							<view class="card-body">
								<text class="card-instruction">{{ s.instruction || s.title }}</text>
							</view>

							<!-- 计时器：只有带等待时长的步骤才出现，只有当前卡可操作（D3/D4/D5） -->
							<view v-if="s.duration_seconds > 0 && i === current" class="timer">
								<text class="timer-clock">{{ clockText }}</text>
								<view
									class="timer-btn"
									:class="timerState === 'running' ? 'timer-btn-stop' : 'timer-btn-go'"
									hover-class="hover-dim"
									@click="toggleTimer"
								>
									<text>{{ timerBtnText }}</text>
								</view>
							</view>
							<view v-else-if="s.duration_seconds > 0" class="timer">
								<text class="timer-idle">⏱ {{ formatClock(s.duration_seconds) }}</text>
							</view>

							<!-- 可展开解释：默认收起，没有 explain 就不出现这个入口（D7） -->
							<view v-if="s.explain" class="explain">
								<view class="explain-head" hover-class="hover-dim" @click="toggleExplain(i)">
									<text class="explain-arrow">{{ expandedIndex === i ? '▾' : '▸' }}</text>
									<text class="explain-label">为什么这么做</text>
								</view>
								<!-- #058④⑤：整条都可点由 CSS 保证（占满卡片宽度 + 44px 高），
								     不在这里多加一行文字，免得把卡片挤乱 -->
								<scroll-view v-if="expandedIndex === i" class="explain-body" scroll-y>
									<text class="explain-text">{{ s.explain }}</text>
								</scroll-view>
							</view>
						</view>
					</view>
				</swiper-item>

				<!-- 最后一张：完成卡——反思笔记 / 评分 / 收藏（一路滑到底就是完成） -->
				<swiper-item key="done">
					<view class="slot">
						<view class="card card-done" :class="{ 'card-current': finished }">
							<!-- 小屏上内容可能比卡片高，整体可滚，保证"完成，返回"永远够得着 -->
							<scroll-view class="done-scroll" scroll-y>
								<view class="done-head">
									<view class="done-head-row">
										<app-icon name="check-circle" :size="22" tone="accent" />
										<text class="done-title">已完成</text>
									</view>
									<text v-if="title" class="done-sub">{{ title }}</text>
								</view>

								<!-- 反思笔记：闭环里最关键的一步，放在评分前面（先写再评价更自然）
								     要登录，网页版第一版先隐藏（canLogin=false，小程序端不变） -->
								<view v-if="canLogin" class="done-block">
									<text class="done-label">以后我会怎么做</text>
									<!-- textarea 是原生组件，不跟父级透明度/缩放走，所以只在当前卡渲染，避免在邻居卡上"透"出来 -->
									<textarea
										v-if="finished"
										class="done-input"
										v-model="noteText"
										:maxlength="500"
										placeholder="写一句下次能照着做的"
										placeholder-class="done-ph"
									/>
									<view class="done-row">
										<view
											class="done-mini"
											:class="{ 'done-mini-off': !noteText.trim() || noteSaving }"
											hover-class="hover-dim"
											@click="onSubmitNote"
										>
											<text>{{ noteSaving ? '保存中…' : '记下来' }}</text>
										</view>
										<text v-if="noteTip" class="done-tip">{{ noteTip }}</text>
									</view>
								</view>

								<!-- 评分：1/3/5 星给文字锚定，2/4 星留空（后端只存 1-5）；要登录，网页版隐藏 -->
								<view v-if="canLogin" class="done-block">
									<text class="done-label">{{ myRating ? '你已评 ' + myRating + ' 星' : '这个模板有用吗' }}</text>
									<view class="stars">
										<view v-for="n in 5" :key="n" class="star" hover-class="hover-dim" @click="onRate(n)">
											<app-icon name="star" :size="22" :tone="n <= myRating ? 'accent' : 'muted'" />
											<text class="star-hint">{{ starHints[n] || '' }}</text>
										</view>
									</view>
									<text v-if="ratingTip" class="done-tip done-tip-block">{{ ratingTip }}</text>
								</view>

								<!-- 收藏 + 分享：做完一件事的时候分享意愿最高（收藏要登录，网页版只留分享） -->
								<view class="done-block">
									<view class="done-row">
										<view v-if="canLogin" class="done-mini done-mini-wide" hover-class="hover-dim" @click="onToggleFavorite">
											<app-icon class="done-mini-ico" :name="favorited ? 'star' : 'star-half'" :size="15" :tone="favorited ? 'accent' : 'muted'" />
											<text>{{ favorited ? '已收藏' : '收藏' }}</text>
										</view>
										<view class="done-mini done-mini-wide" hover-class="hover-dim" @click="openShare">
											<app-icon class="done-mini-ico" name="export" :size="15" tone="muted" />
											<text>分享</text>
										</view>
									</view>
								</view>

								<!-- 完成后的明确出口，否则用户卡在完成页 -->
								<view class="done-exit btn-accent" hover-class="hover-dim" @click="onExit">
									<text>完成，返回</text>
								</view>
							</scroll-view>
						</view>
					</view>
				</swiper-item>
			</swiper>

			<!-- 首次提示；最后一步再提示一次，否则用户不知道"上滑 = 完成" -->
			<view class="hintbar">
				<text v-if="showHint" class="hint-text">{{ hintText }}</text>
			</view>

			<!-- #058④⑧：电脑端底部操作条 —— 宽屏上"上滑"这个手势没有对应操作，
			     给一对明确的按钮（整条 44px+ 可点），滚轮也能切。手机端整条隐藏。 -->
			<view v-if="isWide && steps.length && !finished" class="step-nav">
				<view class="step-nav-btn" :class="{ 'step-nav-off': current <= 0 }" hover-class="hover-dim" @click="goPrev">
					<text>‹ 上一步</text>
				</view>
				<text class="step-nav-mid">{{ current + 1 }} / {{ steps.length }}</text>
				<view class="step-nav-btn step-nav-main" hover-class="hover-dim" @click="goNext">
					<text>{{ isLastStep ? '完成 ›' : '下一步 ›' }}</text>
				</view>
			</view>
		</view>

		<share-sheet :visible="shareVisible" :pattern-id="id" @close="shareVisible = false" />
	</view>
</template>

<script>
	import { get, post } from '@/api/request.js'
	import { ensureLogin } from '@/utils/token.js'
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { toStepList, SOURCE_QUICK } from '@/utils/adapter.js'
	import { CAN_LOGIN } from '@/utils/config.js'
	import ShareSheet from '@/components/share-sheet/share-sheet.vue'
	// #073：结构图标统一走 app-icon（矢量，替代 emoji）
	import AppIcon from '@/components/app-icon/app-icon.vue'

	export default {
		components: { ShareSheet, AppIcon },
		data() {
			return {
				statusBarHeight: 20,
				// 导航栏尺寸（对齐微信胶囊），onLoad 里用 getNavBarMetrics() 填
				nav: {},
				// 网页版第一版不做登录：笔记/评分/收藏先隐藏（utils/config.js）
				canLogin: CAN_LOGIN,
				edgeMargin: '140rpx',
				id: '',
				title: '',
				tagline: '',
				steps: [],
				loading: false,
				errorMsg: '',
				current: 0,
				expandedIndex: -1,
				// idle：未开始（默认暂停）｜running：倒计时中｜paused：暂停后待继续
				timerState: 'idle',
				remaining: 0,
				endAt: 0,
				timerId: null,
				advanceId: null,
				hintDismissed: false,
				// #058⑧：宽屏（≥768px）才显示底部"上一步/下一步"操作条；滚轮同理
				wideScreen: false,
				// 滚轮节流时间戳：一次滑动会连发好几个 wheel，不加锁会连跳好几步
				wheelLockAt: 0,
				// 完成卡闭环：笔记 / 评分 / 收藏
				noteText: '',
				noteSaving: false,
				noteTip: '',
				myRating: 0,
				ratingTip: '',
				ratingSubmitting: false,
				favorited: false,
				favSubmitting: false,
				shareVisible: false,
				// 完成卡的写操作都依赖"已登录 + 已上报执行"，共用一个 promise（见 withUsage）
				afterDone: null,
				// 1/3/5 星文字锚定，Jeff 定的展示规则，2/4 星留空
				starHints: { 1: '没用', 3: '有用', 5: '好用' }
			}
		},
		computed: {
			// 滚到最后一张（完成卡）算走完
			finished() {
				return this.steps.length > 0 && this.current >= this.steps.length
			},
			clockText() {
				return this.formatClock(this.remaining)
			},
			timerBtnText() {
				if (this.timerState === 'running') return '暂停'
				return this.timerState === 'paused' ? '继续' : '开始'
			},
			progressText() {
				if (!this.steps.length) return '0 / 0'
				return Math.min(this.current + 1, this.steps.length) + ' / ' + this.steps.length
			},
			isLastStep() {
				return this.steps.length > 0 && this.current === this.steps.length - 1
			},
			showHint() {
				if (!this.steps.length || this.finished) return false
				// 首次提示；另外最后一步再提示一次，否则用户不知道"上滑 = 完成"
				return !this.hintDismissed || this.isLastStep
			},
			hintText() {
				// #058⑧：电脑端没有"上滑"这个动作，提示改成滚轮/鼠标
				// （isWide 只在 H5 的 mounted 里可能为 true，小程序端恒为 false）
				if (this.isWide) {
					return this.isLastStep && this.hintDismissed ? '滚轮 / 下一步 完成' : '滚轮 / 下一步 继续'
				}
				return this.isLastStep && this.hintDismissed ? '↑ 上滑完成' : '↑ 上滑继续'
			},
			// 桌面宽度（≥768px）：底部操作条与滚轮提示只在这时出现
			isWide() {
				return this.wideScreen
			},
			// 让"退出引导"胶囊和微信胶囊等高，不只是中心线对齐，上下边也齐
			pillStyle() {
				return this.nav && this.nav.capsuleHeight ? { height: this.nav.capsuleHeight + 'px' } : {}
			}
		},
		onLoad(options) {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight)
			// swiper 的前/后边距走 px：rpx 虽然多数端认，但 px 最稳
			this.edgeMargin = typeof uni.upx2px === 'function' ? uni.upx2px(140) + 'px' : '140rpx'
			this.id = (options && options.id) || ''
			if (this.id) {
				this.fetchSteps()
			} else {
				this.errorMsg = '缺少模板 id'
			}
		},
		// 转发卡片：好友点开直达这个模板详情
		onShareAppMessage() {
			const title = this.title ? this.title + (this.tagline ? ' · ' + this.tagline : '') : '行动锚 · 现在就能做的一件小事'
			return {
				title: title,
				path: '/pages/detail/detail?id=' + this.id
			}
		},
		onHide() {
			// 退到后台 / 被别的页面盖住：停掉计时，回来时回到暂停态，不在后台偷跑
			this.resetTimer()
		},
		onUnload() {
			this.clearTimer()
		},
		// #058⑮：beforeDestroy 是 Vue 2 的钩子（项目是 vueVersion:"3"），写在这里是死代码 ——
		// 页面销毁时定时器不会被清、滚轮/resize 监听也摘不掉。换成 Vue 3 的 beforeUnmount。
		beforeUnmount() {
			this.clearTimer()
			// #ifdef H5
			if (this.onWheelStep_) window.removeEventListener('wheel', this.onWheelStep_)
			if (this.onResize_) window.removeEventListener('resize', this.onResize_)
			// #endif
		},
		// #058⑧：电脑端滚轮切步骤 + 记录屏幕宽度（底部操作条只在宽屏出现）
		mounted() {
			// #ifdef H5
			this.onResize_ = () => this.syncWide()
			this.onWheelStep_ = (e) => this.handleWheel(e)
			window.addEventListener('resize', this.onResize_)
			// passive: false —— 滚轮切步骤时要 preventDefault，否则卡片会跟着一起滚
			window.addEventListener('wheel', this.onWheelStep_, { passive: false })
			this.syncWide()
			// #endif
		},
		methods: {
			formatClock(seconds) {
				const total = Math.max(0, Math.round(Number(seconds) || 0))
				const m = Math.floor(total / 60)
				const s = total % 60
				return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s
			},

			async fetchSteps() {
				if (!this.id || this.loading) return
				this.loading = true
				this.errorMsg = ''
				try {
					const data = await get('/quick/' + this.id + '/', null, { silent: true })
					this.title = (data && data.title) || ''
					this.tagline = (data && data.tagline) || ''
					this.steps = toStepList((data && data.steps) || [], SOURCE_QUICK)
					this.applyStep(0)
				} catch (e) {
					this.steps = []
					this.errorMsg = (e && e.data && e.data.error) || '请求失败，检查后端是否启动'
				} finally {
					this.loading = false
				}
			},

			durationOf(index) {
				const s = this.steps[index]
				return s ? Number(s.duration_seconds) || 0 : 0
			},

			// 换卡统一动作（D4）：关掉旧计时、新卡回到原始时长的暂停态、收起解释
			applyStep(index) {
				this.clearTimer()
				this.current = index
				this.timerState = 'idle'
				this.remaining = this.durationOf(index)
				this.expandedIndex = -1
			},

			goTo(index, fromUser = true) {
				if (!this.steps.length) return
				if (index < 0 || index > this.steps.length) return
				if (index === this.current) return
				if (fromUser) this.buzz(false) // 3.3：切换时轻震动
				this.hintDismissed = true
				this.applyStep(index)
				// 到完成卡：静默登录 + 上报执行 + 拉"我的评分/是否已收藏"（失败不打扰，等用户点赞时再提示）
				if (index >= this.steps.length) this.withUsage().catch(() => {})
			},

			// 智能返回：步骤内是"上一步"（滚轴本身也能下滑回退，但那个不容易被发现），
			// 第一步没有上一步，就退化成"返回详情页"，避免按钮变成死按钮
			goPrev() {
				if (this.current <= 0) {
					this.onExit()
					return
				}
				this.goTo(this.current - 1, true)
			},

			// ===== #058⑧ 电脑端：滚轮切步骤 =====
			syncWide() {
				// #ifdef H5
				this.wideScreen = typeof window !== 'undefined' && window.innerWidth >= 768
				// #endif
			},
			handleWheel(e) {
				// #ifdef H5
				if (!this.wideScreen || !this.steps.length || this.finished) return
				// 展开的"为什么这么做"和完成卡里的笔记区自己能滚，别把它抢走
				const t = e.target
				if (t && t.closest && (t.closest('.explain-body') || t.closest('.done-scroll'))) return
				if (Math.abs(e.deltaY) < 2) return
				const now = Date.now()
				if (now - this.wheelLockAt < 420) {
					e.preventDefault()
					return
				}
				this.wheelLockAt = now
				e.preventDefault()
				const next = this.current + (e.deltaY > 0 ? 1 : -1)
				// 下一步到底时也可以去完成卡（swiper 的最后一个 item 就是它）
				if (next < 0 || next > this.steps.length) return
				this.goTo(next, true)
				// #endif
			},
			goNext() {
				// 底部操作条：完成卡是 steps.length（swiper 的最后一项）
				if (this.finished) return
				this.goTo(this.current + 1, true)
			},

			onSwiperChange(e) {
				const next = (e && e.detail && e.detail.current) || 0
				// current 被程序改（计时结束自动滚）时 change 也会来，此时 applyStep 已经跑过
				if (next === this.current) return
				this.goTo(next, true)
			},

			// ===== 计时器 =====
			clearTick() {
				if (this.timerId) {
					clearInterval(this.timerId)
					this.timerId = null
				}
			},
			clearAdvance() {
				if (this.advanceId) {
					clearTimeout(this.advanceId)
					this.advanceId = null
				}
			},
			clearTimer() {
				this.clearTick()
				this.clearAdvance()
			},
			resetTimer() {
				this.clearTimer()
				this.timerState = 'idle'
				this.remaining = this.durationOf(this.current)
			},
			startTimer() {
				const total = this.durationOf(this.current)
				if (total <= 0 || this.timerState === 'running') return
				if (this.remaining <= 0) this.remaining = total
				this.timerState = 'running'
				// 用结束时间戳算剩余，避免 interval 误差累积
				this.endAt = Date.now() + this.remaining * 1000
				this.timerId = setInterval(this.tick, 250)
			},
			tick() {
				const left = Math.max(0, Math.ceil((this.endAt - Date.now()) / 1000))
				if (left !== this.remaining) this.remaining = left
				if (left <= 0) this.onTimerEnd()
			},
			pauseTimer() {
				if (this.timerState !== 'running') return
				this.clearTick()
				this.timerState = 'paused'
			},
			toggleTimer() {
				if (this.timerState === 'running') this.pauseTimer()
				else this.startTimer()
			},
			onTimerEnd() {
				this.clearTick()
				this.remaining = 0
				this.timerState = 'idle'
				this.buzz(true) // D5：提示性振动
				// 让 00:00 停一下再滚，否则用户看不清就到下一步了
				this.advanceId = setTimeout(() => {
					this.advanceId = null
					this.goTo(this.current + 1, false)
				}, 450)
			},
			buzz(long) {
				// 桌面端 / 部分浏览器没有震动能力，失败静默忽略
				try {
					if (long) uni.vibrateLong({ fail() {} })
					else uni.vibrateShort({ fail() {} })
				} catch (e) {
					// 忽略：震动只是锦上添花
				}
			},

			// ===== 交互 =====
			toggleExplain(index) {
				this.expandedIndex = this.expandedIndex === index ? -1 : index
			},
			// ===== 完成卡闭环：笔记 / 评分 / 收藏 =====

			// 完成卡的写操作都要求两个前提：已登录 + 这次执行已上报（/rate/ 会校验"先完成一次引导"）
			withUsage() {
				if (!this.afterDone) {
					this.afterDone = ensureLogin()
						.then(() => post('/quick/' + this.id + '/execute/', {}, { silent: true }))
						.then(() => this.syncMine())
						.catch((err) => {
							// 失败就清空，下次点击能重试（否则会一直复用一个已失败的 promise）
							this.afterDone = null
							throw err
						})
				}
				return this.afterDone
			},

			// 拉"我评过几星 / 是否已收藏"：页面初次加载时多半还没登录，到完成卡再补一次
			syncMine() {
				return ensureLogin()
					.then(() => get('/quick/' + this.id + '/', null, { silent: true }))
					.then((d) => {
						this.myRating = (d && d.my_rating) || 0
						this.favorited = !!(d && d.is_favorited)
						if (d && d.title) this.title = d.title
						if (d && d.tagline) this.tagline = d.tagline
					})
					.catch(() => {})
			},

			onSubmitNote() {
				const content = (this.noteText || '').trim()
				if (!content) {
					uni.showToast({ title: '写一句再记，几个字也行', icon: 'none' })
					return
				}
				if (this.noteSaving) return
				this.noteSaving = true
				this.noteTip = ''
				this.withUsage()
					.then(() => post('/quick/' + this.id + '/note/', { content: content }, { silent: true }))
					.then(() => {
						this.noteText = ''
						this.noteTip = '已记录'
					})
					.catch((e) => {
						if (e && e.needLogin) {
							uni.showToast({ title: '登录一下就好', icon: 'none' })
							return
						}
						uni.showToast({ title: '没存上，再试一次', icon: 'none' })
					})
					.then(() => {
						this.noteSaving = false
					})
			},

			onRate(n) {
				if (this.ratingSubmitting) return
				if (this.myRating) {
					uni.showToast({ title: '这张评过了', icon: 'none' })
					return
				}
				this.ratingSubmitting = true
				this.ratingTip = ''
				this.withUsage()
					.then(() => {
						// 乐观点亮放这里：syncMine 会先跑完，避免它把刚点亮的星又刷回 0
						this.myRating = n
						return post('/quick/' + this.id + '/rate/', { stars: n }, { silent: true })
					})
					.then(() => {
						this.ratingTip = '感谢评分'
					})
					.catch((e) => {
						if (e && e.needLogin) {
							this.myRating = 0
							uni.showToast({ title: '登录一下就好', icon: 'none' })
							return
						}
						const msg = (e && e.data && e.data.error) || ''
						if (msg.indexOf('已评过') >= 0) {
							this.ratingTip = '你已经评过分了'
							this.syncMine() // 把之前那次评分点亮
						} else if (msg.indexOf('先完成') >= 0) {
							this.myRating = 0
							this.ratingTip = '先完整走一遍再评分'
						} else {
							this.myRating = 0
							uni.showToast({ title: '没评上，再试一次', icon: 'none' })
						}
					})
					.then(() => {
						this.ratingSubmitting = false
					})
			},

			onToggleFavorite() {
				if (this.favSubmitting) return
				this.favSubmitting = true
				const next = !this.favorited
				ensureLogin()
					.then(() => post('/quick/' + this.id + '/' + (next ? 'favorite' : 'unfavorite') + '/', {}, { silent: true }))
					.then((d) => {
						this.favorited = !!(d && d.favorited)
						uni.showToast({ title: this.favorited ? '已收藏' : '已取消收藏', icon: 'none' })
					})
					.catch((e) => {
						if (e && e.needLogin) {
							uni.showToast({ title: '登录一下就好', icon: 'none' })
							return
						}
						uni.showToast({ title: '没成功，再点一次', icon: 'none' })
					})
					.then(() => {
						this.favSubmitting = false
					})
			},

			openShare() {
				this.shareVisible = true
			},

			onExit() {
				this.clearTimer()
				if (getCurrentPages().length > 1) {
					uni.navigateBack()
				} else {
					uni.reLaunch({ url: '/pages/index/index' })
				}
			}
		}
	}
</script>

<style>
	.page {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
		background-color: var(--bg);
	}

	/* ===== 顶栏 ===== */
	.topbar {
		flex-shrink: 0;
	}

	/* 高度/上边距/右侧留白都以微信胶囊为准，由 nav.navInnerStyle 注入：
	   内容区 = 胶囊那条带子，所以左边 ‹ 和右边"退出引导"都和胶囊齐平。
	   下面这组静态值 = 拿不到胶囊数据时的兜底 */
	.topbar-inner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 32px;
		margin-top: 6px;
		padding: 0 16rpx;
		padding-right: 98px;
	}

	.topbar-left {
		display: flex;
		align-items: center;
	}

	/* 44px 触控目标（88rpx），与右上角 ✕ 对称 */
	.step-back {
		width: 88rpx;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.step-back-icon {
		font-size: 56rpx;
		line-height: 1;
		color: var(--text);
	}

	.progress {
		font-size: 28rpx;
		font-weight: 600;
		color: var(--muted);
		letter-spacing: 2rpx;
	}

	/* 触控区保持 88rpx(=44px)，视觉上收成胶囊：比裸 ✕ 容易发现，也不会太抢眼。
	   不给左右 padding，好让"退出引导"和首页"我的"一样，只吃 navInnerStyle 里那 3px 呼吸距离 */
	.exit {
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: flex-end;
	}

	.exit-pill {
		display: flex;
		align-items: center;
		height: 32px;
		padding: 0 20rpx;
		border: 2rpx solid var(--border);
		border-radius: 999rpx;
	}

	.exit-ico {
		margin-right: 8rpx;
	}

	.exit-label {
		margin-left: 8rpx;
		font-size: 24rpx;
		color: var(--muted);
	}

	.hover-dim {
		opacity: 0.55;
	}

	/* ===== 滚轴 ===== */
	.roller {
		flex: 1;
		height: 0;
		display: flex;
		flex-direction: column;
	}

	.swiper {
		flex: 1;
		height: 0;
	}

	.slot {
		box-sizing: border-box;
		height: 100%;
		padding: 12rpx 32rpx;
	}

	.card {
		box-sizing: border-box;
		width: 100%;
		height: 100%;
		display: flex;
		flex-direction: column;
		padding: 40rpx 36rpx;
		overflow: hidden;
		background-color: var(--card);
		border: 2rpx solid var(--border);
		border-radius: 32rpx;
		/* 邻居：缩小 + 半透明（3.3） */
		transform: scale(0.86);
		opacity: 0.42;
		transition: transform 0.26s ease, opacity 0.26s ease;
	}

	.card-current {
		transform: scale(1);
		opacity: 1;
		box-shadow: 0 12rpx 48rpx rgba(35, 32, 29, 0.1);
	}

	.card-top {
		flex-shrink: 0;
		display: flex;
		align-items: center;
	}

	.card-order {
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

	.card-title {
		flex: 1;
		min-width: 0;
		font-size: 28rpx;
		color: var(--muted);
	}

	.card-body {
		flex: 1;
		min-height: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 24rpx 0;
		overflow: hidden;
	}

	.card-instruction {
		font-size: 46rpx;
		font-weight: 700;
		line-height: 1.5;
		color: var(--text);
		text-align: center;
	}

	/* ===== 计时器 ===== */
	/* #050：唯一改动 —— 倒计时和按钮从"左右并排"改成"上下排列、水平居中"。
	   字号/颜色/圆角/按钮尺寸全部沿用原版；不加圆环、不加动效、不改文案。 */
	.timer {
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding-top: 8rpx;
	}

	.timer-clock {
		font-size: 56rpx;
		font-weight: 700;
		color: var(--accent);
		letter-spacing: 2rpx;
	}

	.timer-btn {
		margin-top: 24rpx;
		height: 76rpx;
		padding: 0 40rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 999rpx;
		font-size: 28rpx;
		font-weight: 600;
	}

	.timer-btn-go {
		background-color: var(--accent);
		color: #ffffff;
	}

	.timer-btn-stop {
		border: 2rpx solid var(--border);
		color: var(--text);
	}

	.timer-idle {
		font-size: 32rpx;
		color: var(--muted);
	}

	/* ===== 可展开解释 ===== */
	.explain {
		flex-shrink: 0;
		margin-top: 24rpx;
		padding-top: 24rpx;
		border-top: 2rpx solid var(--border);
	}

	.explain-head {
		display: flex;
		align-items: center;
		/* #058④⑤：整条可点 —— 占满卡片宽度、至少 44px 高（触控目标下限），
		   原来只有"▸ 为什么这么做"这几个字形能点，偏一点就点不到。 */
		width: 100%;
		box-sizing: border-box;
		min-height: 44px;
		padding: 8px 0;
	}
	/* 有鼠标的桌面端给手型光标，明确告诉用户"这一整条都能点" */
	@media (hover: hover) {
		.explain-head {
			cursor: pointer;
		}
	}

	.explain-arrow {
		margin-right: 10rpx;
		font-size: 24rpx;
		color: var(--accent);
	}

	.explain-label {
		font-size: 28rpx;
		color: var(--accent);
	}

	.explain-body {
		max-height: 320rpx;
		margin-top: 16rpx;
	}

	.explain-text {
		display: block;
		font-size: 27rpx;
		line-height: 1.7;
		color: var(--muted);
	}

	/* ===== 完成卡（笔记 / 评分 / 收藏闭环） ===== */
	.card-done {
		padding: 32rpx 28rpx;
	}

	.done-scroll {
		width: 100%;
		height: 100%;
	}

	.done-head {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.done-head-row {
		display: flex;
		align-items: center;
	}

	.done-head-row .app-icon {
		margin-right: 10rpx;
	}

	.done-title {
		font-size: 40rpx;
		font-weight: 700;
		color: var(--text);
	}

	.done-sub {
		margin-top: 8rpx;
		font-size: 26rpx;
		color: var(--muted);
		text-align: center;
	}

	.done-block {
		margin-top: 28rpx;
		padding-top: 24rpx;
		border-top: 2rpx solid var(--border);
	}

	.done-label {
		display: block;
		font-size: 26rpx;
		color: var(--muted);
	}

	.done-input {
		box-sizing: border-box;
		width: 100%;
		height: 132rpx;
		margin-top: 16rpx;
		padding: 20rpx 24rpx;
		border-radius: 20rpx;
		background-color: var(--bg);
		font-size: 28rpx;
		line-height: 1.5;
		color: var(--text);
	}

	.done-ph {
		color: var(--muted);
	}

	.done-row {
		display: flex;
		align-items: center;
		margin-top: 20rpx;
	}

	.done-row .done-mini {
		margin-right: 16rpx;
	}

	.done-mini {
		height: 72rpx;
		padding: 0 36rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 999rpx;
		background-color: var(--accent-soft);
		color: var(--accent);
		font-size: 26rpx;
	}

	.done-mini-ico {
		margin-right: 8rpx;
	}

	.done-mini-off {
		background-color: var(--bg);
		color: var(--muted);
	}

	/* 收藏胶囊：未收藏/已收藏都落在这上面，要比"记下来"更中性一点 */
	.done-mini-wide {
		background-color: var(--bg);
		border: 2rpx solid var(--border);
		color: var(--text);
	}

	.done-tip {
		margin-left: 20rpx;
		font-size: 24rpx;
		color: var(--accent);
	}

	.done-tip-block {
		display: block;
		margin-left: 0;
		margin-top: 12rpx;
	}

	.stars {
		display: flex;
		align-items: flex-start;
		margin-top: 12rpx;
	}

	.star {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.star-icon {
		font-size: 56rpx;
		line-height: 1.2;
		color: var(--border);
	}

	.star-on {
		color: var(--accent);
	}

	/* 固定高度：只有 1/3/5 星有锚定文字，否则整行会跳 */
	.star-hint {
		height: 28rpx;
		font-size: 20rpx;
		color: var(--muted);
	}

	/* 完成卡主出口：btn-accent 已给 88rpx 高（=44px 触控标准）与主题强调色，这里只管宽度与间距 */
	.done-exit {
		width: 360rpx;
		margin: 40rpx auto 0;
	}

	/* ===== 首次提示 ===== */
	.hintbar {
		flex-shrink: 0;
		height: 96rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		padding-bottom: constant(safe-area-inset-bottom);
		padding-bottom: env(safe-area-inset-bottom);
	}

	.hint-text {
		font-size: 26rpx;
		color: var(--muted);
	}

	/* ===== #058⑧ 电脑端底部操作条 =====
	   只在宽屏渲染（v-if="isWide"），手机/mp 完全不出现，所以这里不写媒体查询也不影响手机端 */
	.step-nav {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px var(--content-pad) calc(16px + env(safe-area-inset-bottom));
	}
	.step-nav-btn {
		box-sizing: border-box;
		min-height: 44px;
		padding: 0 20px;
		border: 1px solid var(--border);
		border-radius: var(--r-btn);
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 15px;
		color: var(--text);
		cursor: pointer;
	}
	.step-nav-main {
		flex: 1;
		border-color: var(--accent);
		background-color: var(--accent);
		color: var(--accent-text);
		font-weight: 600;
	}
	.step-nav-off {
		opacity: 0.45;
	}
	.step-nav-mid {
		flex-shrink: 0;
		font-size: 13px;
		color: var(--muted);
	}

	/* ===== 加载 / 错误 ===== */
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
	/* ===== 网页版（H5）：只换外层容器（设计规范 §7.3） ===== */
	/* #ifdef H5 */
	/* #035 ④：步骤卡片圆角统一到 --r-card（基类 32rpx 在手机上≈21px，比卡片规范值大一倍多） */
	.card {
		border-radius: var(--r-card);
	}
	/* ⚠️ 滚轴 / 计时 / 步骤跳转逻辑完全不动，这里只把整块内容在电脑端居中限宽。
	   460px 来自任务 #025；设计规范 §7.3 写的是 420px，以任务为准（差 40px，可改）。
	   #058⑫：460px 在 1440/1920 屏上两侧各空 500/730px，"内容太少占屏"就是这么来的 →
	   大屏按档放宽（仍是"专注一列"，不会拉成超宽行）。 */
	@media (min-width: 1024px) {
		.page {
			max-width: 560px;
			margin: 0 auto;
			border-left: 1px solid var(--border);
			border-right: 1px solid var(--border);
		}
	}
	@media (min-width: 1440px) {
		.page {
			max-width: 720px;
		}
		/* 大屏上正文字号跟着抬一点，别显小 */
		.card-instruction {
			font-size: 22px !important;
		}
	}
	/* #038①：执行页顶栏没有标题，只有"2/5"这样的进度文字；
	   字号/行高跟其他页标题走同一套变量，视觉一致。 */
	.progress {
		font-size: var(--nav-fs) !important;
		line-height: var(--nav-h) !important;
	}
	/* #endif */
</style>
