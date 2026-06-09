<template>
  <div id="app">
    <div class="topbar">
      <h1>Chunk 人工复验</h1>
      <span>程序</span>
      <select class="program-select" v-model="activeProgram" @change="onProgramChange">
        <option value="opentcm">OpenTCM</option>
        <option value="snorkel">Snorkel</option>
        <option value="llm">LLM</option>
      </select>
      <span>文档</span>
      <select class="doc-select" v-model="selectedDoc" @change="onDocumentChange">
        <option v-for="doc in documents" :key="doc.doc_key" :value="doc.doc_key">
          {{ doc.source_title || doc.doc_key }}{{ docSuffix(doc) }}
        </option>
      </select>
      <template v-if="!isLlm">
        <button @click="prevChunk">上一条</button>
        <button @click="nextChunk">下一条</button>
        <span v-if="currentChunk" class="small">{{ currentIndex + 1 }} / {{ chunks.length }}</span>
      </template>
      <span v-else-if="currentChunk" class="small">全文模式 · {{ meta.concatenated_chunk_count || 0 }} 段 Chunk 拼接</span>
      <button @click="downloadOutput">下载复验结果 JSON</button>
      <span class="small">{{ message }}</span>
    </div>

    <div class="main" :class="{ 'snorkel-mode': isSnorkel }" v-if="currentChunk">
      <section class="left">
        <div class="panel panel-chunk" :class="{ 'panel-fulltext': isLlm }">
          <div class="panel-header panel-header-chunk">
            <div class="panel-header-row">
              <span v-if="isLlm">PDF 全文（Chunk 拼接） <span class="small">{{ meta.concatenated_chunk_count || 0 }} 段</span></span>
              <span v-else>当前 Chunk 完整文本 <span class="small">{{ currentChunk.chunk_id }}</span></span>
              <span :class="['status', reviewStatusClass(currentChunk.review?.status)]">{{ reviewStatusLabel(currentChunk.review?.status) }}</span>
            </div>
            <div class="chunk-meta-bar" :class="{ 'chunk-meta-bar--llm': isLlm }">
              <span class="meta-chip" :title="meta.source_title">PDF：{{ meta.source_title }}</span>
              <span class="meta-chip">页码：{{ currentChunk.page_start }} - {{ currentChunk.page_end }}</span>
              <span v-if="isLlm" class="meta-chip" :title="currentChunk.section_title">范围：{{ currentChunk.section_title }}</span>
              <span v-else class="meta-chip" :title="currentChunk.section_title">章节：{{ currentChunk.section_title }}</span>
              <span v-if="isLlm" class="meta-chip">字符：{{ currentChunk.text?.length || 0 }}</span>
              <span v-else class="meta-chip">span：{{ currentChunk.text_span?.start }} - {{ currentChunk.text_span?.end }}</span>
            </div>
          </div>
          <div class="panel-body" ref="chunkPanelBody">
            <div class="chunk-text" v-html="highlightedChunkHtml"></div>
          </div>
        </div>

        <div class="panel panel-actions">
          <div class="panel-header">
            <span>复验操作</span>
            <span class="small">{{ reviewActionHint }}</span>
          </div>
          <div class="panel-body">
            <div class="actions">
              <textarea v-model="remark" placeholder="备注，可为空"></textarea>
              <button class="primary" @click="saveReview('0')">保存 (1)</button>
              <button class="danger" @click="saveReview('1')">解析错误 (2)</button>
            </div>
          </div>
        </div>
      </section>

      <section class="right">
        <div class="panel panel-entity">
          <div class="panel-header">
            <span>实体复验表 <span class="small">实体类型固定 8 类</span></span>
            <button class="ghost" @click="addEntity">新增实体</button>
          </div>
          <div class="panel-body">
            <div v-if="currentChunkSourceHint" class="kg-notice">{{ currentChunkSourceHint }}</div>
            <table>
              <thead>
                <tr>
                  <th>实体类型</th>
                  <th>实体名称</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in entitiesDisplay" :key="item.entity.id || item.originIdx">
                  <td>
                    <select
                      v-model="item.entity.entity_type"
                      :class="entityFieldClass(item)"
                      :title="item.entity.entity_type"
                    >
                      <option v-for="t in entityTypes" :key="t" :value="t">{{ t }}</option>
                    </select>
                  </td>
                  <td>
                    <input
                      v-model="item.entity.entity_name"
                      placeholder="实体名称"
                      :class="entityFieldClass(item)"
                      :title="item.entity.entity_name"
                      @focus="onReviewFieldFocus(item.entity.entity_name)"
                      @blur="onReviewFieldBlur"
                    />
                  </td>
                  <td><button @click="removeEntity(item.originIdx)">删除</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel panel-rel">
          <div class="panel-header">
            <span>关系复验表 <span class="small">关系类型固定 7 类</span></span>
            <button class="ghost" @click="addRelation">新增关系</button>
          </div>
          <div class="panel-body">
            <div class="placeholder">{{ relationPlaceholderText }}</div>
            <table>
              <thead>
                <tr>
                  <th>关系类型</th>
                  <th>起始实体</th>
                  <th>终点实体</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in relationshipsDisplay" :key="item.rel.id || item.originIdx">
                  <td>
                    <select
                      v-model="item.rel.relation_type"
                      :class="relationFieldClass(item)"
                      :title="relationTypeNames[item.rel.relation_type] || item.rel.relation_type"
                    >
                      <option v-for="t in relationTypes" :key="t" :value="t">{{ relationTypeNames[t] || t }}</option>
                    </select>
                  </td>
                  <td>
                    <select
                      v-model="item.rel.source_entity"
                      :class="relationFieldClass(item)"
                      :title="item.rel.source_entity || '请选择起始实体'"
                      @focus="onReviewFieldFocus(item.rel.source_entity)"
                      @blur="onReviewFieldBlur"
                    >
                      <option value="">请选择</option>
                      <option v-for="name in entityNames" :key="name" :value="name">{{ name }}</option>
                    </select>
                  </td>
                  <td>
                    <select
                      v-model="item.rel.target_entity"
                      :class="relationFieldClass(item)"
                      :title="item.rel.target_entity || '请选择终点实体'"
                      @focus="onReviewFieldFocus(item.rel.target_entity)"
                      @blur="onReviewFieldBlur"
                    >
                      <option value="">请选择</option>
                      <option v-for="name in entityNames" :key="name" :value="name">{{ name }}</option>
                    </select>
                  </td>
                  <td><button @click="removeRelation(item.originIdx)">删除</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>

    <div v-else-if="loading" class="loading">正在加载 Chunk 数据…</div>
    <div v-else-if="loadError" class="loading load-error">{{ loadError }}</div>
    <div v-else class="loading">未找到可审阅的 Chunk 数据，请检查 data/input/chunk 目录。</div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

const activeProgram = ref('opentcm');
const documents = ref([]);
const selectedDoc = ref('');
const meta = ref({});
const chunks = ref([]);
const currentIndex = ref(0);
const entityTypes = ref([]);
const relationTypes = ref([]);
const relationTypeNames = ref({});
const entities = ref([]);
const relationships = ref([]);
const remark = ref('');
const message = ref('');
const loading = ref(false);
const loadError = ref('');
const chunkPanelBody = ref(null);
const focusedEntityKey = ref('');

const isSnorkel = computed(() => activeProgram.value === 'snorkel');
const isLlm = computed(() => activeProgram.value === 'llm');
const reviewApiBase = computed(() => {
  if (isLlm.value) return '/api/llm-review-data';
  if (isSnorkel.value) return '/api/snorkel-review-data';
  return '/api/review-data';
});
const downloadApiPath = computed(() => {
  if (isLlm.value) return '/api/llm-review-output-file';
  if (isSnorkel.value) return '/api/snorkel-review-output-file';
  return '/api/review-output-file';
});

const currentChunk = computed(() => chunks.value[currentIndex.value] || null);
const entityNames = computed(() => [...new Set(entities.value.map(e => e.entity_name).filter(Boolean))]);

const entityNameCounts = computed(() => {
  const counts = {};
  for (const entity of entities.value) {
    const name = (entity.entity_name || '').trim();
    if (name) counts[name] = (counts[name] || 0) + 1;
  }
  return counts;
});

const relationKeyCounts = computed(() => {
  const counts = {};
  for (const rel of relationships.value) {
    const key = buildRelationKey(rel);
    if (key) counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
});

const entitiesDisplay = computed(() => {
  const text = currentChunk.value?.text || '';
  return entities.value
    .map((entity, originIdx) => {
      const name = (entity.entity_name || '').trim();
      const matched = Boolean(name && isEntityMatched(text, name));
      const isDuplicate = Boolean(name && entityNameCounts.value[name] > 1);
      return { entity, originIdx, matched, isDuplicate, sortName: name };
    })
    .sort((a, b) => compareReviewItems(a, b, entityTypes.value, 'entity'));
});

const relationshipsDisplay = computed(() => {
  const text = currentChunk.value?.text || '';
  return relationships.value
    .map((rel, originIdx) => {
      const source = (rel.source_entity || '').trim();
      const target = (rel.target_entity || '').trim();
      const matched = Boolean(
        source
        && target
        && isEntityMatched(text, source)
        && isEntityMatched(text, target)
      );
      const key = buildRelationKey(rel);
      const isDuplicate = Boolean(key && relationKeyCounts.value[key] > 1);
      return { rel, originIdx, matched, isDuplicate };
    })
    .sort((a, b) => compareReviewItems(a, b, relationTypes.value, 'relation'));
});

const displayChunkText = computed(() => formatChunkForDisplay(currentChunk.value?.text || ''));

const highlightedChunkHtml = computed(() => {
  return buildHighlightedHtml(displayChunkText.value, entities.value);
});

const currentChunkSourceHint = computed(() => {
  const ch = currentChunk.value;
  if (!ch) return '';
  if (isLlm.value) {
    if (meta.value.llm_status === 'missing') {
      return '未找到对应 LLM JSON，当前仅展示 Chunk 拼接全文，实体与关系需手动新增。';
    }
    if (ch.llm_status === 'empty') {
      return '当前文档在 LLM JSON 中无预抽取实体/关系，可手动新增后继续审阅。';
    }
    return '';
  }
  if (isSnorkel.value) {
    if (meta.value.entitybase_status === 'missing') {
      return '未找到对应 entity_base.jsonl，当前仅展示 Chunk 原文，实体与关系需手动新增。';
    }
    if (ch.entitybase_status === 'empty') {
      return '当前 Chunk 在 entity_base 中无预抽取实体，可手动新增后继续审阅。';
    }
    return '';
  }
  if (meta.value.kg_status === 'missing') {
    return '未找到对应 kg_json，当前仅展示 Chunk 原文，实体与关系需手动新增。';
  }
  if (ch.kg_status === 'empty') {
    return '当前 Chunk 在 kg_json 中无预抽取实体/关系，可手动新增后继续审阅。';
  }
  return '';
});

const relationPlaceholderText = computed(() => {
  if (isSnorkel.value) {
    return 'Snorkel 关系抽取任务进行中，预抽取结果接入后将在本区域展示；当前可手动新增关系。';
  }
  return '人工关系标记逻辑占位：后续可支持从实体表拖拽连线生成关系。';
});

const reviewActionHint = computed(() => {
  if (isLlm.value) return '↑ ↓ 切换 PDF · 1 通过 · 2 解析错误';
  return '← → 切换 Chunk · ↑ ↓ 切换 PDF · 1 通过 · 2 解析错误';
});

watch(currentIndex, bindCurrentChunk);

watch(highlightedChunkHtml, async () => {
  if (!focusedEntityKey.value) return;
  await nextTick();
  applyActiveEntityHighlight(focusedEntityKey.value);
});

function reviewCategory(item) {
  if (!item.matched) return 0;
  if (item.isDuplicate) return 1;
  return 2;
}

function typeOrderIndex(type, orderedTypes) {
  const idx = orderedTypes.indexOf(type);
  return idx === -1 ? orderedTypes.length : idx;
}

function compareReviewItems(a, b, orderedTypes, kind) {
  const categoryDiff = reviewCategory(a) - reviewCategory(b);
  if (categoryDiff !== 0) return categoryDiff;

  const typeA = kind === 'entity' ? a.entity.entity_type : a.rel.relation_type;
  const typeB = kind === 'entity' ? b.entity.entity_type : b.rel.relation_type;
  const typeDiff = typeOrderIndex(typeA, orderedTypes) - typeOrderIndex(typeB, orderedTypes);
  if (typeDiff !== 0) return typeDiff;

  if (kind === 'entity') {
    const nameDiff = (a.sortName || '').localeCompare(b.sortName || '', 'zh-CN');
    if (nameDiff !== 0) return nameDiff;
  } else {
    const sourceDiff = (a.rel.source_entity || '').localeCompare(b.rel.source_entity || '', 'zh-CN');
    if (sourceDiff !== 0) return sourceDiff;
    const targetDiff = (a.rel.target_entity || '').localeCompare(b.rel.target_entity || '', 'zh-CN');
    if (targetDiff !== 0) return targetDiff;
  }

  return a.originIdx - b.originIdx;
}

function buildRelationKey(rel) {
  const source = (rel.source_entity || '').trim();
  const target = (rel.target_entity || '').trim();
  if (!rel.relation_type && !source && !target) return '';
  return `${rel.relation_type}::${source}::${target}`;
}

function entityFieldClass(item) {
  if (!item.matched) return 'entity-unmatched';
  if (item.isDuplicate) return 'entity-duplicate';
  return '';
}

function relationFieldClass(item) {
  if (!item.matched) return 'entity-unmatched';
  if (item.isDuplicate) return 'entity-duplicate';
  return '';
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function reflowParagraph(paragraph) {
  let result = paragraph;
  let prev;
  do {
    prev = result;
    result = result
      .replace(
        /([\u4e00-\u9fff，。；：！？、）】」》'"…—－])\n([\u4e00-\u9fff（【「《"'\d])/g,
        '$1$2'
      )
      .replace(/([\u4e00-\u9fff\d])\n([\u4e00-\u9fff\d（【「《"'])/g, '$1$2')
      .replace(/([a-zA-Z0-9])\n([a-zA-Z0-9])/g, '$1$2');
  } while (result !== prev);

  return result
    .replace(/\n/g, ' ')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}

function formatChunkForDisplay(text) {
  if (!text) return '';
  const normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  return normalized
    .split(/\n{2,}/)
    .map(reflowParagraph)
    .filter(Boolean)
    .join('\n\n');
}

function normalizeMatchText(str) {
  return (str || '').replace(/\s+/g, '');
}

function buildCollapsedIndexMap(text) {
  const chars = [];
  const indexMap = [];
  for (let i = 0; i < text.length; i += 1) {
    if (/\s/.test(text[i])) continue;
    chars.push(text[i]);
    indexMap.push(i);
  }
  return { collapsed: chars.join(''), indexMap };
}

function findEntityMatch(text, name) {
  const normalizedName = normalizeMatchText(name);
  if (!normalizedName) return null;
  const { collapsed, indexMap } = buildCollapsedIndexMap(text);
  const start = collapsed.indexOf(normalizedName);
  if (start === -1) return null;
  const endIdx = start + normalizedName.length - 1;
  return {
    start: indexMap[start],
    end: indexMap[endIdx] + 1
  };
}

function isEntityMatched(text, name) {
  return Boolean(findEntityMatch(text, name));
}

function onReviewFieldFocus(name) {
  scrollToEntityInText(name);
}

function onReviewFieldBlur() {
  requestAnimationFrame(() => {
    const active = document.activeElement;
    if (active?.closest?.('.panel-entity, .panel-rel')) return;
    clearActiveEntityHighlight();
  });
}

function clearActiveEntityHighlight() {
  focusedEntityKey.value = '';
  const panel = chunkPanelBody.value;
  if (!panel) return;
  panel.querySelectorAll('.entity-hl--active').forEach(el => {
    el.classList.remove('entity-hl--active');
  });
}

function applyActiveEntityHighlight(key) {
  const panel = chunkPanelBody.value;
  if (!panel || !key) return;
  panel.querySelectorAll('.entity-hl--active').forEach(el => {
    el.classList.remove('entity-hl--active');
  });
  panel.querySelectorAll(`.entity-hl[data-ename="${CSS.escape(key)}"]`).forEach(el => {
    el.classList.add('entity-hl--active');
  });
}

async function scrollToEntityInText(name) {
  const trimmed = (name || '').trim();
  const text = displayChunkText.value;
  if (!trimmed || !isEntityMatched(text, trimmed)) {
    clearActiveEntityHighlight();
    return;
  }

  const key = normalizeMatchText(trimmed);
  focusedEntityKey.value = key;

  await nextTick();
  const panel = chunkPanelBody.value;
  if (!panel) return;

  applyActiveEntityHighlight(key);

  const target = panel.querySelector(`.entity-hl[data-ename="${CSS.escape(key)}"]`);
  if (!target) return;

  const panelRect = panel.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const offset = targetRect.top - panelRect.top - panel.clientHeight / 2 + targetRect.height / 2;
  panel.scrollTo({ top: panel.scrollTop + offset, behavior: 'smooth' });
}

function buildMatchSpans(text, entityList) {
  const seenNames = new Set();
  const spans = [];
  for (const entity of entityList) {
    const name = (entity.entity_name || '').trim();
    if (!name || seenNames.has(name)) continue;
    const match = findEntityMatch(text, name);
    if (!match) continue;
    seenNames.add(name);
    spans.push({
      start: match.start,
      end: match.end,
      entityType: entity.entity_type || '',
      name
    });
  }
  return spans;
}

function assignSpanLayers(spans) {
  const sorted = [...spans].sort((a, b) => {
    const lenDiff = (b.end - b.start) - (a.end - a.start);
    return lenDiff !== 0 ? lenDiff : a.start - b.start;
  });
  const assigned = [];
  for (const span of sorted) {
    let layer = 0;
    for (const other of assigned) {
      if (span.start < other.end && other.start < span.end) {
        layer = Math.max(layer, other.layer + 1);
      }
    }
    span.layer = Math.min(layer, 2);
    assigned.push(span);
  }
  return spans;
}

function buildHighlightedHtml(text, entityList) {
  if (!text) return '';
  const spans = assignSpanLayers(buildMatchSpans(text, entityList));
  if (!spans.length) return escapeHtml(text);

  const points = new Set([0, text.length]);
  for (const span of spans) {
    points.add(span.start);
    points.add(span.end);
  }
  const bounds = [...points].sort((a, b) => a - b);

  const layerClasses = ['entity-hl--bg', 'entity-hl--underline', 'entity-hl--wavy'];
  let html = '';
  for (let i = 0; i < bounds.length - 1; i += 1) {
    const start = bounds[i];
    const end = bounds[i + 1];
    if (start === end) continue;

    const covering = spans.filter(span => span.start <= start && span.end >= end);
    if (!covering.length) {
      html += escapeHtml(text.slice(start, end));
      continue;
    }

    covering.sort((a, b) => (b.end - b.start) - (a.end - a.start));
    let chunk = escapeHtml(text.slice(start, end));
    for (const span of covering) {
      const layerClass = layerClasses[span.layer] || layerClasses[0];
      const typeAttr = escapeHtml(span.entityType);
      const nameAttr = span.name && start >= span.start && end <= span.end
        ? ` data-ename="${escapeHtml(normalizeMatchText(span.name))}"`
        : '';
      chunk = `<span class="entity-hl ${layerClass}" data-etype="${typeAttr}"${nameAttr}>${chunk}</span>`;
    }
    html += chunk;
  }
  return html;
}

function isDocSelect(target) {
  return Boolean(
    target?.classList?.contains('doc-select')
    || target?.classList?.contains('program-select')
  );
}

function isEditableTarget(target) {
  if (!target || isDocSelect(target)) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

function onKeydown(e) {
  if (isEditableTarget(e.target)) return;
  if (e.key === 'ArrowUp') {
    e.preventDefault();
    prevDocument();
    return;
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    nextDocument();
    return;
  }
  if (!currentChunk.value) return;
  if (isLlm.value) {
    if (e.key === '1') {
      e.preventDefault();
      saveReview('0');
    } else if (e.key === '2') {
      e.preventDefault();
      saveReview('1');
    }
    return;
  }
  if (e.key === 'ArrowLeft') {
    e.preventDefault();
    prevChunk();
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    nextChunk();
  } else if (e.key === '1') {
    e.preventDefault();
    saveReview('0');
  } else if (e.key === '2') {
    e.preventDefault();
    saveReview('1');
  }
}

function normalizeReviewStatus(status) {
  if (status === 'pass' || status === '0') return '0';
  if (status === 'error' || status === '1') return '1';
  return status || 'unreviewed';
}

function reviewStatusClass(status) {
  const normalized = normalizeReviewStatus(status);
  if (normalized === '0') return 'pass';
  if (normalized === '1') return 'error';
  return '';
}

function reviewStatusLabel(status) {
  const normalized = normalizeReviewStatus(status);
  if (normalized === '0') return 'pass';
  if (normalized === '1') return 'error';
  return normalized;
}

onMounted(async () => {
  await loadDocuments();
  window.addEventListener('keydown', onKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown);
});

async function loadDocuments() {
  loading.value = true;
  loadError.value = '';
  try {
    const res = await fetch('/api/documents');
    const data = await res.json();
    documents.value = data.documents || [];
    if (documents.value.length > 0) {
      selectedDoc.value = documents.value[0].doc_key;
      await loadReviewData();
    } else {
      chunks.value = [];
      message.value = '';
    }
  } catch (err) {
    loadError.value = `文档列表加载失败：${err.message}`;
    chunks.value = [];
  } finally {
    loading.value = false;
  }
}

function docSuffix(doc) {
  const parts = [];
  if (doc.has_kg === false) parts.push('无 kg');
  if (doc.has_entitybase === false) parts.push('无 entitybase');
  if (doc.has_llm === false) parts.push('无 LLM');
  return parts.length ? `（${parts.join(' · ')}）` : '';
}

async function onProgramChange(e) {
  if (selectedDoc.value) {
    await loadReviewData();
  }
  e?.target?.blur();
}

async function onDocumentChange(e) {
  await loadReviewData();
  e?.target?.blur();
}

async function loadReviewData() {
  if (!selectedDoc.value) return;
  loading.value = true;
  loadError.value = '';
  try {
    const res = await fetch(`${reviewApiBase.value}/${encodeURIComponent(selectedDoc.value)}`);
    const data = await res.json();
    if (!res.ok || data.ok === false) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    meta.value = data.meta || {};
    chunks.value = data.chunks || [];
    entityTypes.value = data.entity_types || [];
    relationTypes.value = data.relation_types || [];
    relationTypeNames.value = data.relation_type_names || {};
    currentIndex.value = 0;
    bindCurrentChunk();
    updateSourceMessage();
  } catch (err) {
    chunks.value = [];
    loadError.value = `Chunk 加载失败：${err.message}`;
    message.value = '';
  } finally {
    loading.value = false;
  }
}

function updateSourceMessage() {
  if (!chunks.value.length) {
    message.value = '当前文档未包含可审阅的 Chunk 段落。';
    return;
  }
  if (isLlm.value) {
    if (meta.value.llm_status === 'missing') {
      message.value = '未找到对应 LLM JSON，已载入 Chunk 拼接全文，可继续审阅并手动标注。';
      return;
    }
    if (meta.value.llm_status === 'empty') {
      message.value = '已载入全文，但 LLM JSON 中暂无预抽取实体/关系，可手动标注。';
      return;
    }
    message.value = `已载入 ${meta.value.concatenated_chunk_count || 0} 段 Chunk 拼接全文，并加载 LLM 预抽取结果。`;
    return;
  }
  if (isSnorkel.value) {
    if (meta.value.entitybase_status === 'missing') {
      message.value = '未找到对应 entity_base.jsonl，已载入 Chunk 原文，可继续审阅并手动标注。';
      return;
    }
    const matched = meta.value.entitybase_matched_chunks || 0;
    const total = meta.value.total_chunks || chunks.value.length;
    if (matched === 0) {
      message.value = '已载入 Chunk，但 entity_base 中暂无匹配的实体，可手动标注。';
      return;
    }
    if (matched < total) {
      message.value = `已载入 Chunk，entity_base 已匹配 ${matched}/${total} 条 Chunk 的预抽取实体。`;
      return;
    }
    message.value = '';
    return;
  }
  if (meta.value.kg_status === 'missing') {
    message.value = '未找到对应 kg_json，已载入 Chunk 原文，可继续审阅并手动标注。';
    return;
  }
  const matched = meta.value.kg_matched_chunks || 0;
  const total = meta.value.total_chunks || chunks.value.length;
  if (matched === 0) {
    message.value = '已载入 Chunk，但 kg_json 中暂无匹配的实体/关系，可手动标注。';
    return;
  }
  if (matched < total) {
    message.value = `已载入 Chunk，kg_json 已匹配 ${matched}/${total} 条 Chunk 的预抽取结果。`;
    return;
  }
  message.value = '';
}

function bindCurrentChunk() {
  clearActiveEntityHighlight();
  const ch = currentChunk.value;
  if (!ch) return;
  entities.value = JSON.parse(JSON.stringify(ch.entities || []));
  relationships.value = JSON.parse(JSON.stringify(ch.relationships || []));
  remark.value = ch.review?.remark || '';
}

function currentDocumentIndex() {
  return documents.value.findIndex(doc => doc.doc_key === selectedDoc.value);
}

async function prevDocument() {
  const idx = currentDocumentIndex();
  if (idx <= 0) return;
  selectedDoc.value = documents.value[idx - 1].doc_key;
  await loadReviewData();
}

async function nextDocument() {
  const idx = currentDocumentIndex();
  if (idx < 0 || idx >= documents.value.length - 1) return;
  selectedDoc.value = documents.value[idx + 1].doc_key;
  await loadReviewData();
}

function prevChunk() {
  if (currentIndex.value > 0) currentIndex.value -= 1;
}

function nextChunk() {
  if (currentIndex.value < chunks.value.length - 1) currentIndex.value += 1;
}

function addEntity() {
  entities.value.push({
    id: `manual_entity_${Date.now()}`,
    entity_type: entityTypes.value[0] || '',
    entity_name: '',
    raw_label: 'manual',
    chunk_id: currentChunk.value.chunk_id
  });
}

function removeEntity(idx) {
  entities.value.splice(idx, 1);
}

function addRelation() {
  relationships.value.push({
    id: `manual_relation_${Date.now()}`,
    relation_type: relationTypes.value[0] || '',
    source_entity: '',
    target_entity: '',
    chunk_id: currentChunk.value.chunk_id
  });
}

function removeRelation(idx) {
  relationships.value.splice(idx, 1);
}

async function saveReview(status) {
  const ch = currentChunk.value;
  const body = {
    status,
    remark: remark.value,
    entities: entities.value,
    relationships: relationships.value
  };
  const saveUrl = isLlm.value
    ? `${reviewApiBase.value}/${encodeURIComponent(selectedDoc.value)}`
    : `${reviewApiBase.value}/${encodeURIComponent(selectedDoc.value)}/${encodeURIComponent(ch.chunk_id)}`;
  const res = await fetch(saveUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  if (data.ok) {
    ch.entities = JSON.parse(JSON.stringify(entities.value));
    ch.relationships = JSON.parse(JSON.stringify(relationships.value));
    ch.review = data.review;
    const label = isLlm.value ? '全文' : ch.chunk_id;
    message.value = `${label} 已保存为 ${reviewStatusLabel(status)}`;
  } else {
    message.value = '保存失败';
  }
}

function downloadOutput() {
  if (!selectedDoc.value) return;
  window.open(`${downloadApiPath.value}/${encodeURIComponent(selectedDoc.value)}`, '_blank');
}
</script>
