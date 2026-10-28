<template>
	<view class="page">
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">{{ isRegister ? '注册' : '登录' }}</text>
				<view class="nav-btn nav-btn-ghost"></view>
			</view>
		</view>

		<view class="wrap">
			<view class="card theme-card">
				<text class="title">行动锚</text>
				<text class="sub">{{ isRegister ? '注册一个账号，收藏和笔记就能存下来了' : '登录后即可收藏模板、记录反思笔记' }}</text>

				<input
					class="ipt"
					v-model="email"
					type="text"
					:disabled="submitting"
					placeholder="邮箱"
					placeholder-class="ipt-ph"
					confirm-type="next"
					@confirm="focusPassword"
				/>
				<input
					class="ipt"
					v-model="password"
					:password="true"
					type="text"
					:disabled="submitting"
					placeholder="密码（至少 6 位）"
					placeholder-class="ipt-ph"
					confirm-type="done"
					@confirm="submit"
				/>

				<text v-if="errorMsg" class="err">{{ errorMsg }}</text>

				<view class="submit btn-accent" :class="{ 'submit-off': submitting }" hover-class="hover-dim" @click="submit">
					<text>{{ submitting ? '请稍候…' : (isRegister ? '注册并登录' : '登录') }}</text>
				</view>

				<view class="switch" hover-class="hover-dim" @click="toggleMode">
					<text class="switch-text">{{ isRegister ? '已有账号？去登录' : '还没有账号？注册一个' }}</text>
				</view>

				<!-- 只有登录模式才有"忘记密码"（注册模式没有密码可忘） -->
				<view v-if="!isRegister" class="switch switch-sub" hover-class="hover-dim" @click="goForgot">
					<text class="switch-text switch-forgot">忘记密码？</text>
				</view>
			</view>

			<text class="foot">网页版账号和微信小程序账号是两套，互不影响</text>
		</view>
	</view>
</template>

<script>
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { loginWithEmail, registerWithEmail, isLoggedIn } from '@/utils/token.js'
	import { errText } from '@/api/request.js'

	export default {
		data() {
			return {
				statusBarHeight: 20,
				// 导航栏尺寸（对齐微信胶囊），onLoad 里用 getNavBarMetrics() 填
				nav: {},
				email: '',
				password: '',
				// 同一页切换登录/注册，省一个页面
				isRegister: false,
				submitting: false,
				errorMsg: ''
			}
		},
		onLoad() {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
			// 已登录还停在登录页没意义（比如从收藏夹里点回来的）
			if (isLoggedIn()) {
				uni.navigateBack()
			}
		},
		methods: {
			toggleMode() {
				if (this.submitting) return
				this.isRegister = !this.isRegister
				this.errorMsg = ''
			},

			// 邮箱框回车 → 焦点给密码框（电脑端体验）
			focusPassword() {
				// uni 没有跨平台聚焦 API，这里只做提示，不强行抢焦点
			},

			submit() {
				if (this.submitting) return
				const email = (this.email || '').trim()
				const password = this.password || ''

				// 前端先拦一道，少一次网络来回（后端同样会校验）
				if (!email || email.indexOf('@') < 0) {
					this.errorMsg = '请填一个正确的邮箱'
					return
				}
				if (password.length < 6) {
					this.errorMsg = '密码至少 6 位'
					return
				}

				this.submitting = true
				this.errorMsg = ''
				const task = this.isRegister ? registerWithEmail(email, password) : loginWithEmail(email, password)
				task
					.then(() => {
						uni.showToast({ title: this.isRegister ? '注册成功' : '登录成功', icon: 'none' })
						// 等 toast 露个脸再走；直接进来的（刷新/分享）没有上一页，就回首页
						setTimeout(() => {
							if (getCurrentPages().length > 1) {
								uni.navigateBack()
							} else {
								uni.reLaunch({ url: '/pages/index/index' })
							}
						}, 600)
					})
					.catch((e) => {
						// 后端的原话（该邮箱已注册 / 邮箱或密码错误）直接显示出来
						this.errorMsg = errText(e, '登录没成，再试一次')
					})
					.then(() => {
						this.submitting = false
					})
			},

			goForgot() {
				uni.navigateTo({ url: '/pages/login/forgot' })
			},

			goBack() {
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
		background-color: var(--bg);
	}

	.nav {
		flex-shrink: 0;
		background-color: var(--card);
	}

	/* 高度/上边距以微信胶囊为准，由 nav.navInnerStyle 注入；下面是拿不到胶囊数据时的兜底 */
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

	.wrap {
		flex: 1;
		height: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 0 40rpx 80rpx;
	}

	.card {
		width: 100%;
		max-width: 640rpx;
		box-sizing: border-box;
		padding: 40rpx;
	}

	.title {
		display: block;
		font-size: 42rpx;
		font-weight: 700;
		color: var(--text);
	}

	.sub {
		display: block;
		margin-top: 12rpx;
		font-size: 26rpx;
		line-height: 1.5;
		color: var(--muted);
	}

	.ipt {
		height: 92rpx;
		margin-top: 28rpx;
		padding: 0 24rpx;
		box-sizing: border-box;
		border-radius: 20rpx;
		background-color: var(--bg);
		border: 2rpx solid var(--border);
		font-size: 30rpx;
		color: var(--text);
	}

	.ipt-ph {
		color: var(--muted);
	}

	.err {
		display: block;
		margin-top: 20rpx;
		font-size: 26rpx;
		color: #c0392b;
	}

	.submit {
		margin-top: 36rpx;
	}

	.submit-off {
		opacity: 0.6;
	}

	.switch {
		margin-top: 28rpx;
		display: flex;
		justify-content: center;
	}

	.switch-text {
		font-size: 26rpx;
		color: var(--accent);
	}

	.switch-sub {
		margin-top: 20rpx;
	}

	.switch-forgot {
		color: var(--muted);
	}

	.foot {
		margin-top: 36rpx;
		font-size: 22rpx;
		color: var(--muted);
		text-align: center;
	}

	/* ===== 网页版（H5）：跟其他页同一套尺寸与留白 ===== */
	/* #ifdef H5 */
	.card {
		max-width: 420px;
		padding: 28px;
	}
	.title {
		font-size: 22px;
	}
	.sub {
		margin-top: 8px;
		font-size: 13px;
	}
	.ipt {
		height: 44px;
		margin-top: 16px;
		padding: 0 14px;
		border-radius: var(--r-btn);
		background-color: var(--surface-2);
		border: 1px solid var(--border);
		font-size: 14px;
	}
	.err {
		margin-top: 12px;
		font-size: 13px;
	}
	.submit {
		margin-top: 20px;
		height: 44px;
	}
	.switch {
		margin-top: 18px;
	}
	.switch-text {
		font-size: 13px;
	}
	.foot {
		margin-top: 20px;
		font-size: 12px;
	}
	/* #endif */
</style>
