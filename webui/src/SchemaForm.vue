<template>
  <div class="schema-form">
    <!-- 后端没返回配置结构时不要留白屏 -->
    <v-empty-state
      v-if="!groups.length"
      icon="lucide:settings"
      title="暂无可配置项"
      text="未从后端读取到配置结构"
    />

    <!-- 一个顶层分组一张卡：卡头硬分段，卡内字段软分段 -->
    <v-card
      v-for="group in groups"
      :key="group.key"
      variant="outlined"
      rounded="card"
      class="group-card"
    >
      <v-card-title class="d-flex align-center ga-3 px-5 py-3">
        <span class="text-subtitle-1 font-weight-medium">{{ group.title }}</span>
        <v-spacer />
        <v-btn
          v-if="group.canReset"
          variant="text"
          size="small"
          prepend-icon="lucide:rotate-ccw"
          @click="resetGroup(group)"
        >
          恢复默认
        </v-btn>
      </v-card-title>
      <v-divider />

      <v-card-text class="px-5 py-2">
        <p v-if="group.subtitle" class="group-desc text-caption text-medium-emphasis">
          {{ group.subtitle }}
        </p>

        <template v-for="row in group.rows" :key="rowKey(row)">
          <!-- 二级子分区（组内嵌套 object）：小标题软分段 -->
          <div
            v-if="row.kind === 'subsection'"
            class="subsection-title text-subtitle-2 font-weight-medium"
          >
            {{ row.title }}
          </div>

          <div v-else class="field-row" :class="{ 'is-block': row.block }">
            <div class="field-main">
              <div class="field-label text-body-2">{{ row.label }}</div>
              <div v-if="row.hint" class="field-hint text-caption text-medium-emphasis">
                {{ row.hint }}
              </div>
            </div>

            <div class="field-control">
              <!-- JSON 映射字段：行式键值编辑器，替代手写 JSON -->
              <div v-if="isKvMap(row.meta, row.path)" class="kv-editor">
                <div
                  v-for="(kv, index) in kvRowsOf(row.path)"
                  :key="index"
                  class="kv-row d-flex align-center ga-2 mb-2"
                >
                  <v-text-field
                    class="kv-key"
                    :model-value="kv.key"
                    placeholder="键"
                    density="compact"
                    variant="outlined"
                    hide-details
                    @update:model-value="(v: unknown) => { kv.key = String(v ?? ''); kvSync(row.path) }"
                  />
                  <v-text-field
                    class="kv-value"
                    :model-value="kv.value"
                    placeholder="值"
                    density="compact"
                    variant="outlined"
                    hide-details
                    @update:model-value="(v: unknown) => { kv.value = String(v ?? ''); kvSync(row.path) }"
                  />
                  <v-btn
                    icon="lucide:trash-2"
                    variant="text"
                    size="small"
                    aria-label="删除该行"
                    @click="kvRemove(row.path, index)"
                  />
                </div>
                <v-btn variant="text" size="small" prepend-icon="lucide:plus" @click="kvAdd(row.path)">
                  添加一项
                </v-btn>
              </div>

              <v-switch
                v-else-if="row.meta.type === 'bool'"
                :model-value="getIn(row.path) === true"
                @update:model-value="(v: unknown) => setIn(row.path, v === true)"
              />

              <v-text-field
                v-else-if="row.meta.type === 'int' || row.meta.type === 'float'"
                class="control-number"
                type="number"
                :step="row.meta.type === 'int' ? 1 : 0.1"
                :model-value="numberInput(getIn(row.path))"
                @update:model-value="(v: unknown) => onNumberInput(row.path, v, row.meta.type === 'int')"
              />

              <v-combobox
                v-else-if="row.meta.type === 'list'"
                :model-value="asList(getIn(row.path))"
                multiple
                chips
                closable-chips
                placeholder="输入后回车添加"
                @update:model-value="(v: unknown) => setIn(row.path, asList(v))"
              />

              <v-textarea
                v-else-if="row.meta.type === 'text'"
                :model-value="asString(getIn(row.path))"
                rows="3"
                auto-grow
                max-rows="8"
                @update:model-value="(v: unknown) => setIn(row.path, asString(v))"
              />

              <v-text-field
                v-else
                class="control-text"
                :model-value="asString(getIn(row.path))"
                @update:model-value="(v: unknown) => setIn(row.path, asString(v))"
              />
            </div>
          </div>
        </template>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SchemaMeta } from './schema'

interface FieldRow {
  kind: 'field'
  path: string[]
  label: string
  hint?: string
  meta: SchemaMeta
  block: boolean
}

interface SubsectionRow {
  kind: 'subsection'
  title: string
}

type CardRow = FieldRow | SubsectionRow

interface Group {
  key: string
  title: string
  subtitle?: string
  canReset: boolean
  rows: CardRow[]
}

const props = defineProps<{
  schema: Record<string, SchemaMeta>
  modelValue?: Record<string, unknown>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, unknown>): void
}>()

/** 去掉 schema description 里的「[分组] 」前缀，UI 不需要重复标签 */
function cleanLabel(text: string | undefined): string {
  return (text ?? '').replace(/^\[[^\]]+\]\s*/, '')
}

function buildField(prefix: string[], key: string, meta: SchemaMeta): FieldRow {
  const type = meta.type ?? 'string'
  // 宽控件独占整行：多行文本、标签编辑器、键值编辑器
  const block = type === 'text' || type === 'list' || meta.editor_language === 'json'
  return {
    kind: 'field',
    path: [...prefix, key],
    label: cleanLabel(meta.description) || key,
    hint: meta.hint,
    meta,
    block,
  }
}

function rowKey(row: CardRow): string {
  return row.kind === 'field' ? row.path.join('.') : row.title
}

// 顶层叶子归入「常规」组置顶；顶层 object 各成一卡；二级 object 成为卡内子分区
const groups = computed<Group[]>(() => {
  const schema = props.schema || {}
  const rootRows: CardRow[] = []
  const sections: Group[] = []

  for (const [key, meta] of Object.entries(schema)) {
    if (!meta || typeof meta !== 'object') continue
    if (meta.type === 'object') {
      const rows: CardRow[] = []
      for (const [subKey, subMeta] of Object.entries(meta.items || {})) {
        if (subMeta?.type === 'object') {
          rows.push({ kind: 'subsection', title: cleanLabel(subMeta.description) || subKey })
          for (const [k, m] of Object.entries(subMeta.items || {})) {
            rows.push(buildField([key, subKey], k, m))
          }
        } else {
          rows.push(buildField([key], subKey, subMeta))
        }
      }
      sections.push({
        key,
        title: cleanLabel(meta.description) || key,
        subtitle: meta.hint,
        canReset: false,
        rows,
      })
    } else {
      rootRows.push(buildField([], key, meta))
    }
  }

  const result: Group[] = []
  if (rootRows.length) {
    // 「常规」组不提供恢复默认（顶层字段无统一默认语义）
    result.push({ key: '__root__', title: '常规', canReset: false, rows: rootRows })
  }
  for (const section of sections) {
    section.canReset = section.rows.some((r) => r.kind === 'field' && r.meta.default !== undefined)
    result.push(section)
  }
  return result
})

/** 恢复默认：组内所有带 default 的字段重置为 schema 默认值，改动后由父级 dirty 检测浮出保存按钮 */
function resetGroup(group: Group) {
  for (const row of group.rows) {
    if (row.kind === 'field' && row.meta.default !== undefined) {
      setIn(row.path, row.meta.default)
    }
  }
}

function getIn(path: string[]): unknown {
  let cur: unknown = props.modelValue
  for (const k of path) {
    if (cur && typeof cur === 'object') cur = (cur as Record<string, unknown>)[k]
    else return undefined
  }
  return cur
}

function setIn(path: string[], value: unknown) {
  const root: Record<string, unknown> = { ...(props.modelValue || {}) }
  let cur = root
  for (let i = 0; i < path.length - 1; i++) {
    const next = cur[path[i]]
    cur[path[i]] = next && typeof next === 'object' ? { ...(next as Record<string, unknown>) } : {}
    cur = cur[path[i]] as Record<string, unknown>
  }
  cur[path[path.length - 1]] = value
  emit('update:modelValue', root)
}

function asString(v: unknown): string {
  return typeof v === 'string' ? v : ''
}

function asList(v: unknown): string[] {
  return Array.isArray(v) ? v.map(String) : []
}

function numberInput(v: unknown): string | number {
  return typeof v === 'number' && Number.isFinite(v) ? v : ''
}

function onNumberInput(path: string[], raw: unknown, isInt: boolean) {
  const text = typeof raw === 'number' ? String(raw) : String(raw ?? '').trim()
  if (!text) {
    setIn(path, null)
    return
  }
  const parsed = Number(text)
  if (!Number.isFinite(parsed)) return
  setIn(path, isInt ? Math.trunc(parsed) : parsed)
}

// ---------- JSON 映射字段：行式键值编辑器替代手写 JSON ----------

interface KvRow {
  key: string
  value: string
}

const kvDrafts = new Map<string, { source: string; rows: KvRow[] }>()

function parseKvObject(v: unknown): Record<string, string> | null {
  if (typeof v !== 'string') return null
  try {
    const parsed = JSON.parse(v) as unknown
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, string>)
      : null
  } catch {
    return null
  }
}

/** schema 标记 editor_language=json 且当前值为合法 JSON 对象字符串时启用；解析失败回退文本框 */
function isKvMap(meta: SchemaMeta, path: string[]): boolean {
  return meta.editor_language === 'json' && parseKvObject(getIn(path)) !== null
}

function kvRowsOf(path: string[]): KvRow[] {
  const id = path.join('.')
  const source = asString(getIn(path))
  let draft = kvDrafts.get(id)
  if (!draft || draft.source !== source) {
    draft = {
      source,
      rows: Object.entries(parseKvObject(getIn(path)) || {}).map(([key, value]) => ({
        key,
        value: String(value),
      })),
    }
    kvDrafts.set(id, draft)
  }
  return draft.rows
}

function kvWrite(path: string[], rows: KvRow[]) {
  const obj: Record<string, string> = {}
  for (const row of rows) {
    if (row.key.trim()) obj[row.key.trim()] = String(row.value ?? '')
  }
  const source = JSON.stringify(obj)
  kvDrafts.set(path.join('.'), { source, rows })
  setIn(path, source)
}

// 行内输入直接 mutate 行对象（不触发 update:value），输入变化后手动序列化写回
function kvSync(path: string[]) {
  const draft = kvDrafts.get(path.join('.'))
  if (draft) kvWrite(path, draft.rows)
}

function kvAdd(path: string[]) {
  kvWrite(path, [...kvRowsOf(path), { key: '', value: '' }])
}

function kvRemove(path: string[], index: number) {
  kvWrite(
    path,
    kvRowsOf(path).filter((_, i) => i !== index),
  )
}
</script>

<style scoped>
.schema-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 分组说明：卡体顶部小字 */
.group-desc {
  margin: 0 0 4px;
  line-height: 1.6;
}

/* ---------- 软分段：卡内字段行，标签/hint 居左，控件右贴 ---------- */

.field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 10px 0;
}

.field-row + .field-row,
.subsection-title + .field-row {
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.field-main {
  flex: 1;
  min-width: 0;
}

.field-label {
  line-height: 1.45;
}

.field-hint {
  margin-top: 3px;
  line-height: 1.55;
}

/* 控件列：不伸展、右贴；具体控件各自定宽 */
.field-control {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.control-number {
  width: 160px;
}

.control-text {
  width: 280px;
}

/* ---------- 宽控件（多行文本 / 标签 / 键值）：独占整行 ---------- */

.field-row.is-block {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}

.field-row.is-block .field-control {
  width: 100%;
}

.kv-editor {
  width: 100%;
}

.kv-key {
  flex: 1.4;
}

.kv-value {
  flex: 1;
}

/* ---------- 二级子分区标题 ---------- */

.subsection-title {
  padding: 14px 0 4px;
}

/* ---------- 窄屏：标签与控件改为上下排 ---------- */

@media (max-width: 640px) {
  .field-row {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
  }

  .field-control {
    width: 100%;
  }

  .control-number,
  .control-text {
    width: 100%;
  }
}
</style>
