<template>
	<!-- 分享面板：显示分享图（长按可存/转发）+ 显式保存按钮 + 微信转发按钮 -->
	<view v-if="visible" class="mask" @click="close">
		<view class="sheet" @click.stop>
			<view class="sheet-head">
				<text class="sheet-title">分享这个模板</text>
				<text class="sheet-close" hover-class="hover-dim" @click="close">✕</text>
			</view>

			<scroll-view class="preview" scroll-y>
				<!-- show-menu-by-longpress：长按图片弹「保存图片 / 转发」 -->
				<image
					class="share-img"
					:src="imgUrl"
					mode="widthFix"
					:show-menu-by-longpress="true"
					@error="onImgError"
					@click="openZoom"
				/>
			</scroll-view>

			<text class="tip">{{ tip }}</text>

			<view class="actions">
				<view class="btn-ghost act" hover-class="hover-dim" @click="saveToAlbum">
					<text>{{ saveText }}</text>
				</view>
				<!-- open-type=share 走宿主页面的 onShareAppMessage，弹出微信转发面板；
				     网页版没有这个面板，按钮点了没反应，所以隐藏 -->
				<button v-if="!isH5" class="btn-accent act act-main" open-type="share" hover-class="hover-dim">
					<text>转发给好友</text>
				</button>
			</view>
		</view>

		<!-- #ifdef H5 -->
		<!-- 点图放大：全屏预览 + 滚轮缩放（设计规范 §五） -->
		<view v-if="zoomed" class="zoom-mask" @click.stop="closeZoom">
			<image class="zoom-img" :src="imgUrl" mode="widthFix" :style="{ transform: 'scale(' + zoom + ')' }" />
			<text class="zoom-tip">滚轮缩放 · 点击空白处关闭</text>
		</view>
		<!-- #endif -->
	</view>
</template>

<script>
	import { BASE_URL } from '@/api/request.js'
	import { IS_H5 } from '@/utils/config.js'

	export default {
		name: 'ShareSheet',
		props: {
			visible: { type: Boolean, default: false },
			patternId: { type: [String, Number], default: '' }
		},
		emits: ['close'],
		data() {
			return {
				saving: false,
				failed: false,
				// 网页版没有"保存到相册"这回事，按钮和提示文案都跟着平台走（utils/config.js）
				isH5: IS_H5,
				// 网页版点图放大：是否全屏预览 + 当前缩放倍数
				zoomed: false,
				zoom: 1
			}
		},
		// #ifdef H5
		// 滚轮缩放挂在 window 上：uni 的 view 在 H5 虽然能收 DOM 事件，但 @wheel 不在 uni 支持的事件表里，
		// 直接监听更稳；只在打开预览时生效，关掉预览就是空转
		mounted() {
			this.onWheel = (e) => {
				if (!this.zoomed) return
				e.preventDefault()
				const next = this.zoom + (e.deltaY < 0 ? 0.2 : -0.2)
				this.zoom = Math.min(4, Math.max(0.5, Number(next.toFixed(2))))
			}
			window.addEventListener('wheel', this.onWheel, { passive: false })
		},
		beforeUnmount() {
			if (this.onWheel) window.removeEventListener('wheel', this.onWheel)
		},
		// #endif
		computed: {
			// 分享图是后端现画的 PNG，必须用完整地址（相对路径在小程序里取不到）
			// ?author=1 只有网页版带：后端默认画「官方」，小程序侧保持看不到用户昵称（#029）
			// #067 根因：uni 的 <image> 在 H5 会把【以 / 开头的路径】当成静态资源，
			// 前面拼上 H5 的 router base（/app/）——实测请求真的变成了
			//   /app/api/v1/quick/27/share/?author=1   → 落到 index.html（不是图片）→ 一直"加载失败"；
			// 而"打开图片"走 window.open，浏览器按 origin 解析 /api/v1/… → 200 正常。
			// 修法：H5 上直接给【带 origin 的绝对地址】，uni 就不再拼 base（小程序端本来就是绝对地址，不受影响）。
			// 跟 base 是 / 还是 /app/ 无关：拼不拼都得靠绝对地址才稳。
			imgUrl() {
				const path = BASE_URL + '/quick/' + this.patternId + '/share/' + (this.isH5 ? '?author=1' : '')
				// #ifdef H5
				if (typeof window !== 'undefined' && window.location && window.location.origin) {
					return window.location.origin + path
				}
				// #endif
				return path
			},
			saveText() {
				if (!this.isH5) return this.saving ? '保存中…' : '保存到相册'
				return '打开图片'
			},
			tip() {
				if (this.failed) {
					// #058⑨：把"要不要配域名"说清楚 ——
					// 网页版：分享图和页面同源，不需要任何域名配置；
					// 小程序：只有"代码主动下载图片"（保存到相册）才需要 downloadFile 合法域名，
					//        而长按图片走的是微信自带菜单，不需要配域名。
					if (this.isH5) return '分享图加载失败：检查网络或后端是否可用（网页版不需要配置任何微信域名）'
					return '分享图加载失败：直接长按图片用微信菜单保存/转发不需要配域名；只有用"保存到相册"按钮才需要在小程序后台把本站加进 downloadFile 合法域名'
				}
				return this.isH5 ? '图片会新开一页，长按（电脑上右键）即可保存或转发' : '长按图片可直接保存或转发（不需要配域名）'
			}
		},
		methods: {
			close() {
				this.$emit('close')
			},

			// ===== 点图放大（网页版）：全屏预览 + 滚轮缩放 =====
			openZoom() {
				// #ifdef H5
				this.zoom = 1
				this.zoomed = true
				// #endif
			},
			closeZoom() {
				this.zoomed = false
			},

			onImgError() {
				this.failed = true
			},

			// ===== 保存分享图 =====
			saveToAlbum() {
				// #ifdef H5
				// 浏览器没有"保存到相册"权限这回事：把图新开一页打开，用户长按/右键自己保存
				window.open(this.imgUrl, '_blank')
				// #endif
				// #ifndef H5
				if (this.saving) return
				this.saving = true
				uni.getSetting({
					success: (s) => {
						const auth = (s && s.authSetting) || {}
						// 之前明确拒过：不再弹系统框，直接引导去设置里开
						if (auth['scope.writePhotosAlbum'] === false) {
							this.saving = false
							this.guideSetting()
							return
						}
						this.download()
					},
					fail: () => this.download()
				})
				// #endif
			},
			download() {
				uni.downloadFile({
					url: this.imgUrl,
					success: (res) => {
						if (!res || res.statusCode !== 200 || !res.tempFilePath) {
							this.saving = false
							uni.showToast({ title: '图片没下下来', icon: 'none' })
							return
						}
						this.saveFile(res.tempFilePath)
					},
					fail: () => {
						this.saving = false
						uni.showToast({ title: '图片没下下来，检查域名白名单', icon: 'none' })
					}
				})
			},
			saveFile(filePath) {
				uni.saveImageToPhotosAlbum({
					filePath: filePath,
					success: () => {
						this.saving = false
						uni.showToast({ title: '已保存，去发朋友圈吧', icon: 'none' })
					},
					fail: (err) => {
						this.saving = false
						const msg = (err && err.errMsg) || ''
						if (msg.indexOf('auth') >= 0 || msg.indexOf('authorize') >= 0) this.guideSetting()
						else uni.showToast({ title: '没存上，再试一次', icon: 'none' })
					}
				})
			},
			guideSetting() {
				uni.showModal({
					title: '需要相册权限',
					content: '保存图片需要「保存到相册」权限，去设置里打开？',
					confirmText: '去设置',
					success: (r) => {
						if (r.confirm) uni.openSetting({})
					}
				})
			}
		}
	}
</script>

<style>
	.mask {
		position: fixed;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		z-index: 30;
		background-color: rgba(0, 0, 0, 0.55);
		display: flex;
		align-items: flex-end;
	}

	.sheet {
		box-sizing: border-box;
		width: 100%;
		padding: 32rpx 24rpx;
		padding-bottom: calc(32rpx + constant(safe-area-inset-bottom));
		padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
		border-radius: 32rpx 32rpx 0 0;
		background-color: var(--card);
		display: flex;
		flex-direction: column;
	}

	.sheet-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.sheet-title {
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text);
	}

	.sheet-close {
		padding: 0 12rpx;
		font-size: 28rpx;
		color: var(--muted);
	}

	.preview {
		max-height: 56vh;
		margin-top: 20rpx;
	}

	.share-img {
		width: 100%;
		border-radius: 20rpx;
		background-color: var(--bg);
	}

	.tip {
		display: block;
		margin-top: 16rpx;
		font-size: 22rpx;
		line-height: 1.5;
		color: var(--muted);
	}

	.actions {
		display: flex;
		align-items: center;
		margin-top: 20rpx;
	}

	.act {
		height: 88rpx;
	}

	.act-main {
		flex: 1;
		margin: 0;
		padding: 0;
		font-size: 32rpx;
		line-height: 1;
	}

	/* 抹掉小程序 button 默认那圈边框 */
	.act-main::after {
		border: none;
	}

	.hover-dim {
		opacity: 0.6;
	}

	/* #ifdef H5 */
	/* 网页版：电脑端把底部抽屉变成居中对话框（宽屏下拉满整屏很怪）；手机端保持从底部升起 */
	@media (min-width: 768px) {
		.mask {
			align-items: center;
		}
		.sheet {
			max-width: 480px;
			margin: 0 auto;
			border-radius: 12px;
		}
	}

	/* 点图放大：全屏预览 + 滚轮缩放（设计规范 §五） */
	.share-img {
		cursor: zoom-in;
	}

	.zoom-mask {
		position: fixed;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		z-index: 60;
		background-color: var(--scrim);
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		cursor: zoom-out;
	}

	.zoom-img {
		width: 80%;
		max-width: 720px;
		transition: transform 200ms ease;
	}

	.zoom-tip {
		position: absolute;
		bottom: 32px;
		font-size: 12px;
		color: var(--text-2);
		opacity: 0.8;
	}
	/* #endif */
</style>
