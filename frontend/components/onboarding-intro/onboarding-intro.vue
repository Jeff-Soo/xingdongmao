<template>
	<!-- #040 第一层：全屏引导（讲概念）。H5 专属，小程序端不渲染 -->
	<view v-if="IS_H5 && visible" class="intro">
		<view class="intro-skip" hover-class="hover-dim" @click="finish"><text>跳过</text></view>

		<!-- 可滑：跟手位移由 step 驱动（阈值 40px 翻页），手机上滑、桌面上点圆点/按钮 -->
		<view
			class="intro-viewport"
			@touchstart="onTouchStart"
			@touchend="onTouchEnd"
		>
			<view class="intro-track" :style="{ transform: 'translateX(' + -step * 100 + '%)' }">
				<view v-for="(s, i) in screens" :key="s.key" class="intro-slide">
					<!-- ⑤ 图形全部用 CSS/SVG 画，不依赖外部素材；配色跟随主题变量 -->
					<view class="art">
						<view v-if="i === 0" class="art-cards">
							<view class="ac ac-3"></view>
							<view class="ac ac-2"></view>
							<view class="ac ac-1">
								<text class="ac-tick">✓</text>
							</view>
						</view>
						<view v-else-if="i === 1" class="art-flow">
							<view class="af-bar">
								<text class="af-text">出门</text>
								<view class="af-caret"></view>
							</view>
							<view class="af-row">
								<text class="af-star">★</text>
								<text class="af-arrow">→</text>
								<text class="af-play">▶</text>
							</view>
						</view>
						<view v-else class="art-plus">
							<view class="ap-ring ap-ring-1"></view>
							<view class="ap-ring ap-ring-2"></view>
							<view class="ap-core"><text class="ap-plus">＋</text></view>
						</view>
					</view>

					<text class="intro-title">{{ s.title }}</text>
					<text class="intro-desc">{{ s.desc }}</text>
				</view>
			</view>
		</view>

		<view class="intro-dots">
			<view
				v-for="(s, i) in screens"
				:key="'d' + s.key"
				class="dot"
				:class="{ 'dot-on': i === step }"
				@click="go(i)"
			></view>
		</view>

		<view class="intro-btn btn-accent" hover-class="hover-dim" @click="next">
			<text>{{ last ? '好，开始吧' : '下一步' }}</text>
		</view>
	</view>
</template>

<script>
	import { IS_H5 } from '@/utils/config.js'
	import { markIntroDone } from '@/utils/onboarding.js'

	export default {
		name: 'OnboardingIntro',
		props: {
			visible: { type: Boolean, default: false }
		},
		data() {
			return {
				IS_H5,
				step: 0,
				startX: 0,
				screens: [
					{
						key: 'what',
						title: '总忘的那几件事，其实能做成一页纸',
						desc: '出门前带什么、交接班怎么讲、搬家先动哪箱——拆成几步，做的时候照着看一眼就行。'
					},
					{
						key: 'how',
						title: '先找到此刻要用的那一张',
						desc: '搜个动作，或者随手翻翻。找到对的那张点★收起来，下次不用再找。'
					},
					{
						key: 'make',
						title: '用着用着，你会想改一张自己的',
						desc: '右下角那个＋，能照着你的做法写一张；AI 帮你理好的步骤，也能整段粘进来。'
					}
				]
			}
		},
		computed: {
			last() {
				return this.step >= this.screens.length - 1
			}
		},
		watch: {
			// 每次重新打开都从第一屏开始（"再看教程"要能完整看一遍）
			visible(v) {
				if (v) this.step = 0
			}
		},
		methods: {
			go(i) {
				if (i >= 0 && i < this.screens.length) this.step = i
			},
			next() {
				if (this.last) this.finish()
				else this.step += 1
			},
			prev() {
				if (this.step > 0) this.step -= 1
			},
			onTouchStart(e) {
				this.startX = e.touches && e.touches.length ? e.touches[0].clientX : 0
			},
			onTouchEnd(e) {
				const t = e.changedTouches && e.changedTouches.length ? e.changedTouches[0] : null
				if (!t) return
				const dx = t.clientX - this.startX
				if (dx <= -40) this.next()
				else if (dx >= 40) this.prev()
			},
			// 看完和跳过都走这里：先落标记再通知外面，保证"跳过"永远能收场、不会卡死
			finish() {
				markIntroDone()
				this.$emit('done')
			}
		}
	}
</script>

<style scoped>
	/* #ifdef H5 */
	.intro {
		position: fixed;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		z-index: 1000; /* 盖住导航、底部操作栏、弹层（最高的弹层是 20） */
		box-sizing: border-box;
		padding: calc(12px + env(safe-area-inset-top)) var(--content-pad)
			calc(20px + env(safe-area-inset-bottom));
		background-color: var(--bg);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.intro-skip {
		flex: none;
		align-self: flex-end;
		min-height: 44px; /* 触控目标 ≥ 44px */
		padding: 0 4px;
		display: flex;
		align-items: center;
		font-size: 14px;
		color: var(--muted);
	}

	.intro-viewport {
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.intro-track {
		display: flex;
		height: 100%;
		transition: transform 260ms ease;
	}

	.intro-slide {
		flex: 0 0 100%;
		box-sizing: border-box;
		padding: 0 4px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
	}

	.intro-title {
		margin-top: 28px;
		font-size: 22px;
		font-weight: 600;
		line-height: 1.4;
		color: var(--text);
	}

	.intro-desc {
		margin-top: 12px;
		max-width: 420px;
		font-size: 14px;
		line-height: 1.7;
		color: var(--text-2);
	}

	.intro-dots {
		flex: none;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 20px 0 18px;
	}

	.dot {
		width: 8px;
		height: 8px;
		margin: 0 5px;
		border-radius: 50%;
		background-color: var(--border);
		transition: width 200ms ease, background-color 200ms ease;
	}

	.dot-on {
		width: 22px;
		border-radius: 999px;
		background-color: var(--accent);
	}

	.intro-btn {
		flex: none;
		height: 48px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 16px;
	}

	/* ===== 三屏的动画插画 ===== */
	.art {
		width: 220px;
		height: 170px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* 第一屏：三张卡片叠起来，最上面一张打勾 */
	.art-cards {
		position: relative;
		width: 190px;
		height: 150px;
	}

	.ac {
		position: absolute;
		left: 50%;
		width: 150px;
		height: 54px;
		box-sizing: border-box;
		border: 1px solid var(--border);
		border-radius: var(--r-card);
		background-color: var(--card);
		transform: translateX(-50%);
	}

	.ac-3 {
		top: 0;
		opacity: 0.35;
	}
	.ac-2 {
		top: 28px;
		opacity: 0.7;
	}
	.ac-1 {
		top: 56px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-color: var(--accent-soft);
		animation: intro-rise 2.4s ease-in-out infinite;
	}

	.ac-tick {
		font-size: 22px;
		font-weight: 700;
		color: var(--accent);
	}

	@keyframes intro-rise {
		0%,
		100% {
			transform: translateX(-50%) translateY(0);
		}
		50% {
			transform: translateX(-50%) translateY(-6px);
		}
	}

	/* 第二屏：搜索框里打字 → 收藏 → 开始 */
	.art-flow {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.af-bar {
		display: flex;
		align-items: center;
		width: 190px;
		height: 42px;
		box-sizing: border-box;
		padding: 0 14px;
		border: 1px solid var(--border);
		border-radius: var(--r-btn);
		background-color: var(--surface-2);
	}

	.af-text {
		font-size: 14px;
		color: var(--text);
	}

	.af-caret {
		width: 2px;
		height: 16px;
		margin-left: 2px;
		background-color: var(--accent);
		animation: intro-blink 1s step-end infinite;
	}

	@keyframes intro-blink {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0;
		}
	}

	.af-row {
		display: flex;
		align-items: center;
		margin-top: 22px;
	}

	.af-star,
	.af-play {
		width: 44px;
		height: 44px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 18px;
	}

	.af-star {
		background-color: var(--accent-soft);
		color: var(--accent);
		animation: intro-pop 2.4s ease-in-out infinite;
	}

	.af-play {
		background-color: var(--accent);
		color: var(--accent-text);
		animation: intro-pop 2.4s ease-in-out infinite 0.4s;
	}

	.af-arrow {
		margin: 0 14px;
		font-size: 16px;
		color: var(--muted);
	}

	@keyframes intro-pop {
		0%,
		100% {
			transform: scale(1);
		}
		50% {
			transform: scale(1.12);
		}
	}

	/* 第三屏：右下角的 ＋ 带涟漪 */
	.art-plus {
		position: relative;
		width: 150px;
		height: 150px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.ap-core {
		width: 62px;
		height: 62px;
		border-radius: 50%;
		background-color: var(--accent);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.ap-plus {
		font-size: 28px;
		color: var(--accent-text);
	}

	.ap-ring {
		position: absolute;
		width: 62px;
		height: 62px;
		border: 1px solid var(--accent);
		border-radius: 50%;
		animation: intro-ripple 2.4s ease-out infinite;
	}

	.ap-ring-2 {
		animation-delay: 1.2s;
	}

	@keyframes intro-ripple {
		0% {
			transform: scale(1);
			opacity: 0.6;
		}
		100% {
			transform: scale(2.1);
			opacity: 0;
		}
	}

	/* 平板/电脑：插画和字号都放大一档，别显得空 */
	@media (min-width: 768px) {
		.intro-title {
			font-size: 26px;
		}
		.intro-desc {
			font-size: 15px;
		}
		.art {
			width: 280px;
			height: 200px;
		}
		.intro-btn {
			max-width: 360px;
			align-self: center;
			width: 100%;
		}
	}
	/* #endif */
</style>
