// H5 构建后处理：把 favicon 补进 index.html
// 为什么需要：uni-app 生成的 index.html 不带 <link rel="icon">，浏览器就会去请求
// 站点根目录的 /favicon.ico，而 nginx 没有这个文件 → 控制台一条 404。
// 声明一个存在的图标（static/logo.png 会随包一起发布）就够了。
// 用法：node scripts/postbuild-h5.mjs   （在构建出 dist/build/web 之后跑）
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const dist = join(process.cwd(), 'unpackage', 'dist', 'build', 'web')
const indexFile = join(dist, 'index.html')

if (!existsSync(indexFile)) {
  console.error('没找到 ' + indexFile + '，先构建 H5')
  process.exit(1)
}

let html = readFileSync(indexFile, 'utf8')
const iconTag = '<link rel="icon" type="image/png" href="/app/static/logo.png">'

if (html.includes('rel="icon"')) {
  console.log('已经有 icon 声明，跳过')
  process.exit(0)
}

// 插在 </head> 前，保证在最前面被解析到
html = html.replace('</head>', '  ' + iconTag + '\n</head>')
writeFileSync(indexFile, html, 'utf8')

// 顺手放一份真的 /app/favicon.ico 兜底（万一有页面直接请求它）
const logo = join(dist, 'static', 'logo.png')
if (existsSync(logo)) {
  const { copyFileSync } = await import('node:fs')
  copyFileSync(logo, join(dist, 'favicon.png'))
}

console.log('已插入 ' + iconTag)
