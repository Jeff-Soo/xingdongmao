// 执行引擎适配器：QuickStep 和后续的 PlanBlock 都归一成 step_data，执行页只认 step_data。
// 双模式（总览/护送）与语音播报已砍掉，统一走滚轴式执行页，这里只做结构与默认值收敛。

export const SOURCE_QUICK = 'quick'
export const SOURCE_PLAN = 'plan'

export function toStepData(step, sourceType = SOURCE_QUICK) {
	const s = step || {}
	return {
		order: s.order || 0,
		title: s.title || '',
		instruction: s.instruction || '',
		explain: s.explain || '',
		duration_seconds: s.duration_seconds || 0,
		is_timed: !!s.is_timed,
		source_type: sourceType
	}
}

export function toStepList(steps, sourceType = SOURCE_QUICK) {
	return (steps || []).map((s) => toStepData(s, sourceType))
}

// 秒 → 人话，列表 / 详情 / 执行页共用，避免各页各写一套
export function formatDuration(seconds) {
	const s = Number(seconds) || 0
	if (s <= 0) return '不限时'
	if (s < 60) return s + ' 秒'
	if (s < 3600) return Math.round(s / 60) + ' 分钟'
	const h = Math.floor(s / 3600)
	const m = Math.round((s % 3600) / 60)
	return m ? h + ' 小时 ' + m + ' 分' : h + ' 小时'
}
