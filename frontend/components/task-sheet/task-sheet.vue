<template>
	<!-- 「加入我的任务」/「任务设置」面板（#079 加任务 · #083 编辑已有任务）。
	     同一个组件两副面孔：传 task 就是编辑，不传就是从模板加入。 -->
	<view v-if="visible" class="mask" @click="close">
		<view class="sheet" @click.stop>
			<view class="sheet-head">
				<text class="sheet-title">{{ sheetTitle }}</text>
				<text class="sheet-close" hover-class="hover-dim" @click="close">✕</text>
			</view>

			<text v-if="hint" class="sheet-hint">{{ hint }}</text>

			<!-- 编辑模式才改标题（从模板加入时标题跟着模板走） -->
			<view v-if="editing" class="field">
				<text class="field-label">这件事叫什么</text>
				<input
					class="input"
					v-model="title"
					placeholder="比如：睡前把手机放客厅"
					placeholder-class="ph"
					:maxlength="100"
				/>
			</view>

			<view class="field">
				<text class="field-label">频率</text>
				<view class="chips">
					<view
						v-for="f in freqs"
						:key="f.key"
						class="chip"
						:class="{ 'chip-on': freq === f.key }"
						hover-class="hover-dim"
						@click="pickFreq(f.key)"
					>
						<text class="chip-text">{{ f.label }}</text>
					</view>
				</view>
			</view>

			<!-- 配额制才问"一周几次" -->
			<view v-if="freq === 'quota'" class="field">
				<text class="field-label">一周几次</text>
				<view class="chips chips-sm">
					<view
						v-for="n in 7"
						:key="n"
						class="chip chip-num"
						:class="{ 'chip-on': quotaCount === n }"
						hover-class="hover-dim"
						@click="quotaCount = n"
					>
						<text class="chip-text">{{ n }}</text>
					</view>
				</view>
				<!-- #081：配额不是 KPI，别让用户觉得被考核 -->
				<text class="field-tip">选几次都行，节奏你定</text>
			</view>

			<view class="field">
				<text class="field-label">放到哪个时段</text>
				<view class="chips">
					<view
						v-for="s in slots"
						:key="s.key"
						class="chip"
						:class="{ 'chip-on': timeslot === s.key }"
						hover-class="hover-dim"
						@click="timeslot = s.key"
					>
						<text class="chip-text">{{ s.label }}</text>
					</view>
				</view>
			</view>

			<!-- 编辑模式才给目标次数（从模板加入时后端会按配额兜底） -->
			<view v-if="editing" class="field">
				<view class="field-row">
					<text class="field-label field-label-inline">目标次数</text>
					<text class="field-tip field-tip-inline">留空 = 不限次数</text>
				</view>
				<input
					class="input input-num"
					v-model="targetCount"
					type="number"
					placeholder="不限"
					placeholder-class="ph"
				/>
			</view>

			<!-- 编辑模式：归档 / 放回 / 删除（藏在这一层，任务卡上就不用挂一排按钮） -->
			<view v-if="editing" class="manage">
				<text
					v-if="isArchived"
					class="manage-act"
					hover-class="hover-dim"
					@click="setStatus('active')"
				>放回进行中</text>
				<text
					v-else
					class="manage-act"
					hover-class="hover-dim"
					@click="setStatus('archived')"
				>先收起来（归档）</text>
				<text class="manage-act manage-del" hover-class="hover-dim" @click="remove">删除</text>
			</view>

			<view class="sheet-acts">
				<view class="btn-ghost sheet-act" hover-class="hover-dim" @click="close"><text>取消</text></view>
				<view class="btn-accent sheet-act sheet-act-main" hover-class="hover-dim" @click="submit">
					<text>{{ submitting ? (editing ? '保存中…' : '加入中…') : (editing ? '保存' : '加入') }}</text>
				</view>
			</view>
		</view>
	</view>
</template>

<script>
	import { get, post, request, errText } from '@/api/request.js'
	import { requireLogin } from '@/utils/token.js'

	export default {
		name: 'TaskSheet',
		props: {
			visible: { type: Boolean, default: false },
			// pattern：从模板整体加入（POST /tasks/）
			// step   ：把单个步骤拆成一件小事（POST /tasks/from-step/）
			mode: { type: String, default: 'pattern' },
			patternId: { type: [String, Number], default: '' },
			stepId: { type: [String, Number], default: '' },
			// 面板上那句灰字（告诉你正在加什么）
			hint: { type: String, default: '' },
			// 从详情页进来时带当前推荐时段（可以不给）
			defaultTimeslot: { type: String, default: '' },
			// #083：传了 task 就是【编辑已有任务】（改标题/频率/时段/目标次数，还能归档/删除）
			task: { type: Object, default: null }
		},
		emits: ['close', 'done', 'saved'],
		data() {
			return {
				freqs: [
					{ key: 'once', label: '一次性' },
					{ key: 'quota', label: '一周 N 次' },
					{ key: 'habit', label: '每天' }
				],
				// key 与后端 TIMESLOT_ORDER 一致；'' = 不分时段
				slots: [
					{ key: '', label: '不限' },
					{ key: 'morning', label: '早上' },
					{ key: 'noon', label: '中午' },
					{ key: 'afternoon', label: '下午' },
					{ key: 'evening', label: '晚上' },
					{ key: 'night', label: '睡前' }
				],
				freq: 'once',
				quotaCount: 3,
				timeslot: '',
				title: '',
				targetCount: '',
				submitting: false
			}
		},
		computed: {
			editing() {
				return !!(this.task && this.task.id)
			},
			isArchived() {
				return this.editing && this.task.status === 'archived'
			},
			sheetTitle() {
				if (this.editing) return '任务设置'
				return this.mode === 'step' ? '把这一步加成任务' : '加入我的任务'
			}
		},
		watch: {
			// 每次打开：编辑模式回填现有值，加入模式回到默认值
			visible(v) {
				if (!v) return
				this.submitting = false
				if (this.editing) {
					const t = this.task
					this.title = t.title || ''
					this.freq = t.frequency_type || 'once'
					this.quotaCount = t.quota_count || 3
					this.timeslot = t.timeslot || ''
					this.targetCount = t.target_count === null || t.target_count === undefined ? '' : String(t.target_count)
					return
				}
				this.title = ''
				this.freq = 'once'
				this.quotaCount = 3
				this.timeslot = this.defaultTimeslot || ''
				this.targetCount = ''
			}
		},
		methods: {
			close() {
				if (this.submitting) return
				this.$emit('close')
			},
			pickFreq(key) {
				this.freq = key
			},
			payload() {
				const body = { frequency_type: this.freq }
				if (this.freq === 'quota') {
					body.quota_period = 'week'
					body.quota_count = this.quotaCount
				}
				// 编辑时要把"清空"也发出去（'' 会让后端把 quota_* / timeslot 清掉），
				// 加入时只在选了值才带（不选就是"不按时段"）
				if (this.editing) {
					body.timeslot = this.timeslot || ''
				} else if (this.timeslot) {
					body.timeslot = this.timeslot
				}
				return body
			},
			async submit() {
				if (this.submitting) return
				if (this.editing) {
					await this.saveEdit()
					return
				}
				if (this.mode === 'step' && !this.stepId) {
					uni.showToast({ title: '这一步没找到，刷新再试', icon: 'none' })
					return
				}
				if (this.mode === 'pattern' && !this.patternId) {
					uni.showToast({ title: '这张卡没找到，刷新再试', icon: 'none' })
					return
				}
				this.submitting = true
				try {
					// 任务是「我的」数据，必须带身份（没登录 -> H5 跳登录页 / 小程序静默登录）
					await requireLogin()
					const body = this.payload()
					// #084：同一张模板重复加入说不同的话。这个查询和创建【并行】发，
					// 不拖慢主流程；查不到就按第一次加入的文案走。
					let hadSame = null
					if (this.mode === 'pattern') {
						hadSame = get('/tasks/', { status: 'all' }, { silent: true })
							.then((data) => {
								const items = (data && data.items) || []
								return items.some((t) => t.source_pattern && t.source_pattern.id === Number(this.patternId))
							})
							.catch(() => null)
					}
					let task
					if (this.mode === 'step') {
						body.quick_step_id = Number(this.stepId)
						task = await post('/tasks/from-step/', body)
					} else {
						body.pattern_id = Number(this.patternId)
						task = await post('/tasks/', body)
					}
					// #084：成功也分两种 —— 第一次加入 / 又来一张
					let again = null
					if (hadSame) {
						try { again = await hadSame } catch (e) { again = null }
					}
					uni.showToast({
						title: again ? '又加了一张，两张互不影响' : '好，它现在是你的了。今天试一次？',
						icon: 'none'
					})
					this.$emit('done', task)
					this.$emit('close')
				} catch (e) {
					// requireLogin 的"请先登录"不重复弹（它自己已经引导过了）
					if (!(e && e.needLogin)) {
						uni.showToast({ title: errText(e, '加入失败'), icon: 'none' })
					}
				} finally {
					this.submitting = false
				}
			},

			// ===== #083：编辑已有任务 =====
			async saveEdit() {
				const title = (this.title || '').trim()
				if (!title) {
					uni.showToast({ title: '给它留个名字吧', icon: 'none' })
					return
				}
				this.submitting = true
				try {
					await requireLogin()
					const body = this.payload()
					body.title = title
					// 留空 = 不限次数（后端 _to_int('') 会落成 None）
					body.target_count = this.targetCount === '' ? '' : this.targetCount
					const task = await request('/tasks/' + this.task.id + '/', 'PATCH', body)
					uni.showToast({ title: '改好了', icon: 'none' })
					this.$emit('saved', { action: 'update', task })
					this.$emit('close')
				} catch (e) {
					if (!(e && e.needLogin)) uni.showToast({ title: errText(e, '没保存上，再试一次'), icon: 'none' })
				} finally {
					this.submitting = false
				}
			},
			async setStatus(status) {
				if (this.submitting) return
				this.submitting = true
				try {
					await requireLogin()
					const task = await request('/tasks/' + this.task.id + '/', 'PATCH', { status })
					uni.showToast({
						title: status === 'archived' ? '先收起来了，在「归档」里还能找到' : '放回来了',
						icon: 'none'
					})
					this.$emit('saved', { action: status === 'archived' ? 'archive' : 'restore', task })
					this.$emit('close')
				} catch (e) {
					if (!(e && e.needLogin)) uni.showToast({ title: errText(e, '没成功，再点一次'), icon: 'none' })
				} finally {
					this.submitting = false
				}
			},
			remove() {
				if (this.submitting) return
				const that = this
				uni.showModal({
					title: '删了就没了',
					content: '这张任务和它的步骤会一起删掉。只是想先放一边的话，用「先收起来」更稳妥。',
					confirmText: '删除',
					cancelText: '再想想',
					confirmColor: '#c0392b',
					success: async (res) => {
						if (!res.confirm) return
						that.submitting = true
						try {
							await requireLogin()
							await request('/tasks/' + that.task.id + '/', 'DELETE')
							uni.showToast({ title: '删掉了', icon: 'none' })
							that.$emit('saved', { action: 'delete', id: that.task.id })
							that.$emit('close')
						} catch (e) {
							if (!(e && e.needLogin)) uni.showToast({ title: errText(e, '没删掉，再试一次'), icon: 'none' })
						} finally {
							that.submitting = false
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
		z-index: 30;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		background-color: rgba(0, 0, 0, 0.45);
	}

	.sheet {
		box-sizing: border-box;
		width: 100%;
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

	.sheet-hint {
		display: block;
		margin-top: 8rpx;
		font-size: 24rpx;
		color: var(--muted);
		line-height: 1.5;
	}

	.field {
		margin-top: 28rpx;
	}

	/* #083：编辑模式的输入框（标题 / 目标次数） */
	.input {
		box-sizing: border-box;
		width: 100%;
		min-height: 84rpx;
		padding: 16rpx 22rpx;
		border-radius: 16rpx;
		border: 2rpx solid var(--border);
		background-color: var(--surface-2, var(--card));
		font-size: 28rpx;
		color: var(--text);
	}

	.input-num {
		width: 220rpx;
	}

	.ph {
		color: var(--muted);
	}

	.field-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}

	.field-label-inline {
		margin-bottom: 0;
	}

	.field-tip-inline {
		margin-top: 0;
	}

	/* #083：编辑模式底部的"归档 / 删除" —— 破坏性操作离"保存"远一点，别误点 */
	.manage {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: 26rpx;
		padding-top: 22rpx;
		border-top: 2rpx solid var(--border);
	}

	.manage-act {
		min-height: 72rpx;
		padding: 0 4rpx;
		display: flex;
		align-items: center;
		font-size: 25rpx;
		color: var(--muted);
	}

	.manage-del {
		color: #c0392b;
	}

	.field-tip {
		display: block;
		margin-top: 2rpx;
		font-size: 22rpx;
		color: var(--muted);
	}

	.field-label {
		display: block;
		margin-bottom: 14rpx;
		font-size: 24rpx;
		color: var(--text-2);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
	}

	.chip {
		box-sizing: border-box;
		min-height: 80rpx;
		padding: 0 26rpx;
		margin: 0 14rpx 14rpx 0;
		border-radius: 999rpx;
		border: 2rpx solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.chip-num {
		min-width: 80rpx;
		padding: 0;
	}

	.chip-on {
		border-color: var(--accent);
		background-color: var(--accent-soft);
	}

	.chip-text {
		font-size: 26rpx;
		color: var(--text);
	}

	.chip-on .chip-text {
		color: var(--accent);
		font-weight: 600;
	}

	.sheet-acts {
		display: flex;
		margin-top: 20rpx;
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
		margin-left: 20rpx;
	}

	.sheet-act-main {
		flex: 1.6;
	}

	/* 电脑端：面板变成居中的卡片，别横在屏幕最底下 */
	@media (min-width: 768px) {
		.mask {
			align-items: center;
		}
		.sheet {
			width: 520px;
			border-radius: 16px;
			border: 1px solid var(--border);
			padding: 24px 28px;
		}
		.chip {
			min-height: 40px;
			padding: 0 16px;
			margin: 0 10px 10px 0;
			border-width: 1px;
			cursor: pointer;
		}
		.chip-num {
			min-width: 40px;
			padding: 0;
		}
		.chip-text {
			font-size: 13px;
		}
		.sheet-title {
			font-size: 16px;
		}
		.field-tip {
			font-size: 12px;
		}
		.field-label {
			font-size: 13px;
		}
		.input {
			min-height: 42px;
			padding: 10px 12px;
			border-radius: 8px;
			border-width: 1px;
			font-size: 14px;
		}
		.input-num {
			width: 110px;
		}
		.manage {
			margin-top: 18px;
			padding-top: 16px;
			border-top-width: 1px;
		}
		.manage-act {
			min-height: 32px;
			font-size: 13px;
			cursor: pointer;
		}
		.sheet-act {
			height: 44px;
			font-size: 14px;
			border-radius: var(--r-btn);
		}
		.sheet-close {
			cursor: pointer;
		}
	}
</style>
