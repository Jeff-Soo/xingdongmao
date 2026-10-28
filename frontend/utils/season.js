/**
 * #085 Step 2：季档 & 季节推荐（接口先留位）
 *
 * 为什么单独一个文件：季节的边界、"这一季算哪年"这种判断很容易写错（冬天跨年），
 * 集中在一处，季档时间轴和以后的"季节推荐"共用一套，不会两处算出不同结果。
 */

// 北半球按自然月粗分（比节气好理解，用户也不会纠结 5 月 5 日算春还是夏）
export const SEASONS = [
	{ key: 'spring', label: '春', months: '3–5 月', monthList: [3, 4, 5] },
	{ key: 'summer', label: '夏', months: '6–8 月', monthList: [6, 7, 8] },
	{ key: 'autumn', label: '秋', months: '9–11 月', monthList: [9, 10, 11] },
	{ key: 'winter', label: '冬', months: '12–2 月', monthList: [12, 1, 2] }
]

const pad = (n) => (n < 10 ? '0' + n : '' + n)

export function dateKey(d) {
	const x = d instanceof Date ? d : new Date(d)
	return x.getFullYear() + '-' + pad(x.getMonth() + 1) + '-' + pad(x.getDate())
}

export function parseDateKey(s) {
	if (!s) return null
	const p = String(s).slice(0, 10).split('-')
	if (p.length !== 3) return null
	const d = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]))
	return isNaN(d.getTime()) ? null : d
}

export function addDays(d, n) {
	const x = new Date(d.getTime())
	x.setDate(x.getDate() + n)
	return x
}

/** 这一季的 key：12 月归"当年冬"，1–2 月归"去年冬"（否则 1 月和 12 月会被算成两季） */
export function seasonKeyOf(d) {
	const m = d.getMonth() + 1
	if (m >= 3 && m <= 5) return 'spring'
	if (m >= 6 && m <= 8) return 'summer'
	if (m >= 9 && m <= 11) return 'autumn'
	return 'winter'
}

/** 这一季的"年份标签"（冬天的年份取它开始的那一年） */
export function seasonYearOf(d) {
	const m = d.getMonth() + 1
	return m <= 2 ? d.getFullYear() - 1 : d.getFullYear()
}

/** 返回 { key, label, months, year, start: Date, end: Date }（end 含当天） */
export function seasonOf(d) {
	const key = seasonKeyOf(d)
	const year = seasonYearOf(d)
	const meta = SEASONS.find((s) => s.key === key) || SEASONS[0]
	let start
	let end
	if (key === 'winter') {
		start = new Date(year, 11, 1)
		end = new Date(year + 1, 1, 28)
	} else {
		const first = meta.monthList[0]
		start = new Date(year, first - 1, 1)
		// 下个月 0 号 = 本月最后一天
		end = new Date(year, first + 2, 0)
	}
	return { key, label: meta.label, months: meta.months, year, start, end }
}

/** 从某一季往后/往前推 n 季 */
export function shiftSeason(d, n) {
	const s = seasonOf(d)
	// 用"季首月 1 号"当锚点，按 3 个月滚动，避免跨年时月份算错
	const anchorMonth = s.key === 'winter' ? 11 : SEASONS.find((x) => x.key === s.key).monthList[0] - 1
	const anchor = new Date(s.year, anchorMonth, 1)
	anchor.setMonth(anchor.getMonth() + n * 3)
	return seasonOf(anchor)
}

export function seasonLabel(s) {
	return s.label + '季'
}

export function seasonFullLabel(s) {
	return s.year + ' 年 ' + s.label + '季'
}

/**
 * 季节推荐：接口先留位。
 * 后端做好后（比如 GET /api/v1/quick/season-suggestions/?season=autumn&year=2026）
 * 只要把这个函数改成一个 get()，页面那边不用动。
 * 现在返回空数组 = 页面不显示"当季推荐"这一块。
 */
export async function fetchSeasonSuggestions(seasonKey, year) {
	// TODO(#087+): return await get('/quick/season-suggestions/', { season: seasonKey, year })
	void seasonKey
	void year
	return []
}
