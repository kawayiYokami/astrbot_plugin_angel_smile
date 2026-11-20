/**
 * 从本地 @iconify-json/lucide 抽取页面用到的图标，生成离线集合。
 *
 * 为什么不在运行时走 Iconify API：插件页跑在 WebUI 的 iframe 里，
 * 外网请求可能被 CSP 或网络挡住，图标会整片空白。这里把需要的几十个
 * 图标在构建期固化成内联数据，产物自带、零网络请求。
 *
 * 用法：node scripts/gen-icons.mjs
 */
import { createRequire } from 'node:module'
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const here = dirname(fileURLToPath(import.meta.url))
const outFile = resolve(here, '../src/icons/lucide-offline.ts')

// 界面用到的图标 + Vuetify 内部别名用到的图标
const NEEDED = [
  // 界面
  'plus',
  'upload',
  'trash-2',
  'pencil',
  'settings',
  'sticker',
  'sun',
  'moon',
  'panel-left-close',
  'panel-left-open',
  'save',
  'rotate-ccw',
  'image',
  'file-image',
  'images',
  'search',
  'folder-open',
  'circle',
  'circle-check',
  'circle-alert',
  'triangle-alert',
  'info',
  // Vuetify 内部（dropdown / clearable / checkbox / alert 等）
  'x',
  'check',
  'chevron-down',
  'chevron-up',
  'chevron-left',
  'chevron-right',
  'minus',
  'square',
  'paperclip',
  'menu',
  'x-circle',
]

const collection = require('@iconify-json/lucide/icons.json')

function bodyOf(name) {
  const icon = collection.icons[name]
  if (icon) return icon.body
  const alias = collection.aliases?.[name]
  if (alias) {
    const parent = collection.icons[alias.parent]
    if (parent) return parent.body
  }
  return null
}

const icons = {}
const missing = []
for (const name of NEEDED) {
  const body = bodyOf(name)
  if (body) icons[name] = { body }
  else missing.push(name)
}

if (missing.length) {
  console.error(`[gen-icons] 以下图标在 @iconify-json/lucide 中不存在：${missing.join(', ')}`)
  process.exit(1)
}

const payload = {
  prefix: 'lucide',
  width: collection.width || 24,
  height: collection.height || 24,
  icons,
}

const banner = `// 本文件由 scripts/gen-icons.mjs 生成，请勿手工编辑。\n// 仅包含页面实际使用的 ${Object.keys(icons).length} 个 lucide 图标，用于离线渲染。\n`

mkdirSync(dirname(outFile), { recursive: true })
writeFileSync(
  outFile,
  `${banner}\nexport const lucideOffline = ${JSON.stringify(payload)} as const\n`,
  'utf8',
)

console.log(`[gen-icons] 已写出 ${Object.keys(icons).length} 个图标 -> ${outFile}`)
