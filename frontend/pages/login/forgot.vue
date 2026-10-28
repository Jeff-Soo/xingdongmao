<template>
	<view class="page">
		<view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner" :style="nav.navInnerStyle">
				<view class="nav-btn" @click="goBack"><text class="nav-btn-icon">‹</text></view>
				<text class="nav-title">找回密码</text>
				<view class="nav-btn nav-btn-ghost"></view>
			</view>
		</view>

		<view class="wrap">
			<view class="card theme-card">
				<text class="title">忘记密码</text>
				<text class="sub">填注册时用的邮箱，我们把重置链接发给你（30 分钟内有效）</text>

				<input
					v-if="!sent"
					class="ipt"
					v-model="email"
					type="text"
					:disabled="submitting"
					placeholder="邮箱"
					placeholder-class="ipt-ph"
					confirm-type="done"
					@confirm="submit"
				/>
				<text v-if="errorMsg" class="err">{{ errorMsg }}</text>

				<!-- 提交后统一说这一句：跟邮箱有没有注册无关，不泄露账号情况 -->
				<view v-if="sent" class="ok">
					<text class="ok-title">邮件已发送</text>
					<text class="ok-desc">如果该邮箱已注册，重置邮件已经发出，请查收（垃圾箱也翻一下）</text>
				</view>

				<view v-else class="submit btn-accent" :class="{ 'submit-off': submitting }" hover-class="hover-dim" @click="submit">
					<text>{{ submitting ? '发送中…' : '发送重置邮件' }}</text>
				</view>

				<view class="switch" hover-class="hover-dim" @click="goLogin">
					<text class="switch-text">想起密码了？去登录</text>
				</view>
			</view>
		</view>
	</view>
</template>

<script>
	import { getNavBarMetrics } from '@/utils/nav.js'
	import { requestPasswordReset } from '@/utils/token.js'
	import { errText } from '@/api/request.js'

	export default {
		data() {
			return {
				statusBarHeight: 20,
				// 导航栏尺寸（对齐微信胶囊），onLoad 里用 getNavBarMetrics() 填
				nav: {},
				email: '',
				submitting: false,
				// 提交成功后就不再显示表单，只留那句统一提示
				sent: false,
				errorMsg: ''
			}
		},
		onLoad() {
			this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
			this.nav = getNavBarMetrics(this.statusBarHeight, { reserveRight: false })
		},
		methods: {
			submit() {
				if (this.submitting || this.sent) return
				const email = (this.email || '').trim()
				if (!email || email.indexOf('@') < 0) {
					this.errorMsg = '请填一个正确的邮箱'
					return
				}

				this.submitting = true
				this.errorMsg = ''
				requestPasswordReset(email)
					.then(() => {
						this.sent = true
					})
					.catch((e) => {
						this.errorMsg = errText(e, '没发出去，再试一次')
					})
					.then(() => {
						this.submitting = false
					})
			},

			goLogin() {
				// 从登录页点进来的话直接退回，别在栈里堆一层
				if (getCurrentPages().length > 1) {
					uni.navigateBack()
				} else {
					uni.reLaunch({ url: '/pages/login/login' })
				}
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

	.ok {
		margin-top: 28rpx;
		padding: 24rpx;
		border-radius: 20rpx;
		background-color: var(--accent-soft);
	}

	.ok-title {
		display: block;
		font-size: 30rpx;
		font-weight: 600;
		color: var(--accent);
	}

	.ok-desc {
		display: block;
		margin-top: 10rpx;
		font-size: 26rpx;
		line-height: 1.5;
		color: var(--text);
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
	.ok {
		margin-top: 18px;
		padding: 16px;
		border-radius: var(--r-card);
	}
	.ok-title {
		font-size: 15px;
	}
	.ok-desc {
		margin-top: 6px;
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
