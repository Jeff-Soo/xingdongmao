<template>
	<!--
	  #073 统一图标组件：全站结构图标 + 模板图标都走这里（替代 emoji）

	  两端实现不一样，原因：小程序端不支持 CSS mask，所以
	    · H5：mask + background-color:currentColor → 颜色自动继承父级（深浅主题都不用改 JS）
	    · 小程序：background-image + base64 SVG → 颜色必须写死具体值，走下面的 TONES 表
	  尺寸一律传 px（图标都很小，px 在两端表现一致，不用 rpx 换算）。
	-->
	<!-- #ifdef H5 -->
	<view class="app-icon" :class="'app-icon-' + tone" :style="h5Style"></view>
	<!-- #endif -->
	<!-- #ifndef H5 -->
	<view class="app-icon" :style="mpStyle"></view>
	<!-- #endif -->
</template>

<script>
	import { iconSvg } from '@/utils/icons.js'

	// 小程序端的色值表：必须和 App.vue 里 page{} 的定义保持一致（那边是唯一真源，改一处要改两处）
	const TONES = {
		text: '#23201D',
		muted: '#8C8579',
		accent: '#E2703A',
		inverse: '#FFFFFF',
		danger: '#C0392B'
	}

	// 纯 JS 的 base64（小程序端没有 btoa；输入只有 ASCII，所以不用处理多字节）
	const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
	function toBase64(str) {
		let out = ''
		for (let i = 0; i < str.length; i += 3) {
			const c1 = str.charCodeAt(i)
			const c2 = str.charCodeAt(i + 1)
			const c3 = str.charCodeAt(i + 2)
			out += B64[c1 >> 2]
			out += B64[((c1 & 3) << 4) | (isNaN(c2) ? 0 : c2 >> 4)]
			out += isNaN(c2) ? '=' : B64[((c2 & 15) << 2) | (isNaN(c3) ? 0 : c3 >> 6)]
			out += isNaN(c3) ? '=' : B64[c3 & 63]
		}
		return out
	}

	export default {
		name: 'AppIcon',
		props: {
			// 图标名，见 utils/icons.js 的 ICONS
			name: { type: String, default: 'sparkle' },
			// 边长（px）
			size: { type: [Number, String], default: 20 },
			// H5 走 CSS 变量、小程序走 TONES 表；也可以直接给 color 覆盖
			tone: { type: String, default: 'text' },
			color: { type: String, default: '' }
		},
		computed: {
			px() {
				const n = Number(this.size)
				return (isNaN(n) ? 20 : n) + 'px'
			},
			uri() {
				const c = this.color || TONES[this.tone] || TONES.text
				return 'data:image/svg+xml;base64,' + toBase64(iconSvg(this.name, c))
			},
			h5Style() {
				// mask 只取形状的 alpha，所以里面的颜色随便（用黑色最省字节）
				const u = 'url("data:image/svg+xml;base64,' + toBase64(iconSvg(this.name, '#000000')) + '")'
				return {
					width: this.px,
					height: this.px,
					backgroundColor: 'currentColor',
					WebkitMaskImage: u,
					maskImage: u,
					WebkitMaskRepeat: 'no-repeat',
					maskRepeat: 'no-repeat',
					WebkitMaskSize: 'contain',
					maskSize: 'contain',
					WebkitMaskPosition: 'center',
					maskPosition: 'center'
				}
			},
			mpStyle() {
				return {
					width: this.px,
					height: this.px,
					backgroundColor: 'transparent',
					// 不加引号：base64 字符集里没有括号/空格，小程序端对带引号的 data URI 处理更挑
					backgroundImage: 'url(' + this.uri + ')',
					backgroundRepeat: 'no-repeat',
					backgroundSize: 'contain',
					backgroundPosition: 'center'
				}
			}
		}
	}
</script>

<style>
	.app-icon {
		display: block;
		flex-shrink: 0;
	}

	/* H5：用 color 决定图标颜色（mask + currentColor），跟着父级/主题走 */
	/* #ifdef H5 */
	.app-icon-text { color: var(--text); }
	.app-icon-muted { color: var(--text-2); }
	.app-icon-accent { color: var(--accent); }
	.app-icon-inverse { color: var(--accent-text); }
	.app-icon-danger { color: var(--danger); }
	/* #endif */
</style>
