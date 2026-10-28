// 全局功能开关（改完要重新编译：小程序走「发行 → 微信小程序」，网页版走「发行 → 网站/Web」）
//
// ===== 平台判定（必须定义在最前面：下面的开关要用它）=====
// #ifdef H5
export const IS_H5 = true
// #endif
// #ifndef H5
export const IS_H5 = false
// #endif

// ===== UGC 开关（#029）=====
// 是否放开"用户自建内容"（创建 / 导入 / 编辑模板）及其全部入口。
// 现状：**网页端恢复，小程序端保持隐藏**——小程序主体还是个人主体，一放开就会被
// 【社交-笔记】类目驳回；网页端不受微信类目限制，可以正常用。
// 小程序主体升级成个体户后，把这里改成 `export const ENABLE_UGC = true` 即可两端一起恢复。
//
// 受这个开关控制的入口：
//   · 首页「＋ 创建」悬浮按钮              pages/index/index.vue
//   · 「我的」页「创建模板」+「我创建的」tab   pages/mine/mine.vue
//   · 详情页「编辑 / 发布」按钮（作者可见）    pages/detail/detail.vue
//   · 详情页作者显示（关着时固定显示「官方」）  pages/detail/detail.vue
//   · 创建页本体 pages/create/create.vue（文件一直在包里，关着时只是没有任何入口）
export const ENABLE_UGC = IS_H5 ? true : false

// 能否登录：小程序走 wx.login，网页版走邮箱密码（#027 已接上），所以两边都能登录。
// 各页面的收藏 / 笔记 / 评分 用 canLogin 控制显隐——现在是全开的。
export const CAN_LOGIN = true
