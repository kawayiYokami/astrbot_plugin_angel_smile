<template>
  <!-- 左侧：表情分组导航（240px，可折叠到 56px） -->
  <v-navigation-drawer
    :rail="rail"
    permanent
    width="240"
    rail-width="56"
    class="meme-drawer"
    color="transparent"
  >
    <div class="d-flex flex-column h-100">
      <div class="drawer-head pa-2" :class="rail ? 'd-flex flex-column align-center ga-2' : 'd-flex align-center ga-2'">
        <v-btn
          :icon="rail ? 'lucide:panel-left-open' : 'lucide:panel-left-close'"
          variant="text"
          size="small"
          :aria-label="rail ? '展开侧栏' : '收起侧栏'"
          @click="toggleRail"
        />
        <template v-if="!rail">
          <span class="text-subtitle-1 font-weight-medium flex-grow-1 text-truncate">表情库</span>
          <v-btn color="primary" variant="flat" size="small" prepend-icon="lucide:plus" @click="openUpload">
            新增
          </v-btn>
        </template>
        <v-btn
          v-else
          color="primary"
          variant="flat"
          size="small"
          icon="lucide:plus"
          aria-label="新增表情"
          @click="openUpload"
        />
      </div>

      <v-divider />

      <v-list class="flex-grow-1 overflow-y-auto py-2" nav bg-color="transparent">
        <v-list-item
          v-for="m in memes"
          :key="m.name"
          :active="viewMode === 'memes' && selectedName === m.name"
          color="primary"
          @click="selectMeme(m.name)"
        >
          <v-list-item-title class="d-flex align-center ga-2">
            <!-- 折叠态用名称首字代替图标，列表里不再放图片类 icon -->
            <span v-if="rail" class="text-truncate text-center flex-grow-1">{{ m.name.slice(0, 1) }}</span>
            <template v-else>
              <span class="text-truncate flex-grow-1">{{ m.name }}</span>
              <v-chip size="x-small" variant="tonal" color="primary">{{ m.variants.length }}</v-chip>
            </template>
          </v-list-item-title>
          <v-tooltip v-if="rail" activator="parent" location="end">{{ m.name }}</v-tooltip>
        </v-list-item>

        <div v-if="!memes.length && !loadingMemes && !rail">
          <v-empty-state
            icon="lucide:sticker"
            title="暂无表情"
            text="点上方「新增」上传第一个表情"
            class="pa-2"
          />
        </div>
      </v-list>

      <v-divider />

      <v-list class="py-2" nav bg-color="transparent">
        <v-list-item :active="viewMode === 'settings'" color="primary" @click="openSettings">
          <template #prepend>
            <v-icon icon="lucide:settings" />
          </template>
          <v-list-item-title v-if="!rail">插件设置</v-list-item-title>
          <v-tooltip v-if="rail" activator="parent" location="end">插件设置</v-tooltip>
        </v-list-item>
      </v-list>
    </div>
  </v-navigation-drawer>

  <!-- 右侧：选中分组的变体 / 插件设置 -->
  <v-main class="meme-main">
    <div class="d-flex flex-column h-100">
      <!-- ========== 插件设置 ========== -->
      <template v-if="viewMode === 'settings'">
        <header class="view-head px-6 py-4">
          <div class="min-w-0">
            <h2 class="text-h4 mb-1">插件设置</h2>
            <p class="text-body-2 text-medium-emphasis mb-0">
              与 AstrBot 原生插件配置页共用同一份数据，保存后即时生效，无需重启
            </p>
          </div>
        </header>
        <v-divider />

        <div class="flex-grow-1 overflow-y-auto">
          <div class="settings-body">
            <SchemaForm
              v-if="settingsLoaded"
              v-model:model-value="settingsValues"
              :schema="settingsSchema"
            />
            <div v-else class="d-flex justify-center py-12">
              <v-progress-circular indeterminate />
            </div>
          </div>
        </div>

        <v-btn
          v-if="settingsDirty"
          class="save-fab"
          color="primary"
          variant="flat"
          rounded="pill"
          size="large"
          elevation="6"
          prepend-icon="lucide:save"
          :loading="savingSettings"
          @click="saveSettings"
        >
          保存更改
        </v-btn>
      </template>

      <!-- ========== 表情库 ========== -->
      <template v-else-if="!selectedName">
        <v-empty-state
          icon="lucide:sticker"
          title="还没有选中表情"
          text="从左侧选择一个表情分组查看变体"
          class="h-100"
        />
      </template>

      <template v-else>
        <header class="view-head px-6 py-4">
          <div class="d-flex align-center ga-3 min-w-0">
            <h2 class="text-h4 mb-0 text-truncate">{{ selectedName }}</h2>
            <v-chip size="small" variant="tonal" color="primary">{{ variantCount }} 个变体</v-chip>
          </div>

          <div class="view-actions d-flex align-center ga-2">
            <template v-if="selecting">
              <span class="text-caption text-medium-emphasis">已选 {{ selectedVariants.size }} 项</span>
              <v-btn variant="text" @click="exitSelect">取消</v-btn>
              <v-btn
                color="error"
                variant="flat"
                :disabled="selectedVariants.size === 0"
                @click="batchDelete"
              >
                删除选中
              </v-btn>
            </template>
            <template v-else>
              <v-btn variant="text" prepend-icon="lucide:trash-2" @click="enterSelect">批量删除</v-btn>
              <v-btn variant="text" prepend-icon="lucide:pencil" @click="openRename(selectedName)">
                重命名
              </v-btn>
              <v-btn variant="text" color="error" @click="confirmDeleteMeme(selectedName)">
                删除分组
              </v-btn>
              <v-btn color="primary" variant="flat" prepend-icon="lucide:upload" @click="openVariantUpload">
                添加变体
              </v-btn>
            </template>
          </div>
        </header>
        <v-divider />

        <div class="flex-grow-1 overflow-y-auto">
          <div v-if="visibleVariants.length" class="variant-grid">
            <v-card
              v-for="v in visibleVariants"
              :key="v.relative"
              variant="outlined"
              rounded="card"
              class="variant-card"
              :class="{ 'is-selected': isSelected(v.relative) }"
              @click="onCardClick(v)"
            >
              <div class="variant-preview">
                <img :src="imageUrl(v.relative)" :alt="v.file" loading="lazy" />
              </div>
              <v-divider />
              <div class="variant-info px-3 py-2 d-flex align-center ga-2">
                <span class="text-caption text-medium-emphasis text-truncate flex-grow-1" :title="v.file">
                  {{ v.file }}
                </span>
                <v-icon
                  v-if="selecting"
                  :icon="isSelected(v.relative) ? 'lucide:circle-check' : 'lucide:circle'"
                  :color="isSelected(v.relative) ? 'primary' : undefined"
                  size="20"
                />
                <v-btn
                  v-else
                  icon="lucide:trash-2"
                  variant="text"
                  size="x-small"
                  class="variant-del"
                  aria-label="删除该变体"
                  @click.stop="confirmDeleteVariant(v)"
                />
              </div>
            </v-card>
          </div>

          <div
            v-else-if="loadingImages"
            class="d-flex justify-center py-12"
          >
            <v-progress-circular indeterminate />
          </div>

          <v-empty-state
            v-else
            icon="lucide:images"
            title="该分组没有变体"
            class="py-16"
          />
        </div>
      </template>
    </div>
  </v-main>

  <!-- ========== 图片预览 ========== -->
  <v-dialog v-model="showPreview" max-width="760">
    <v-card rounded="card">
      <div class="preview-stage">
        <img :src="preview.src" :alt="preview.alt" />
      </div>
      <v-card-actions class="px-4 pb-3">
        <span class="text-caption text-medium-emphasis flex-grow-1 text-truncate">{{ preview.alt }}</span>
        <v-btn variant="text" @click="showPreview = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- ========== 新增表情 ========== -->
  <v-dialog v-model="showUpload" max-width="440" persistent>
    <v-card rounded="card">
      <v-card-title class="text-h6">新增表情</v-card-title>
      <v-card-text>
        <v-text-field
          v-model="uploadForm.emotion"
          label="表情名（贴纸名）"
          placeholder="如：坏笑"
          class="mb-4"
        />
        <v-file-input
          v-model="uploadFileModel"
          label="图片文件"
          accept="image/*"
          prepend-icon=""
          prepend-inner-icon="lucide:image"
          show-size
          @update:model-value="onUploadChange"
        />
        <div v-if="uploadForm.previewUrl" class="upload-preview mt-3">
          <img :src="uploadForm.previewUrl" alt="预览" />
        </div>
      </v-card-text>
      <v-card-actions class="px-4 pb-3">
        <v-spacer />
        <v-btn variant="text" @click="closeUpload">取消</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="uploading"
          :disabled="!uploadForm.emotion.trim() || !uploadFile"
          @click="submitUpload"
        >
          上传
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- ========== 添加变体 ========== -->
  <v-dialog v-model="showVariantUpload" max-width="440" persistent>
    <v-card rounded="card">
      <v-card-title class="text-h6">添加变体：{{ selectedName ?? '' }}</v-card-title>
      <v-card-text>
        <v-file-input
          v-model="variantFileModel"
          label="图片文件"
          accept="image/*"
          prepend-icon=""
          prepend-inner-icon="lucide:image"
          show-size
          @update:model-value="onVariantUploadChange"
        />
        <div v-if="variantForm.previewUrl" class="upload-preview mt-3">
          <img :src="variantForm.previewUrl" alt="预览" />
        </div>
      </v-card-text>
      <v-card-actions class="px-4 pb-3">
        <v-spacer />
        <v-btn variant="text" @click="closeVariantUpload">取消</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="uploading"
          :disabled="!variantForm.file"
          @click="submitVariantUpload"
        >
          上传
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- ========== 重命名 ========== -->
  <v-dialog v-model="showRename" max-width="440" persistent>
    <v-card rounded="card">
      <v-card-title class="text-h6">重命名表情</v-card-title>
      <v-card-text>
        <v-text-field
          :model-value="renameForm.oldName"
          label="原名称"
          readonly
          variant="outlined"
          class="mb-4"
        />
        <v-text-field
          v-model="renameForm.newName"
          label="新名称"
          placeholder="输入新名字"
          @keyup.enter="submitRename"
        />
      </v-card-text>
      <v-card-actions class="px-4 pb-3">
        <v-spacer />
        <v-btn variant="text" @click="showRename = false">取消</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="renaming"
          :disabled="!renameForm.newName.trim() || renameForm.newName.trim() === renameForm.oldName"
          @click="submitRename"
        >
          确定
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useBridge } from './composables/useBridge'
import { toast } from './composables/useToast'
import { confirmDialog } from './composables/useConfirm'
import SchemaForm from './SchemaForm.vue'
import type { SchemaMeta } from './schema'

interface MemeVariant {
  file: string
  relative: string
}

interface MemeItem {
  name: string
  variants: MemeVariant[]
}

const { apiGet, apiPost, upload } = useBridge()

/** 表情名 → 路径安全的 token（UTF-8 → base64url） */
function emotionToken(name: string): string {
  const bytes = new TextEncoder().encode(name)
  let bin = ''
  bytes.forEach((b) => {
    bin += String.fromCharCode(b)
  })
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

// ---------- 侧栏折叠 ----------

const rail = ref(false)
// 用户手动折叠/展开后，不再让宽度变化覆盖他的选择
let railTouched = false
// 用 ResizeObserver 而不是只读一次 matchMedia：iframe 的视口宽度在文档
// 首次布局前后会变，只在 onMounted 读一次会把 240px 侧栏误判成窄屏。
let widthObserver: ResizeObserver | null = null

function toggleRail() {
  railTouched = true
  rail.value = !rail.value
}

onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return
  widthObserver = new ResizeObserver((entries) => {
    if (railTouched) return
    const width = entries[0]?.contentRect.width ?? window.innerWidth
    rail.value = width <= 900
  })
  widthObserver.observe(document.documentElement)
})
onUnmounted(() => {
  widthObserver?.disconnect()
  widthObserver = null
})

// ---------- 视图切换（表情库 / 插件设置） ----------

type ViewMode = 'memes' | 'settings'
const viewMode = ref<ViewMode>('memes')

const settingsSchema = ref<Record<string, SchemaMeta>>({})
const settingsValues = ref<Record<string, unknown>>({})
const settingsLoaded = ref(false)
const savingSettings = ref(false)
// 草稿基线：与当前值不一致即有变更，浮出保存按钮
const settingsBaseline = ref('')
const settingsDirty = computed(
  () => settingsLoaded.value && JSON.stringify(settingsValues.value) !== settingsBaseline.value,
)

function openSettings() {
  viewMode.value = 'settings'
  if (!settingsLoaded.value) void loadPluginConfig()
}

async function loadPluginConfig() {
  try {
    const data = await apiGet<{
      schema: Record<string, SchemaMeta>
      values: Record<string, unknown>
    }>('plugin_config')
    settingsSchema.value = data?.schema || {}
    settingsValues.value = data?.values || {}
    settingsBaseline.value = JSON.stringify(settingsValues.value)
    settingsLoaded.value = true
  } catch (e) {
    toast.error(`加载插件设置失败: ${(e as Error).message}`)
  }
}

async function saveSettings() {
  savingSettings.value = true
  try {
    await apiPost('plugin_config/save', { values: settingsValues.value })
    settingsBaseline.value = JSON.stringify(settingsValues.value)
    toast.success('已保存并即时生效')
  } catch (e) {
    toast.error(`保存失败: ${(e as Error).message}`)
  } finally {
    savingSettings.value = false
  }
}

// ---------- 表情列表 ----------

const memes = ref<MemeItem[]>([])
const selectedName = ref<string | null>(null)
const loadingMemes = ref(false)

const currentMeme = computed(() => memes.value.find((m) => m.name === selectedName.value) ?? null)
const currentVariants = computed(() => currentMeme.value?.variants ?? [])
const variantCount = computed(() => currentVariants.value.length)

function selectMeme(name: string) {
  if (selecting.value) exitSelect()
  viewMode.value = 'memes'
  selectedName.value = name
}

async function loadMemes() {
  loadingMemes.value = true
  try {
    const data = await apiGet<MemeItem[]>('memes')
    memes.value = data ?? []
    if (selectedName.value && !memes.value.some((m) => m.name === selectedName.value)) {
      selectedName.value = null
    }
  } catch (e) {
    toast.error(`加载失败: ${(e as Error).message}`)
  } finally {
    loadingMemes.value = false
  }
}

// ---------- 图片：走 b64 接口拿 data URL ----------
// 原生 <img src="/api/plug/..."> 不带 Authorization header，Secure cookie 在 HTTP 下
// 不发送会 401 裂图，所以统一走 bridge apiGet（宿主 axios 带 token）取 base64。

const imageSrcMap = reactive<Record<string, string>>({})
const readySet = reactive(new Set<string>())
const loadingImages = ref(false)

function imageUrl(relative: string): string {
  return imageSrcMap[relative] ?? ''
}

// 图片就绪才让卡片入列；网格按 currentVariants 原顺序过滤，顺序天然稳定
const visibleVariants = computed(() => currentVariants.value.filter((v) => readySet.has(v.relative)))

const IMAGE_CONCURRENCY = 16
let loadGeneration = 0

async function loadVariantImages(memeName: string | null) {
  const gen = ++loadGeneration
  readySet.clear()
  if (!memeName) {
    loadingImages.value = false
    return
  }
  const meme = memes.value.find((m) => m.name === memeName)
  if (!meme) {
    loadingImages.value = false
    return
  }

  // 已有缓存的立即可见，其余并发加载（限流 16）
  for (const v of meme.variants) {
    if (imageSrcMap[v.relative]) readySet.add(v.relative)
  }
  const pending = meme.variants.filter((v) => !imageSrcMap[v.relative])
  if (!pending.length) {
    loadingImages.value = false
    return
  }

  loadingImages.value = true
  let cursor = 0
  const worker = async () => {
    while (cursor < pending.length) {
      // 快速切换分组时丢弃过期任务
      if (gen !== loadGeneration) return
      const v = pending[cursor++]
      try {
        const data = await apiGet<{ data_url?: string }>('memes/image/b64', { path: v.relative })
        if (gen !== loadGeneration) return
        if (data?.data_url) {
          imageSrcMap[v.relative] = data.data_url
          readySet.add(v.relative)
        }
      } catch (e) {
        console.warn(`[MemeManage] 图片加载失败: ${v.relative}`, e)
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(IMAGE_CONCURRENCY, pending.length) }, () => worker()),
  )
  if (gen === loadGeneration) loadingImages.value = false
}

watch(selectedName, (name) => {
  void loadVariantImages(name)
})

// ---------- 图片预览 ----------

const showPreview = ref(false)
const preview = reactive({ src: '', alt: '' })

function openPreview(v: MemeVariant) {
  preview.src = imageSrcMap[v.relative] ?? ''
  preview.alt = v.file
  if (!preview.src) return
  showPreview.value = true
}

// ---------- 批量删除（多选） ----------

const selecting = ref(false)
const selectedVariants = reactive(new Set<string>())

function enterSelect() {
  selectedVariants.clear()
  selecting.value = true
}

function exitSelect() {
  selecting.value = false
  selectedVariants.clear()
}

function toggleSelect(rel: string) {
  if (selectedVariants.has(rel)) selectedVariants.delete(rel)
  else selectedVariants.add(rel)
}

function isSelected(rel: string): boolean {
  return selectedVariants.has(rel)
}

function onCardClick(v: MemeVariant) {
  if (selecting.value) toggleSelect(v.relative)
  else openPreview(v)
}

async function batchDelete() {
  if (!selectedName.value || selectedVariants.size === 0) return
  const count = selectedVariants.size
  const ok = await confirmDialog({
    title: '批量删除变体',
    text: `确定删除选中的 ${count} 个变体？删完若该分组没有变体，分组会一并移除。`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await apiPost('memes/variant/batch_delete', {
      name: selectedName.value,
      relatives: [...selectedVariants],
    })
    toast.success(`已删除 ${count} 个变体`)
    exitSelect()
    await loadMemes()
  } catch (e) {
    toast.error(`删除失败: ${(e as Error).message}`)
  }
}

async function confirmDeleteVariant(v: MemeVariant) {
  if (!selectedName.value) return
  const ok = await confirmDialog({
    title: '删除变体',
    text: `确定删除变体「${v.file}」？删完若该分组没有变体，分组会一并移除。`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await apiPost('memes/variant/delete', { name: selectedName.value, relative: v.relative })
    toast.success('已删除该变体')
    delete imageSrcMap[v.relative]
    readySet.delete(v.relative)
    await loadMemes()
    await loadVariantImages(selectedName.value)
  } catch (e) {
    toast.error(`删除失败: ${(e as Error).message}`)
  }
}

// ---------- 上传（新增表情） ----------

const showUpload = ref(false)
const uploading = ref(false)
const uploadFile = ref<File | null>(null)
const uploadFileModel = ref<File | File[] | null>(null)
const uploadForm = reactive({ emotion: '', previewUrl: '' })

function pickSingleFile(value: File | File[] | null | undefined): File | null {
  if (!value) return null
  return Array.isArray(value) ? (value[0] ?? null) : value
}

function revokePreview(target: { previewUrl: string }) {
  if (target.previewUrl) URL.revokeObjectURL(target.previewUrl)
  target.previewUrl = ''
}

function openUpload() {
  uploadForm.emotion = ''
  revokePreview(uploadForm)
  uploadFile.value = null
  uploadFileModel.value = null
  showUpload.value = true
}

function closeUpload() {
  showUpload.value = false
  revokePreview(uploadForm)
  uploadFile.value = null
  uploadFileModel.value = null
}

function onUploadChange(value: File | File[] | null) {
  const file = pickSingleFile(value)
  uploadFile.value = file
  revokePreview(uploadForm)
  if (file) uploadForm.previewUrl = URL.createObjectURL(file)
}

async function submitUpload() {
  if (!uploadFile.value) return
  const emotion = uploadForm.emotion.trim()
  if (!emotion) {
    toast.warning('先给表情起个名字')
    return
  }
  uploading.value = true
  try {
    const result = await upload<{ saved?: boolean; duplicate?: boolean }>(
      `memes/upload/${emotionToken(emotion)}`,
      uploadFile.value,
    )
    if (result?.duplicate) toast.warning('这个表情包已经收过了')
    else toast.success('上传成功')
    closeUpload()
    await loadMemes()
    selectedName.value = emotion
  } catch (e) {
    toast.error(`上传失败: ${(e as Error).message}`)
  } finally {
    uploading.value = false
  }
}

// ---------- 上传（添加变体） ----------

const showVariantUpload = ref(false)
const variantFileModel = ref<File | File[] | null>(null)
const variantForm = reactive<{ file: File | null; previewUrl: string }>({
  file: null,
  previewUrl: '',
})

function openVariantUpload() {
  variantForm.file = null
  variantFileModel.value = null
  revokePreview(variantForm)
  showVariantUpload.value = true
}

function closeVariantUpload() {
  showVariantUpload.value = false
  revokePreview(variantForm)
  variantForm.file = null
  variantFileModel.value = null
}

function onVariantUploadChange(value: File | File[] | null) {
  const file = pickSingleFile(value)
  variantForm.file = file
  revokePreview(variantForm)
  if (file) variantForm.previewUrl = URL.createObjectURL(file)
}

async function submitVariantUpload() {
  if (!variantForm.file || !selectedName.value) return
  const name = selectedName.value
  uploading.value = true
  try {
    const result = await upload<{ saved?: boolean; duplicate?: boolean }>(
      `memes/upload/${emotionToken(name)}`,
      variantForm.file,
    )
    if (result?.duplicate) toast.warning('这个表情包已经收过了')
    else toast.success('变体已添加')
    closeVariantUpload()
    await loadMemes()
    await loadVariantImages(name)
  } catch (e) {
    toast.error(`上传失败: ${(e as Error).message}`)
  } finally {
    uploading.value = false
  }
}

// ---------- 重命名 ----------

const showRename = ref(false)
const renaming = ref(false)
const renameForm = reactive({ oldName: '', newName: '' })

function openRename(name: string | null) {
  if (!name) return
  const meme = memes.value.find((m) => m.name === name)
  if (!meme) return
  renameForm.oldName = meme.name
  renameForm.newName = meme.name
  showRename.value = true
}

async function submitRename() {
  const next = renameForm.newName.trim()
  if (!next || next === renameForm.oldName) return
  renaming.value = true
  try {
    await apiPost('memes/rename', { old_name: renameForm.oldName, new_name: next })
    toast.success('重命名成功')
    showRename.value = false
    if (selectedName.value === renameForm.oldName) selectedName.value = next
    await loadMemes()
    await loadVariantImages(next)
  } catch (e) {
    toast.error(`重命名失败: ${(e as Error).message}`)
  } finally {
    renaming.value = false
  }
}

// ---------- 删除分组 ----------

async function confirmDeleteMeme(name: string | null) {
  if (!name) return
  const ok = await confirmDialog({
    title: '删除分组',
    text: `确定删除「${name}」及其全部 ${variantCount.value} 个变体？`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await apiPost('memes/delete', { name })
    toast.success(`已删除 ${name}`)
    if (selectedName.value === name) selectedName.value = null
    await loadMemes()
  } catch (e) {
    toast.error(`删除失败: ${(e as Error).message}`)
  }
}

onMounted(async () => {
  await loadMemes()
  if (memes.value.length && !selectedName.value) {
    selectMeme(memes.value[0].name)
  }
})
</script>

<style scoped>
.meme-drawer {
  border-inline-end: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  /* drawer 默认吃 surface；侧栏必须跟页面同 background，卡片才配浮出 */
  background-color: rgb(var(--v-theme-background)) !important;
}
/* v-list 默认吃 surface；侧栏里的列表必须透明，否则菜单区比空白亮一档 */
.v-application .meme-drawer .v-list {
  background-color: transparent !important;
}

/* 折叠到 56px 时列表项只剩名称首字，需要居中 */
.meme-drawer.v-navigation-drawer--rail :deep(.v-list-item) {
  padding-inline: 0;
  justify-content: center;
}

.meme-main {
  height: 100vh;
  overflow: hidden;
}

/* 标题与操作区：窄宽度下换行，不让按钮被挤出可点区域 */
.view-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px 20px;
  flex-wrap: wrap;
}

.view-head > .view-actions {
  flex-wrap: wrap;
}

.settings-body {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 24px 120px;
}

.save-fab {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 6;
}

.variant-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  padding: 20px 24px 32px;
}

.variant-card {
  cursor: pointer;
  /* 圆角直接裁切图片，不留白边 */
  overflow: hidden;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.variant-card:hover {
  border-color: rgb(var(--v-theme-primary));
}

.variant-card.is-selected {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.06);
}

.variant-preview {
  aspect-ratio: 1;
  display: flex;
  overflow: hidden;
}

/* 图片铺满整个预览区，多出的部分由卡片圆角裁掉 */
.variant-preview img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.variant-del {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}

.variant-card:hover .variant-del {
  color: rgb(var(--v-theme-error));
}

.preview-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  max-height: 70vh;
  overflow: auto;
  background: rgba(var(--v-theme-on-surface), 0.03);
}

.preview-stage img {
  max-width: 100%;
  max-height: 66vh;
  object-fit: contain;
}

.upload-preview {
  display: flex;
  justify-content: center;
}

.upload-preview img {
  max-width: 100%;
  max-height: 180px;
  object-fit: contain;
  border-radius: 12px;
}
</style>
