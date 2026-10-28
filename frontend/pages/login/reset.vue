<template>
	<view class="page">
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">重置密码</text>
				<view class="nav-btn nav-btn-ghost"></view>
			</view>
		</view>

		<view class="wrap">
			<view class="card theme-card">
				<text class="title">设置新密码</text>
				<text class="sub">{{ token ? '新密码至少 6 位，设好就能直接登录' : '这个链接里没有 token，请重新申请一次' }}</text>

				<view v-if="token" class="form">
					<input
						class="ipt"
						v-model="password"
						:password="true"
						type="text"
						:disabled="submitting"
						placeholder="新密码（至少 6 位）"
						placeholder-class="ipt-ph"
					/>
					<input
						class="ipt"
						v-model="password2"
						:password="true"
						type="text"
						:disabled="submitting"
						placeholder="再输一遍"
						placeholder-class="ipt-ph"
						confirm-type="done"
						@confirm="submit"
					/>
					<text v-if="errorMsg" class="err">{{ errorMsg }}</text>

					<view class="submit btn-accent" :class="{ 'submit-off': submitting }" hover-class="hover-dim" @click="submit">
						<text>{{ submitting ? '提交中…' : '确认重置' }}</text>
					</view>
				</view>

				<view class="switch" hover-class="hover-dim" @click="goForgot">
					<text class="switch-text">链接失效了？重新申请</text>
				</view>
			</view>
		</view>
	</view>
</template>

<script>
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { resetPassword } from '@/utils/token.js'
	import { errText } from '@/api/request.js'

	export default {
		data() {
			return {
				statusBarHeight: 20,
				// 导航栏尺寸（对齐微信胶囊），onLoad 里用 getNavBarMetrics() 填
				nav: {},
				// 邮件里带过来的一次性 token
				token: '',
				password: '',
				password2: '',
				submitting: false,
				errorMsg: ''
			}
		},
		onLoad(options) {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
			this.token = (options && options.token) || ''
			if (!this.token) {
				this.errorMsg = '链接无效，请重新申请'
			}
		},
		methods: {
			submit() {
				if (this.submitting) return
				const password = this.password || ''
				if (password.length < 6) {
					this.errorMsg = '密码至少 6 位'
					return
				}
				if (password !== this.password2) {
					this.errorMsg = '两次输入的密码不一样'
					return
				}

				this.submitting = true
				this.errorMsg = ''
				resetPassword(this.token, password)
					.then(() => {
						uni.showToast({ title: '密码已重置，请用新密码登录', icon: 'none' })
						// 换掉当前页：token 已经用掉了，退回来也没意义
						setTimeout(() => uni.reLaunch({ url: '/pages/login/login' }), 800)
					})
					.catch((e) => {
						// 后端原话是「链接无效或已过期」，直接用
						this.errorMsg = errText(e, '链接无效，请重新申请')
					})
					.then(() => {
						this.submitting = false
					})
			},

			goForgot() {
				uni.reLaunch({ url: '/pages/login/forgot' })
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

	.form {
		display: block;
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

	/* ===== 网页版（H5）===== */
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
	/* #endif */
</style>
