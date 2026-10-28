<template>
	<!-- 步骤编辑面板（#080）：改标题/说明/为什么/时长/要不要倒计时；也能新建和删除。
	     任务里的步骤是"快照"，改这里不影响原模板 —— 面板上明说一句，免得用户以为动了模板。 -->
	<view v-if="visible" class="mask" @click="close">
		<view class="sheet" @click.stop>
			<view class="sheet-head">
				<text class="sheet-title">{{ isNew ? '加一个步骤' : '编辑步骤' }}</text>
				<text class="sheet-close" hover-class="hover-dim" @click="close">✕</text>
			</view>

			<view class="field">
				<text class="field-label">这一步做什么</text>
				<input
					class="input"
					v-model="form.title"
					placeholder="例如：五指分开托住盘底"
					placeholder-class="ph"
					:maxlength="100"
					confirm-type="done"
				/>
			</view>

			<view class="field">
				<text class="field-label">画面文字 / 说明</text>
				<textarea
					class="textarea"
					v-model="form.instruction"
					placeholder="屏幕上给人念的那句话"
					placeholder-class="ph"
					:maxlength="2000"
					auto-height
				/>
			</view>

			<view class="field">
				<text class="field-label">为什么这么做（可留空）</text>
				<textarea
					class="textarea"
					v-model="form.explain"
					placeholder="展开后看到的解释"
					placeholder-class="ph"
					:maxlength="2000"
					auto-height
				/>
			</view>

			<view class="field">
				<text class="field-label">时长</text>
				<view class="chips">
					<view
						v-for="d in durations"
						:key="d.v"
						class="chip"
						:class="{ 'chip-on': Number(form.duration_seconds) === d.v }"
						hover-class="hover-dim"
						@click="pickDuration(d.v)"
					>
						<text class="chip-text">{{ d.label }}</text>
					</view>
				</view>
				<view class="dur-custom">
					<text class="dur-pre">自定义</text>
					<input
						class="input input-dur"
						v-model="form.duration_seconds"
						type="number"
						placeholder="秒"
						placeholder-class="ph"
					/>
					<text class="dur-suf">秒</text>
				</view>
			</view>

			<view class="field field-row">
				<view class="tick-row">
					<text class="field-label">需要倒计时</text>
					<text class="field-hint">关了就是手动推进（时长只当参考）</text>
				</view>
				<view class="switch" :class="{ 'switch-on': form.is_timed }" @click="form.is_timed = !form.is_timed">
					<view class="switch-dot"></view>
				</view>
			</view>

			<view class="sheet-acts">
				<view v-if="!isNew" class="btn-ghost sheet-act sheet-del" hover-class="hover-dim" @click="remove">
					<text>{{ deleting ? '删除中…' : '删除' }}</text>
				</view>
				<view class="btn-ghost sheet-act" hover-class="hover-dim" @click="close"><text>取消</text></view>
				<view class="btn-accent sheet-act sheet-act-main" hover-class="hover-dim" @click="save">
					<text>{{ saving ? '保存中…' : '保存' }}</text>
				</view>
			</view>
		</view>
	</view>
</template>

<script>
	import { post, request, errText } from '@/api/request.js'
	import { requireLogin } from '@/utils/token.js'

	export default {
		name: 'StepSheet',
		props: {
			visible: { type: Boolean, default: false },
			taskId: { type: [String, Number], default: '' },
			// 传 step 就是"编辑"，不传就是"新建"
			step: { type: Object, default: null }
		},
		emits: ['close', 'saved'],
		data() {
			return {
				// 常用时长（秒）：0=不限时；其余按场景给几档
				durations: [
					{ v: 0, label: '不限时' },
					{ v: 30, label: '30 秒' },
					{ v: 60, label: '1 分钟' },
					{ v: 300, label: '5 分钟' },
					{ v: 600, label: '10 分钟' }
				],
				form: { title: '', instruction: '', explain: '', duration_seconds: 0, is_timed: false },
				saving: false,
				deleting: false
			}
		},
		computed: {
			isNew() {
				return !this.step
			}
		},
		watch: {
			// 每次打开用当前步骤回填（不要带上一次的残留）
			visible(v) {
				if (!v) return
				const s = this.step || {}
				this.form = {
					title: s.title || '',
					instruction: s.instruction || '',
					explain: s.explain || '',
					duration_seconds: s.duration_seconds || 0,
					is_timed: !!s.is_timed
				}
				this.saving = false
				this.deleting = false
			}
		},
		methods: {
			close() {
				if (this.saving || this.deleting) return
				this.$emit('close')
			},
			pickDuration(v) {
				this.form.duration_seconds = v
				// 时长 >0 时顺手把倒计时打开（用户点"1 分钟"通常是想起倒计时）；
				// 选"不限时"就关掉，避免出现"不限时还倒计时"
				this.form.is_timed = v > 0 ? true : false
			},
			body() {
				return {
					title: (this.form.title || '').trim(),
					instruction: this.form.instruction || '',
					explain: this.form.explain || '',
					duration_seconds: Math.max(0, Number(this.form.duration_seconds) || 0),
					is_timed: !!this.form.is_timed
				}
			},
			async save() {
				if (this.saving) return
				const body = this.body()
				if (!body.title) {
					uni.showToast({ title: '标题还没写', icon: 'none' })
					return
				}
				this.saving = true
				try {
					await requireLogin()
					let task
					if (this.isNew) {
						task = await post('/tasks/' + this.taskId + '/steps/', body)
					} else {
						task = await request('/tasks/' + this.taskId + '/steps/' + this.step.id + '/', 'PATCH', body)
					}
					uni.showToast({ title: this.isNew ? '加上了' : '改好了', icon: 'success' })
					this.$emit('saved', task)
					this.$emit('close')
				} catch (e) {
					if (!(e && e.needLogin)) uni.showToast({ title: errText(e, '保存失败'), icon: 'none' })
				} finally {
					this.saving = false
				}
			},
			async remove() {
				if (this.deleting || this.isNew) return
				const that = this
				uni.showModal({
					title: '删除这一步？',
					content: '只删这条任务里的步骤，不影响原模板。',
					success: async (res) => {
						if (!res.confirm) return
						that.deleting = true
						try {
							const task = await request('/tasks/' + that.taskId + '/steps/' + that.step.id + '/', 'DELETE')
							uni.showToast({ title: '删掉了', icon: 'none' })
							that.$emit('saved', task)
							that.$emit('close')
						} catch (e) {
							uni.showToast({ title: errText(e, '删除失败'), icon: 'none' })
						} finally {
							that.deleting = false
						}
					}
				})
			}
		}
	}
</script>

<style scoped>
	.mask {
		position: fixed;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		z-index: 40;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		background-color: rgba(0, 0, 0, 0.45);
	}

	.sheet {
		box-sizing: border-box;
		width: 100%;
		max-height: 92vh;
		overflow-y: auto;
		padding: 28rpx 32rpx calc(28rpx + env(safe-area-inset-bottom));
		border-radius: 28rpx 28rpx 0 0;
		background-color: var(--bg);
		border-top: 2rpx solid var(--border);
	}

	.sheet-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.sheet-title {
		font-size: 30rpx;
		font-weight: 600;
		color: var(--text);
	}

	.sheet-close {
		width: 56rpx;
		height: 56rpx;
		line-height: 56rpx;
		text-align: center;
		font-size: 28rpx;
		color: var(--muted);
	}

	.field {
		margin-top: 18rpx;
	}

	.field-label {
		display: block;
		margin-bottom: 12rpx;
		font-size: 24rpx;
		color: var(--text-2);
	}

	.field-hint {
		font-size: 22rpx;
		color: var(--muted);
	}

	.input,
	.textarea {
		box-sizing: border-box;
		width: 100%;
		min-height: 78rpx;
		padding: 14rpx 20rpx;
		border-radius: 16rpx;
		border: 2rpx solid var(--border);
		background-color: var(--surface-2, var(--card));
		font-size: 28rpx;
		color: var(--text);
	}

	.textarea {
		line-height: 1.5;
		min-height: 88rpx;
	}

	.ph {
		color: var(--muted);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
	}

	.chip {
		min-height: 68rpx;
		padding: 0 24rpx;
		margin: 0 14rpx 14rpx 0;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
	}

	.chip-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	.chip-text {
		font-size: 25rpx;
		color: var(--text);
	}

	.chip-on .chip-text {
		color: var(--accent);
		font-weight: 600;
	}

	.dur-custom {
		display: flex;
		align-items: center;
		margin-top: 4rpx;
	}

	.dur-pre,
	.dur-suf {
		font-size: 24rpx;
		color: var(--muted);
	}

	.input-dur {
		width: 180rpx;
		min-height: 68rpx;
		margin: 0 12rpx;
		text-align: center;
	}

	.field-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.tick-row {
		flex: 1;
		min-width: 0;
	}

	.tick-row .field-label {
		margin-bottom: 4rpx;
	}

	/* 开关：纯 CSS，避免引入原生 switch 的样式差异 */
	.switch {
		flex-shrink: 0;
		box-sizing: border-box;
		width: 92rpx;
		height: 52rpx;
		padding: 4rpx;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		background-color: var(--surface-2, var(--card));
		display: flex;
		align-items: center;
	}

	.switch-dot {
		width: 40rpx;
		height: 40rpx;
		border-radius: 50%;
		background-color: var(--muted);
		transition: transform 180ms ease, background-color 180ms ease;
	}

	.switch-on {
		background-color: var(--accent-soft);
		border-color: var(--accent);
	}

	.switch-on .switch-dot {
		transform: translateX(40rpx);
		background-color: var(--accent);
	}

	.sheet-acts {
		display: flex;
		margin-top: 18rpx;
		/* 手机上内容高（三个输入框 + 时长 + 开关），保存键以前会被挤到屏幕外。
		   这里做成"粘在面板底部"，滚动时也够得着。 */
		position: sticky;
		bottom: 0;
		padding: 16rpx 0 4rpx;
		background-color: var(--bg);
	}

	.sheet-act {
		flex: 1;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 28rpx;
	}

	.sheet-act + .sheet-act {
		margin-left: 16rpx;
	}

	.sheet-act-main {
		flex: 1.4;
	}

	.sheet-del {
		flex: 0.8;
		color: var(--danger, #c0392b);
		border-color: rgba(192, 57, 43, 0.35);
	}

	/* 电脑端：居中小卡 */
	@media (min-width: 768px) {
		.mask {
			align-items: center;
		}
		.sheet {
			width: 560px;
			max-height: 84vh;
			border-radius: 16px;
			border: 1px solid var(--border);
			padding: 22px 26px;
		}
		.sheet-title {
			font-size: 16px;
		}
		.field {
			margin-top: 16px;
		}
		.field-label {
			font-size: 13px;
			margin-bottom: 8px;
		}
		.field-hint {
			font-size: 12px;
		}
		.input,
		.textarea {
			min-height: 42px;
			padding: 10px 12px;
			border-radius: 8px;
			border-width: 1px;
			font-size: 14px;
		}
		.textarea {
			min-height: 64px;
		}
		.chip {
			min-height: 38px;
			padding: 0 14px;
			margin: 0 8px 8px 0;
			border-width: 1px;
			cursor: pointer;
		}
		.chip-text {
			font-size: 13px;
		}
		.input-dur {
			width: 90px;
			min-height: 38px;
			margin: 0 8px;
		}
		.dur-pre,
		.dur-suf {
			font-size: 13px;
		}
		.switch {
			width: 46px;
			height: 26px;
			padding: 2px;
			border-width: 1px;
			cursor: pointer;
		}
		.switch-dot {
			width: 20px;
			height: 20px;
		}
		.switch-on .switch-dot {
			transform: translateX(20px);
		}
		.sheet-act {
			height: 44px;
			font-size: 14px;
			border-radius: var(--r-btn);
		}
		.sheet-acts {
			margin-top: 20px;
		}
	}
</style>