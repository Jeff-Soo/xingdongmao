// 统一请求层：baseURL + Token 头 + 统一错误处理
// 小程序/App：直连生产域名。真机预览要走电脑上的服务时，改 #ifndef H5 那一行，
// 例如 http://192.168.1.6:8000/api/v1（同时 Django 要 runserver 0.0.0.0:8000 且 ALLOWED_HOSTS 放行）
// #ifdef H5
// 网页版与 API 同域（xingdongmao.com/app/ 配 xingdongmao.com/api/v1），用根绝对路径天然没有跨域。
// 必须是 "/api/v1" 这种根绝对路径：history 路由下页面地址形如 /app/pages/detail/detail?id=23，
// 写相对路径会被解析成 /app/pages/detail/api/v1
const BASE_URL = '/api/v1'
// #endif
// #ifndef H5
const BASE_URL = 'https://xingdongmao.com/api/v1'
// #endif

export { BASE_URL }

// 请求失败抛出的错误有两种形状，页面别各写一套取值逻辑：
//   · 网络层失败（fail 回调）：只有 errMsg，例如 "request:fail url not in domain list"
//   · 后端返回失败（ok:false）：只有 data.error
export function errText(e, fallback) {
	if (!e) return fallback || '未知错误'
	if (e.data && e.data.error) return e.data.error
	if (e.errMsg) return e.errMsg
	if (e.message) return e.message
	return fallback || '未知错误'
}

function authHeader() {
	const token = uni.getStorageSync('token')
	return token ? { Authorization: 'Token ' + token } : {}
}

// options.silent = true 时不弹 toast：首屏失败交给页面自己渲染错误态，避免打开就弹两个提示
export function request(path, method = 'GET', data = {}, options = {}) {
	const silent = !!options.silent
	return new Promise((resolve, reject) => {
		uni.request({
			url: BASE_URL + path,
			method: method,
			data: data,
			timeout: 10000,
			header: Object.assign({ 'Content-Type': 'application/json' }, authHeader()),
			success: (res) => {
				const body = res.data
				// 后端成功统一是 {ok:true, data:...}，这里直接把 data 交给调用方
				if (res.statusCode >= 200 && res.statusCode < 300 && body && body.ok) {
					resolve(body.data)
					return
				}
				// 后端失败统一是 {ok:false, data:{error:'...'}}
				const msg = (body && body.data && body.data.error) || '请求失败(' + res.statusCode + ')'
				// Console 也留一条：真机排查时页面上的一行提示容易看漏，日志才是证据
				console.error('[request error]', method, path, res.statusCode, msg)
				if (res.statusCode === 401) {
					// 登录态失效：清掉本地 token 并给一句人话引导。
					// 这里不弹登录墙，需要身份的操作各自 ensureLogin() 后重试（utils/token.js）
					uni.removeStorageSync('token')
					if (!silent) uni.showToast({ title: '登录状态已失效，请重试', icon: 'none' })
					// 打上 needLogin 标记：页面靠它显示"登录一下"的引导，而不是当成"没连上"。
					// 之前没这个标记，未登录访客会看到"没连上 / 再试一次"，把可解决的问题说成了故障。
					reject(Object.assign({}, body || {}, { needLogin: true }))
					return
				} else if (!silent) {
					uni.showToast({ title: msg, icon: 'none' })
				}
				reject(body || res)
			},
			fail: (err) => {
				// 真机连不上时 Console 以前是空的，只能靠猜，所以原始 errMsg 必须打出来：
				// url not in domain list → 域名白名单；timeout → 超时；ssl hand shake error → 证书
				const detail = (err && err.errMsg) ? err.errMsg : '未知错误'
				console.error('[request fail]', method, path, detail, err)
				if (!silent) uni.showToast({ title: '请求失败：' + detail, icon: 'none', duration: 3000 })
				reject(err)
			}
		})
	})
}

// GET 拼查询串：空值（''/null/undefined）直接丢掉，避免发出 category= 这种无效参数
export const get = (path, params, options) => {
	let qs = ''
	if (params) {
		const parts = Object.keys(params)
			.filter((k) => params[k] !== '' && params[k] !== null && params[k] !== undefined)
			.map((k) => k + '=' + encodeURIComponent(params[k]))
		if (parts.length) qs = '?' + parts.join('&')
	}
	return request(path + qs, 'GET', {}, options)
}

export const post = (path, data, options) => request(path, 'POST', data, options)
