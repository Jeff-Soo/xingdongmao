// 自定义导航栏（navigationStyle: custom）尺寸工具：让页面按钮和微信系统胶囊在同一水平线上。
//
// 原理：`getMenuButtonBoundingClientRect()` 给出的就是胶囊在屏幕上的位置，
// 只要把导航内容区做成"和胶囊上下边完全重合的一条带子"，里面的按钮再垂直居中，
// 就天然和胶囊齐平——不用手调 padding 去凑。
//
// ⚠️ 兜底：微信开发者工具 / 部分平台会把胶囊 rect 返回成全 0。
// 这时绝不能让 0 参与计算（会让内容区高度变 0、padding 变满屏宽），
// 一律退回静态值（胶囊 32×87px、离状态栏 6px、右边距 8px）。

const FALLBACK = {
	capsuleWidth: 87,
	capsuleHeight: 32,
	gap: 6, // 胶囊顶部到状态栏底部的间距
	rightMargin: 8 // 胶囊到屏幕右缘的间距
}

// 右上角按钮与胶囊之间额外留出的呼吸距离（px）：
// 正好贴着胶囊左边界看着发挤（#016 真机反馈），所以统一再让开 3px
const CAPSULE_GAP = 3

function systemInfo() {
	try {
		return uni.getSystemInfoSync() || {}
	} catch (e) {
		return {}
	}
}

// 拿到"可信"的胶囊 rect；全 0 或异常值一律当拿不到，交给调用方走兜底
function capsuleRect() {
	try {
		if (typeof uni.getMenuButtonBoundingClientRect !== 'function') return null
		const rect = uni.getMenuButtonBoundingClientRect()
		if (!rect) return null
		if (!(rect.width > 0) || !(rect.height > 0) || !(rect.top > 0)) return null
		return rect
	} catch (e) {
		return null
	}
}

/**
 * @param {number} [statusBarHeight] 状态栏高度（px），不传则内部自取
 * @param {{reserveRight?: boolean}} [options] reserveRight=false 时不注入 paddingRight
 *        （右上角没有内容的页面用，比如详情页/我的页，否则居中标题会被顶偏）
 * @returns {{
 *   statusBarHeight: number,
 *   capsuleHeight: number,
 *   navTop: number,
 *   rightInset: number,
 *   usingFallback: boolean,
 *   navInnerStyle: object
 * }}
 */
export function getNavBarMetrics(statusBarHeight, options) {
	const reserveRight = !options || options.reserveRight !== false
	const sys = systemInfo()
	const statusBar = Math.max(Number(statusBarHeight) || Number(sys.statusBarHeight) || 20, 0)
	const windowWidth = Number(sys.windowWidth) || 375
	const rect = capsuleRect()

	// 胶囊高度加个上下限，防止个别机型给出离谱值把导航撑爆
	const capsuleHeight = rect ? Math.min(Math.max(rect.height, 24), 60) : FALLBACK.capsuleHeight
	const navTop = rect ? Math.max(rect.top - statusBar, 0) : FALLBACK.gap
	// 右侧留给胶囊的宽度 = 屏幕宽 - 胶囊左边界（含胶囊右边距），再加一点呼吸距离
	const rightInset = (rect ? Math.max(windowWidth - rect.left, 0) : FALLBACK.capsuleWidth + FALLBACK.rightMargin) + CAPSULE_GAP

	// 绑到导航内容区：高度=胶囊高、顶部=胶囊顶，内容再垂直居中就和胶囊天然齐平
	const navInnerStyle = {
		height: capsuleHeight + 'px',
		marginTop: navTop + 'px'
	}
	if (reserveRight) navInnerStyle.paddingRight = rightInset + 'px'

	return {
		statusBarHeight: statusBar,
		capsuleHeight: capsuleHeight,
		navTop: navTop,
		rightInset: rightInset,
		usingFallback: !rect,
		navInnerStyle: navInnerStyle
	}
}
