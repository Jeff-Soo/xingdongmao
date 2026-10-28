// 新手引导的"看过没"标记（#040）。
// 两层引导用两个独立 key 分开记：全屏引导看完不影响蒙层高亮，反之亦然。
// key 带 v1 版本号：以后引导改版就把版本号 +1，老用户会再看一次新版。
export const INTRO_KEY = 'onboarding_intro_v1'
export const TOUR_KEY = 'onboarding_tour_v1'
// #041：创建页的引导（教怎么创建模板），独立于上面两个
export const CREATE_KEY = 'onboarding_create_v1'

const ALL_KEYS = [INTRO_KEY, TOUR_KEY, CREATE_KEY]

// storage 在隐私模式/存储满时可能抛错。这里全部 try 住，并且本次会话内留一份内存标记：
// 读失败就当"没看过"（大不了多弹一次），写失败也要记住，避免"关掉又弹"的死循环。
const session = {}

function has(key) {
	if (session[key]) return true
	try {
		return !!uni.getStorageSync(key)
	} catch (e) {
		return false
	}
}

function mark(key) {
	session[key] = 1
	try {
		uni.setStorageSync(key, 1)
	} catch (e) {
		// 写不进去也无所谓，内存标记已经生效
	}
}

export function isIntroDone() {
	return has(INTRO_KEY)
}

export function isTourDone() {
	return has(TOUR_KEY)
}

export function isCreateDone() {
	return has(CREATE_KEY)
}

export function markIntroDone() {
	mark(INTRO_KEY)
}

export function markTourDone() {
	mark(TOUR_KEY)
}

export function markCreateDone() {
	mark(CREATE_KEY)
}

// 通用版：蒙层高亮组件按传入的 key 落标记（#041 起一个组件服务多个页面）
export function markDone(key) {
	if (key) mark(key)
}

// 「我的」页的"再看教程"：清掉全部引导标记，回到"首次打开"的状态
export function resetOnboarding() {
	ALL_KEYS.forEach((k) => {
		session[k] = 0
		try {
			uni.removeStorageSync(k)
		} catch (e) {
			// 清不掉也能靠内存标记重看这一次
		}
	})
}
