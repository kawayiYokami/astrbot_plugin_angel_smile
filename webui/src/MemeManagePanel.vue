<template>
  <n-layout class="layout" has-sider :style="cssVars">
    <!-- 左侧：表情分组导航 -->
    <n-layout-sider bordered width="260">
      <div class="sidebar-inner">
        <div class="sidebar-header">
          <div class="brand">表情库</div>
          <n-button size="small" type="primary" @click="openUpload">
            <template #icon><Icon icon="lucide:plus" /></template>
            新增
          </n-button>
        </div>
        <n-scrollbar class="sidebar-scroll">
          <n-menu
            :value="selectedName ?? undefined"
            :options="menuOptions"
            @update:value="selectMeme"
          />
        </n-scrollbar>
        <div class="sidebar-footer">
          <span class="footer-text">{{ memes.length }} 组 · {{ totalVariants }} 个变体</span>
        </div>
      </div>
    </n-layout-sider>

    <!-- 右侧：选中分组的变体 -->
    <n-layout-content class="content">
      <div v-if="!selectedName" class="empty-state">
        <n-empty description="从左侧选择一个表情分组查看变体" size="large">
          <template #icon><Icon icon="lucide:sticker" class="empty-icon" /></template>
        </n-empty>
      </div>

      <template v-else>
        <div class="content-inner">
          <div class="content-header">
            <div class="content-title">
              <h2>{{ selectedName }}</h2>
              <n-tag size="small" round :bordered="false">{{ variantCount }} 个变体</n-tag>
            </div>
            <div class="content-actions" v-if="selecting">
              <span class="select-count">已选 {{ selectedVariants.size }} 项</span>
              <n-button size="small" @click="exitSelect">取消</n-button>
              <n-popconfirm
                :disabled="selectedVariants.size === 0"
                @positive-click="batchDelete"
                :positive-button-props="{ type: 'error' }"
                positive-text="删除"
                negative-text="取消"
              >
                <template #trigger>
                  <n-button
                    size="small"
                    type="error"
                    :disabled="selectedVariants.size === 0"
                  >
                    删除选中
                  </n-button>
                </template>
                确定删除选中的 {{ selectedVariants.size }} 个变体？
              </n-popconfirm>
            </div>
            <div class="content-actions" v-else>
              <n-button size="small" @click="enterSelect">
                <template #icon><Icon icon="lucide:trash-2" /></template>
                批量删除
              </n-button>
              <n-button size="small" @click="openRename(selectedName)">
                <template #icon><Icon icon="lucide:pencil" /></template>
                重命名
              </n-button>
              <n-popconfirm
                v-if="variantCount === 0"
                @positive-click="deleteMeme(selectedName)"
                :positive-button-props="{ type: 'error' }"
                positive-text="删除"
                negative-text="取消"
              >
                <template #trigger>
                  <n-button size="small" type="error">删除分组</n-button>
                </template>
                确定删除「{{ selectedName }}」？
              </n-popconfirm>
              <n-tooltip v-else>
                <template #trigger>
                  <n-button size="small" type="error" disabled>删除分组</n-button>
                </template>
                请先删除全部变体
              </n-tooltip>
              <n-button size="small" type="primary" @click="openVariantUpload">
                <template #icon><Icon icon="lucide:upload" /></template>
                添加变体
              </n-button>
            </div>
          </div>

          <n-scrollbar class="content-scroll">
            <div class="variant-grid">
              <div
                v-for="v in currentVariants"
                :key="v.relative"
                class="variant-card"
                :class="{ 'is-selected': isSelected(v.relative) }"
                @click="onCardClick(v.relative)"
              >
                <div class="variant-preview">
                  <n-image
                    :src="imageUrl(v.relative)"
                    object-fit="contain"
                    :fallback-src="fallbackImage"
                    :preview-disabled="selecting"
                  >
                    <template #placeholder>
                      <div class="variant-preview-loading">加载中…</div>
                    </template>
                  </n-image>
                </div>
                <div class="variant-info">
                  <n-checkbox
                    v-if="selecting"
                    size="small"
                    class="variant-checkbox"
                    :checked="isSelected(v.relative)"
                    @click.stop
                    @update:checked="toggleSelect(v.relative)"
                  />
                  <span class="variant-name" :title="v.file">{{ v.file }}</span>
                </div>
              </div>
              <n-empty
                v-if="currentVariants.length === 0"
                description="该分组没有变体"
                class="grid-empty"
              />
            </div>
          </n-scrollbar>
        </div>
      </template>
    </n-layout-content>

    <!-- 新增表情弹窗 -->
    <n-modal v-model:show="showUpload" preset="card" title="新增表情" style="width: 420px">
      <n-form label-placement="top">
        <n-form-item label="表情名（贴纸名）">
          <n-input v-model:value="uploadForm.emotion" placeholder="如：坏笑" />
        </n-form-item>
        <n-form-item label="图片文件">
          <n-upload
            :default-upload="false"
            accept="image/*"
            :show-file-list="true"
            :max="1"
            @change="onUploadChange"
          >
            <n-button>
              <template #icon><Icon icon="lucide:upload" /></template>
              选择图片
            </n-button>
          </n-upload>
        </n-form-item>
        <n-form-item v-if="uploadForm.previewUrl" label="预览">
          <img :src="uploadForm.previewUrl" class="upload-preview" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="showUpload = false">取消</n-button>
          <n-button
            type="primary"
            :loading="uploading"
            :disabled="!uploadForm.emotion || !uploadFile"
            @click="submitUpload"
          >
            上传
          </n-button>
        </div>
      </template>
    </n-modal>

    <!-- 添加变体弹窗 -->
    <n-modal
      v-model:show="showVariantUpload"
      preset="card"
      :title="`添加变体：${selectedName ?? ''}`"
      style="width: 420px"
    >
      <n-form label-placement="top">
        <n-form-item label="图片文件">
          <n-upload
            :default-upload="false"
            accept="image/*"
            :show-file-list="true"
            :max="1"
            @change="onVariantUploadChange"
          >
            <n-button>
              <template #icon><Icon icon="lucide:upload" /></template>
              选择图片
            </n-button>
          </n-upload>
        </n-form-item>
        <n-form-item v-if="variantForm.previewUrl" label="预览">
          <img :src="variantForm.previewUrl" class="upload-preview" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="showVariantUpload = false">取消</n-button>
          <n-button
            type="primary"
            :loading="uploading"
            :disabled="!variantForm.file"
            @click="submitVariantUpload"
          >
            上传
          </n-button>
        </div>
      </template>
    </n-modal>

    <!-- 重命名弹窗 -->
    <n-modal v-model:show="showRename" preset="card" title="重命名表情" style="width: 420px">
      <n-form label-placement="top">
        <n-form-item label="原名称">
          <n-input :value="renameForm.oldName" disabled />
        </n-form-item>
        <n-form-item label="新名称">
          <n-input v-model:value="renameForm.newName" placeholder="输入新名字" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="showRename = false">取消</n-button>
          <n-button
            type="primary"
            :loading="renaming"
            :disabled="!renameForm.newName || renameForm.newName === renameForm.oldName"
            @click="submitRename"
          >
            确定
          </n-button>
        </div>
      </template>
    </n-modal>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NCheckbox,
  NEmpty,
  NForm,
  NFormItem,
  NImage,
  NInput,
  NLayout,
  NLayoutContent,
  NLayoutSider,
  NMenu,
  NModal,
  NPopconfirm,
  NScrollbar,
  NTag,
  NTooltip,
  NUpload,
  useMessage,
  useThemeVars,
} from 'naive-ui'
import { Icon } from '@iconify/vue'
import { useBridge } from './composables/useBridge'

interface MemeVariant {
  file: string
  relative: string
}

interface MemeItem {
  name: string
  variants: MemeVariant[]
}

const PLUGIN_NAME = 'astrbot_plugin_angel_smile'

const message = useMessage()
const themeVars = useThemeVars()
const { apiGet, apiPost } = useBridge()

// Naive UI 的主题变量只挂在组件自己的根节点上，自定义类里用到的
// var(--n-*) 需要在这里显式注入到根容器，否则解析失败。
const cssVars = computed(() => {
  const v = themeVars.value
  return {
    '--n-body-color': v.bodyColor,
    '--n-card-color': v.cardColor,
    '--n-color-1': v.bodyColor,
    '--n-color-2': v.cardColor,
    '--n-text-color-1': v.textColor1,
    '--n-text-color-2': v.textColor2,
    '--n-text-color-3': v.textColor3,
    '--n-divider-color': v.dividerColor,
    '--n-border-color': v.borderColor,
    '--n-primary-color': v.primaryColor,
    '--n-primary-color-1': v.primaryColorSuppl,
    '--n-primary-color-soft': `${v.primaryColor}1f`,
  }
})

const fallbackImage =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'>" +
      "<rect width='100%' height='100%' fill='#2f3337'/>" +
      "<text x='50%' y='50%' fill='#80858c' font-size='14' text-anchor='middle' dominant-baseline='middle'>图片缺失</text>" +
      '</svg>',
  )

const memes = ref<MemeItem[]>([])
const selectedName = ref<string | null>(null)

const showUpload = ref(false)
const showVariantUpload = ref(false)
const uploading = ref(false)
const uploadFile = ref<File | null>(null)
const uploadForm = reactive({ emotion: '', previewUrl: '' })
const variantForm = reactive<{ file: File | null; previewUrl: string }>({
  file: null,
  previewUrl: '',
})

const showRename = ref(false)
const renaming = ref(false)
const renameForm = reactive({ oldName: '', newName: '' })

const currentMeme = computed(() =>
  memes.value.find((m) => m.name === selectedName.value) ?? null,
)

const currentVariants = computed(() => currentMeme.value?.variants ?? [])

const variantCount = computed(() => currentVariants.value.length)

const totalVariants = computed(() =>
  memes.value.reduce((sum, m) => sum + m.variants.length, 0),
)

// 左侧导航：NMenu，名称 + 变体数标签
const menuOptions = computed(() =>
  memes.value.map((m) => ({
    key: m.name,
    icon: () => h(Icon, { icon: 'lucide:sticker' }),
    label: () =>
      h('div', { class: 'menu-label' }, [
        h('span', { class: 'menu-name' }, m.name),
        h(
          NTag,
          { size: 'small', round: true, bordered: false },
          { default: () => `${m.variants.length}` },
        ),
      ]),
  })),
)

function selectMeme(name: string) {
  if (selecting.value) exitSelect()
  selectedName.value = name
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
  if (selectedVariants.has(rel)) {
    selectedVariants.delete(rel)
  } else {
    selectedVariants.add(rel)
  }
}

function isSelected(rel: string): boolean {
  return selectedVariants.has(rel)
}

function onCardClick(rel: string) {
  if (selecting.value) toggleSelect(rel)
}

async function batchDelete() {
  if (!selectedName.value || selectedVariants.size === 0) return
  try {
    await apiPost('memes/variant/batch_delete', {
      name: selectedName.value,
      relatives: [...selectedVariants],
    })
    message.success(`已删除 ${selectedVariants.size} 个变体`)
    exitSelect()
    await loadMemes()
  } catch (e) {
    message.error(`删除失败: ${(e as Error).message}`)
  }
}

// 变体图片 data URL 缓存：relative -> data:image/...;base64,...
// 原生 <img src="/api/plug/..."> 不带 Authorization header，Secure cookie 在
// HTTP 下不发送会 401 裂图；改走 bridge apiGet（宿主 axios 带 token）获取 base64。
const imageSrcMap = reactive<Record<string, string>>({})

function imageUrl(relative: string): string {
  return imageSrcMap[relative] ?? ''
}

async function loadVariantImages(memeName: string | null) {
  if (!memeName) return
  const meme = memes.value.find((m) => m.name === memeName)
  if (!meme) return
  for (const v of meme.variants) {
    if (imageSrcMap[v.relative]) continue
    try {
      const data = await apiGet<{ data_url?: string }>('memes/image/b64', {
        path: v.relative,
      })
      if (data?.data_url) {
        imageSrcMap[v.relative] = data.data_url
      }
    } catch (e) {
      console.warn(`[MemeManage] 图片加载失败: ${v.relative}`, e)
    }
  }
}

watch(selectedName, (name) => {
  void loadVariantImages(name)
})

async function loadMemes() {
  try {
    const data = await apiGet<MemeItem[]>('memes')
    memes.value = data ?? []
    if (selectedName.value && !memes.value.some((m) => m.name === selectedName.value)) {
      selectedName.value = null
    }
  } catch (e) {
    message.error(`加载失败: ${(e as Error).message}`)
  }
}

// ---------- 上传（新增表情） ----------

function openUpload() {
  uploadForm.emotion = ''
  uploadForm.previewUrl = ''
  uploadFile.value = null
  showUpload.value = true
}

function onUploadChange(options: { file: { file?: File | null } }) {
  const f = options.file.file
  uploadFile.value = f ?? null
  if (f) {
    uploadForm.previewUrl = URL.createObjectURL(f)
  }
}

async function submitUpload() {
  if (!uploadFile.value) return
  uploading.value = true
  try {
    const form = new FormData()
    form.append('emotion', uploadForm.emotion.trim())
    form.append('file', uploadFile.value)
    const resp = await fetch(`/api/plug/${PLUGIN_NAME}/memes/upload`, {
      method: 'POST',
      body: form,
    })
    const json = await resp.json()
    if (json?.status === 'error') {
      throw new Error(json.message || '上传失败')
    }
    message.success(json?.message || '上传成功')
    showUpload.value = false
    await loadMemes()
    selectedName.value = uploadForm.emotion.trim()
  } catch (e) {
    message.error(`上传失败: ${(e as Error).message}`)
  } finally {
    uploading.value = false
  }
}

// ---------- 上传（添加变体） ----------

function openVariantUpload() {
  variantForm.file = null
  variantForm.previewUrl = ''
  showVariantUpload.value = true
}

function onVariantUploadChange(options: { file: { file?: File | null } }) {
  const f = options.file.file
  variantForm.file = f ?? null
  if (f) {
    variantForm.previewUrl = URL.createObjectURL(f)
  }
}

async function submitVariantUpload() {
  if (!variantForm.file || !selectedName.value) return
  uploading.value = true
  try {
    const form = new FormData()
    form.append('emotion', selectedName.value)
    form.append('file', variantForm.file)
    const resp = await fetch(`/api/plug/${PLUGIN_NAME}/memes/upload`, {
      method: 'POST',
      body: form,
    })
    const json = await resp.json()
    if (json?.status === 'error') {
      throw new Error(json.message || '上传失败')
    }
    message.success(json?.message || '上传成功')
    showVariantUpload.value = false
    await loadMemes()
  } catch (e) {
    message.error(`上传失败: ${(e as Error).message}`)
  } finally {
    uploading.value = false
  }
}

// ---------- 重命名 ----------

function openRename(name: string) {
  const meme = memes.value.find((m) => m.name === name)
  if (!meme) return
  renameForm.oldName = meme.name
  renameForm.newName = meme.name
  showRename.value = true
}

async function submitRename() {
  renaming.value = true
  try {
    await apiPost('memes/rename', {
      old_name: renameForm.oldName,
      new_name: renameForm.newName.trim(),
    })
    message.success('重命名成功')
    showRename.value = false
    if (selectedName.value === renameForm.oldName) {
      selectedName.value = renameForm.newName.trim()
    }
    await loadMemes()
  } catch (e) {
    message.error(`重命名失败: ${(e as Error).message}`)
  } finally {
    renaming.value = false
  }
}

// ---------- 删除 ----------

async function deleteMeme(name: string) {
  try {
    await apiPost('memes/delete', { name })
    message.success(`已删除 ${name}`)
    if (selectedName.value === name) selectedName.value = null
    await loadMemes()
  } catch (e) {
    message.error(`删除失败: ${(e as Error).message}`)
  }
}

onMounted(async () => {
  await loadMemes()
  if (memes.value.length && !selectedName.value) {
    selectMeme(memes.value[0].name)
  }
})
</script>

<style>
.layout {
  height: 100vh;
}

.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--n-divider-color);
}

.brand {
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.sidebar-scroll {
  flex: 1;
  min-height: 0;
}

.menu-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.menu-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  border-top: 1px solid var(--n-divider-color);
}

.footer-text {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.content {
  height: 100%;
}

.content-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 28px 12px;
  border-bottom: 1px solid var(--n-divider-color);
}

.content-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.content-title h2 {
  font-size: 18px;
  margin: 0;
  color: var(--n-text-color-1);
}

.content-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.select-count {
  font-size: 13px;
  color: var(--n-text-color-2);
}

.content-scroll {
  flex: 1;
  min-height: 0;
}

.variant-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  padding: 20px 28px;
}

.variant-card {
  position: relative;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.variant-card:hover {
  border-color: var(--n-primary-color);
}

.variant-card.is-selected {
  border-color: var(--n-primary-color);
  background: var(--n-primary-color-soft);
  box-shadow: 0 0 0 1px var(--n-primary-color) inset;
}

.variant-card.is-selected .variant-preview {
  background: var(--n-primary-color-soft);
}

.variant-checkbox {
  flex-shrink: 0;
}

.variant-preview {
  aspect-ratio: 1;
  background: var(--n-color-1);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

/* NImage 的 img 无类名，直接后代选择器约束尺寸 */
.variant-preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.variant-preview-loading {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.variant-info {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 10px;
}

.variant-name {
  flex: 1;
  font-size: 12px;
  color: var(--n-text-color-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.grid-empty {
  grid-column: 1 / -1;
  margin-top: 40px;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-icon {
  font-size: 48px;
  opacity: 0.4;
  color: var(--n-text-color-3);
}

.upload-preview {
  max-width: 100%;
  max-height: 200px;
  object-fit: contain;
  border-radius: 6px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* 图片放大预览遮罩：默认仅 30% 暗，加深到 85% */
.n-image-preview-container {
  background-color: rgba(0, 0, 0, 0.85) !important;
}
</style>
