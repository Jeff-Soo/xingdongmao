<template>
	<!-- #040 第二层：蒙层高亮（教操作）。H5 专属，小程序端不渲染 -->
	<view v-if="IS_H5 && visible && rect" class="tour">
		<!-- 遮罩用 4 块拼出"挖空区"：比 box-shadow 溢出差值好算，也不怕目标贴边 -->
		<view class="tour-mask" :style="maskTop"></view>
		<view class="tour-mask" :style="maskBottom"></view>
		<view class="tour-mask" :style="maskLeft"></view>
		<view class="tour-mask" :style="maskRight"></view>

		<!-- 高亮框：2px 标志色描边 + 淡光晕。
		     pierce 的步骤放行点击（挖空区可点穿，真的能操作目标）；其余挡住，防误触真实动作 -->
		<view class="tour-hole" :class="{ 'hole-open': pierced }" :style="holeStyle"></view>

		<view class="tour-tip" :style="tipStyle">
			<view class="tip-head">
				<text class="tip-step">第 {{ step + 1 }} / {{ list.length }} 步</text>
				<text v-if="!pierced" class="tip-badge">看看就好</text>
				<text class="tip-skip" hover-class="hover-dim" @click="finish">跳过</text>
			</view>
			<text class="tip-text">{{ current.text }}</text>
			<view class="tip-next btn-accent" hover-class="hover-dim" @click="next">
				<text>{{ last ? '懂了' : '下一步' }}</text>
			</view>
		</view>
	</view>
</template>

<script>
	import { IS_H5 } from '@/utils/config.js'
	import { markDone, TOUR_KEY } from '@/utils/onboarding.js'

	export default {
		name: 'OnboardingTour',
		props: {
			visible: { type: Boolean, default: false },
			// 高亮步骤由页面传（#040 首页 / #041 创建页各一套）；不传就用首页那套
			steps: { type: Array, default: null },
			// 走完/跳过时落哪个标记（utils/onboarding.js 的 key）
			markKey: { type: String, default: TOUR_KEY }
		},
		data() {
			return {
				IS_H5,
				step: 0,
				rect: null,
				tipBelow: true,
				tipTop: null,
				tipBottom: null,
				tapHandler: null,
				tapTarget: null,
				// 首页那套（默认）。选择器不存在就自动跳过这一步（见 waitTarget），绝不卡死。
				// pierce：stay=可以操作但不推进 / next=操作完进下一步 / end=操作完收场（弹层类目标）
				homeSteps: [
					{ sel: '.search-box', text: '心里想着的那件事，直接打两个字试试——比如「出门」', pierce: 'stay' },
					{ sel: '.list .card', text: '点开看看步骤；顺手点★收起来，下次不用再翻', pierce: 'end' },
					{ sel: '.fab', text: '有自己的一套做法？从这儿写成卡片，以后照着做', pierce: 'end' }
				]
			}
		},
		computed: {
			// 页面传了 steps 就用页面的，没传用首页那套
			list() {
				return this.steps && this.steps.length ? this.steps : this.homeSteps
			},
			last() {
				return this.step >= this.list.length - 1
			},
			current() {
				return this.list[this.step] || { text: '' }
			},
			// 这一步是否允许点穿（能点到下面被高亮的真实元素）
			pierced() {
				return !!(this.current && this.current.pierce)
			},
			maskTop() {
				if (!this.rect) return null
				return { top: '0', left: '0', width: '100%', height: this.rect.top + 'px' }
			},
			maskBottom() {
				if (!this.rect) return null
				return { top: this.rect.top + this.rect.h + 'px', left: '0', width: '100%', bottom: '0' }
			},
			maskLeft() {
				if (!this.rect) return null
				return {
					top: this.rect.top + 'px',
					left: '0',
					width: this.rect.left + 'px',
					height: this.rect.h + 'px'
				}
			},
			maskRight() {
				if (!this.rect) return null
				return {
					top: this.rect.top + 'px',
					left: this.rect.left + this.rect.w + 'px',
					right: '0',
					height: this.rect.h + 'px'
				}
			},
			holeStyle() {
				if (!this.rect) return null
				return {
					top: this.rect.top + 'px',
					left: this.rect.left + 'px',
					width: this.rect.w + 'px',
					height: this.rect.h + 'px'
				}
			},
			tipStyle() {
				const s = { left: '16px', right: '16px' }
				if (this.tipTop !== null) s.top = this.tipTop + 'px'
				if (this.tipBottom !== null) s.bottom = this.tipBottom + 'px'
				return s
			}
		},
		watch: {
			visible(v) {
				if (v) {
					this.step = 0
					this.rect = null
					this.$nextTick(() => this.measure())
				}
			}
		},
		mounted() {
			if (typeof window !== 'undefined') window.addEventListener('resize', this.onViewportChange)
		},
		// #057⑮：beforeDestroy 是 Vue 2 的钩子，这个项目是 Vue 3（vueVersion:"3"），
		// 写在这里等于死代码 —— 组件销毁时 resize 监听和 document 上的点按监听都不会被摘掉。
		// 换成 Vue 3 的 beforeUnmount，行为才是当初想要的那样。
		beforeUnmount() {
			if (typeof window !== 'undefined') window.removeEventListener('resize', this.onViewportChange)
			this.unbindTap()
		},
		methods: {
			sleep(ms) {
				return new Promise((r) => setTimeout(r, ms))
			},
			// 首页列表是异步拉的：给目标 2.4s 出现时间，还不出现就跳过这一步
			waitTarget(step) {
				return new Promise((resolve) => {
					let tries = 0
					const tick = () => {
						const el = this.pick(step)
						if (el) return resolve(el)
						tries += 1
						if (tries > 12) return resolve(null)
						setTimeout(tick, 200)
					}
					tick()
				})
			},
			pick(step) {
				if (typeof document === 'undefined' || !step) return null
				// 卡片优先挑"真卡"：加载中的骨架卡也带 .card，但里面是 .sk-block
				if (step.sel === '.list .card') {
					const all = document.querySelectorAll('.list .card')
					for (let i = 0; i < all.length; i++) {
						if (!all[i].querySelector('.sk-block')) return all[i]
					}
					return all.length ? all[0] : null
				}
				return document.querySelector(step.sel)
			},
			async measure() {
				try {
					const target = await this.waitTarget(this.current)
					if (!target || !this.visible) return this.next()
					try {
						target.scrollIntoView({ block: 'center' })
					} catch (e) {
						// 老浏览器不支持参数也没关系，位置照样能算
					}
					await this.sleep(300) // 等滚动稳定，否则量到的是滚动前的位置
					if (!this.visible) return
					this.place(target)
					this.bindTap(target)
				} catch (e) {
					this.finish() // 任何意外都收场，不留半透明蒙层卡住页面
				}
			},
			place(el) {
				const pad = 6
				const r = el.getBoundingClientRect()
				const vw = window.innerWidth
				const vh = window.innerHeight
				const w = Math.min(r.width + pad * 2, vw - 8)
				this.rect = {
					left: Math.max(4, Math.min(r.left - pad, vw - w - 4)),
					top: Math.max(4, r.top - pad),
					w: w,
					h: r.height + pad * 2
				}
				// 气泡放下方；下方放不下就翻到上方
				const tipH = 172
				const below = this.rect.top + this.rect.h + 14
				this.tipBelow = below + tipH < vh - 8
				if (this.tipBelow) {
					this.tipTop = below
					this.tipBottom = null
				} else {
					this.tipTop = null
					this.tipBottom = Math.max(12, vh - this.rect.top + 14)
				}
			},
			onViewportChange() {
				// 转屏/改窗口大小后重新量一次，别让高亮框错位
				if (this.visible && this.rect) {
					const el = this.pick(this.current)
					if (el) this.place(el)
				}
			},
			// 可点穿的步骤：把点击监听挂在 document 的【捕获阶段】。
			// 这样引导会先于目标自己的处理收场——否则"从文本导入"的弹层会先弹出来，
			// 引导还压在上面（z-index 1000 > 弹层 20），两边打架。
			bindTap(el) {
				this.unbindTap()
				if (!this.pierced || typeof document === 'undefined') return
				this.tapTarget = el
				this.tapHandler = (e) => {
					if (!this.tapTarget || !this.tapTarget.contains(e.target)) return
					const mode = this.current && this.current.pierce
					if (mode === 'end') this.finish()      // 点开弹层类：引导先退场
					else if (mode === 'next') this.next()  // 点了就算完成这一步
					// 'stay'：只让用户操作（例如聚焦输入框），推进仍交给"下一步"
				}
				document.addEventListener('click', this.tapHandler, true)
			},
			unbindTap() {
				if (this.tapHandler && typeof document !== 'undefined') {
					document.removeEventListener('click', this.tapHandler, true)
				}
				this.tapHandler = null
				this.tapTarget = null
			},
			next() {
				if (this.last) return this.finish()
				this.unbindTap()
				this.step += 1
				this.rect = null
				this.$nextTick(() => this.measure())
			},
			// 走完和跳过都走这里：先落标记再通知外面
			finish() {
				this.unbindTap()
				markDone(this.markKey)
				this.rect = null
				this.$emit('done')
			}
		}
	}
</script>

<style scoped>
	/* #ifdef H5 */
	/* 容器只作定位壳，本身不拦事件：拦截交给 4 块遮罩，气泡/高亮框各管自己。
	   ⚠️ z-index 必须给：#042 实测发现，没有它时页面里"带 z-index 的 fixed 元素"
	   （创建页底部操作栏 z-index 15、首页 ＋ 按钮 30）会盖在引导上面 ——
	   既没被遮罩压暗，挖空区也挡不住它们，点上去就真的触发了（"发布"会被误触）。 */
	.tour {
		position: fixed;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		z-index: 1000;
		pointer-events: none;
	}

	.tour-mask {
		position: fixed;
		background-color: var(--scrim-tour);
		pointer-events: auto;
	}

	.tour-hole {
		position: fixed;
		box-sizing: border-box;
		border-radius: 14px;
		box-shadow: 0 0 0 2px var(--accent), 0 0 28px var(--accent-soft);
		transition: top 200ms ease, left 200ms ease, width 200ms ease, height 200ms ease;
		/* #042 根因就在这一行：以前这里是 auto（默认），
		   挖空区上盖着一个透明盒子，把点向目标的点击全吃掉了 → "点不进去" */
		pointer-events: auto;
	}

	/* 可点穿的步骤：挖空区放行点击，用户能真的操作被高亮的元素 */
	.tour-hole.hole-open {
		pointer-events: none;
	}

	.tour-tip {
		position: fixed;
		box-sizing: border-box;
		padding: 16px;
		border: 1px solid var(--border);
		border-radius: var(--r-card);
		background-color: var(--card);
		box-shadow: 0 12px 32px var(--scrim-tour);
		display: flex;
		flex-direction: column;
		pointer-events: auto; /* 容器放行了事件，气泡自己要收回来 */
	}

	.tip-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.tip-step {
		font-size: 12px;
		color: var(--muted);
	}

	/* #042：只示意、不点穿的步骤打个标，免得用户去点一个点不动的东西 */
	.tip-badge {
		margin-left: auto;
		margin-right: 10px;
		padding: 1px 8px;
		border-radius: var(--r-chip);
		background-color: var(--surface-2);
		font-size: 11px;
		color: var(--muted);
	}

	.tip-skip {
		min-height: 44px;
		padding: 0 2px;
		display: flex;
		align-items: center;
		font-size: 14px;
		color: var(--muted);
	}

	.tip-text {
		margin-top: 4px;
		font-size: 16px;
		line-height: 1.5;
		white-space: pre-line; /* 气泡文案允许写 \n 换行（创建页第 2 步是两句） */
		color: var(--text);
	}

	.tip-next {
		margin-top: 14px;
		height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 15px;
	}

	/* 平板/电脑：气泡固定在底部中间，别拉成通栏 */
	@media (min-width: 768px) {
		.tour-tip {
			left: 50% !important;
			right: auto !important;
			top: auto !important;
			bottom: 40px !important;
			width: 420px;
			margin-left: -210px;
		}
	}
	/* #endif */
</style>
