// Token 存取 + 登录。
// 定位是"应急零门槛"：浏览不需要身份，只有评分/收藏/笔记/创建这类操作才要 token，
// 所以这里不做登录墙，只提供 requireLogin() 给需要的操作自己调用。
//
// 两套账号并存、互不打通（#027）：
//   小程序：wx.login 拿 code → /auth/wx-login/ → 微信用户（openid 有值、没有可登录的密码）
//   网页版：邮箱 + 密码 → /auth/login/ 或 /auth/register/ → 网页用户（openid 为空）
import { post } from '@/api/request.js'

const TOKEN_KEY = 'token'
const EMAIL_KEY = 'email' // 网页版邮箱登录后存下来，「我的」页要显示

// ⚠️ 上线前必须改成 false（只改这一处）。
// true = 用固定 email 调 /auth/dev-login/ 换 token（开发用）；后端 ENABLE_DEV_LOGIN 跟着 DEBUG 走，
// 生产 DEBUG=False 时该接口返回 403，这里就会登录失败。部署检查清单见后端 DEPLOY.md 第 5 节。
const USE_DEV_LOGIN = false
// 开发期身份：同一个 email 永远落到同一个用户，方便反复联调
const DEV_EMAIL = 'dev@xingdongmao.local'

export function getToken() {
	return uni.getStorageSync(TOKEN_KEY) || ''
}

export function setToken(token) {
	if (token) {
		uni.setStorageSync(TOKEN_KEY, token)
	} else {
		uni.removeStorageSync(TOKEN_KEY)
	}
}

export function clearToken() {
	uni.removeStorageSync(TOKEN_KEY)
	uni.removeStorageSync(EMAIL_KEY)
}

// 被动判断登录态：只读、不跳转。页面首屏判断用它，免得一进页面就被弹去登录页。
export function isLoggedIn() {
	return !!getToken()
}

export function getEmail() {
	return uni.getStorageSync(EMAIL_KEY) || ''
}

// ===== 网页版邮箱密码登录 =====
// silent：错误交给登录页自己渲染（否则 toast 和页面里的红字会重复提示）
export function loginWithEmail(email, password) {
	return post('/auth/login/', { email: email, password: password }, { silent: true }).then(saveToken)
}

export function registerWithEmail(email, password) {
	return post('/auth/register/', { email: email, password: password }, { silent: true }).then(saveToken)
}

// 引导登录失败时 reject 的错误带 needLogin=true：
// 调用方据此提示"请先登录"，而不是笼统的"操作失败"
function needLoginError() {
	const e = new Error('先登录一下就好')
	e.needLogin = true
	return e
}

// 需要身份的操作统一走这里：已登录直接过；没登录就引导登录
//   H5：跳登录页（登录完返回上一页，用户再点一次动作）+ reject(needLogin)
//   小程序：静默 wx.login，用户无感
export function requireLogin() {
	const token = getToken()
	if (token) return Promise.resolve(token)
	// #ifdef H5
	uni.navigateTo({ url: '/pages/login/login' })
	return Promise.reject(needLoginError())
	// #endif
	// #ifndef H5
	return USE_DEV_LOGIN ? devLogin() : wxLogin()
	// #endif
}

// 兼容旧调用点（create/detail/execute/mine 里的 ensureLogin 语义不变）
export function ensureLogin() {
	return requireLogin()
}

// ===== 忘记密码（#028）=====
// 申请重置：后端无论邮箱是否存在都回同一句话（不泄露注册情况），前端照着显示就行
export function requestPasswordReset(email) {
	return post('/auth/forgot/', { email: email }, { silent: true })
}

// 用邮件里的一次性 token 设新密码
export function resetPassword(token, password) {
	return post('/auth/reset/', { token: token, password: password }, { silent: true })
}

function saveToken(data) {
	const token = (data && data.token) || ''
	if (!token) throw new Error('登录失败：服务端没有返回 token')
	setToken(token)
	if (data && data.email) uni.setStorageSync(EMAIL_KEY, data.email)
	return token
}

// 开发期过渡：无 openid，用固定 email 换 token
function devLogin() {
	return post('/auth/dev-login/', { email: DEV_EMAIL }).then(saveToken)
}

// 小程序正式路径：wx.login 拿 code → 后端换 openid → 返回 token
function wxLogin() {
	return new Promise((resolve, reject) => {
		uni.login({
			provider: 'weixin',
			success: (res) => {
				if (!res || !res.code) {
					reject(new Error('wx.login 没有返回 code'))
					return
				}
				post('/auth/wx-login/', { code: res.code })
					.then((d) => resolve(saveToken(d)))
					.catch(reject)
			},
			fail: reject
		})
	})
}
