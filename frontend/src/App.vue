<template>
  <div id="app">
    <div class="topbar">
      <h1>Chunk 人工复验</h1>
      <span>文档</span>
      <select v-model="selectedDoc" @change="loadReviewData">
        <option v-for="doc in documents" :key="doc.doc_key" :value="doc.doc_key">
          {{ doc.source_title || doc.doc_key }}
        </option>
      </select>
      <button @click="prevChunk">上一条</button>
      <button @click="nextChunk">下一条</button>
      <span v-if="currentChunk" class="small">{{ currentIndex + 1 }} / {{ chunks.length }}</span>
      <button @click="downloadOutput">下载复验结果 JSON</button>
      <span class="small">{{ message }}</span>
    </div>

    <div class="main" v-if="currentChunk">
      <section class="left">
        <div class="panel">
          <div class="panel-header">
            <span>当前 Chunk 完整文本</span>
            <span class="small">{{ currentChunk.chunk_id }} · {{ currentChunk.section_title }}</span>
          </div>
          <div class="panel-body">
            <div class="chunk-text" v-html="highlightedChunkHtml"></div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <span>Chunk 基础信息与复验操作</span>
            <span :class="['status', currentChunk.review?.status]">{{ currentChunk.review?.status || 'unreviewed' }}</span>
          </div>
          <div class="panel-body">
            <div class="meta-grid">
              <div class="meta-item">PDF：{{ meta.source_title }}</div>
              <div class="meta-item">doc_id：{{ meta.doc_id }}</div>
              <div class="meta-item">chunk_id：{{ currentChunk.chunk_id }}</div>
              <div class="meta-item">页码：{{ currentChunk.page_start }} - {{ currentChunk.page_end }}</div>
              <div class="meta-item">章节：{{ currentChunk.section_title }}</div>
              <div class="meta-item">span：{{ currentChunk.text_span?.start }} - {{ currentChunk.text_span?.end }}</div>
            </div>
            <div class="actions">
              <textarea v-model="remark" placeholder="备注，可为空"></textarea>
              <button class="primary" @click="saveReview('pass')">保存</button>
              <button class="danger" @click="saveReview('error')">解析错误</button>
            </div>
          </div>
        </div>
      </section>

      <section class="right">
        <div class="panel">
          <div class="panel-header">
            <span>实体复验表 <span class="small">实体类型固定 8 类</span></span>
            <button class="ghost" @click="addEntity">新增实体</button>
          </div>
          <div class="panel-body">
            <table>
              <thead>
                <tr>
                  <th style="width: 180px;">实体类型</th>
                  <th>实体名称</th>
                  <th style="width: 70px;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in entitiesDisplay" :key="item.entity.id || item.originIdx">
                  <td>
                    <select
                      v-model="item.entity.entity_type"
                      :class="entityFieldClass(item)"
                    >
                      <option v-for="t in entityTypes" :key="t" :value="t">{{ t }}</option>
                    </select>
                  </td>
                  <td>
                    <input
                      v-model="item.entity.entity_name"
                      placeholder="实体名称"
                      :class="entityFieldClass(item)"
                    />
                  </td>
                  <td><button @click="removeEntity(item.originIdx)">删除</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <span>关系复验表 <span class="small">关系类型固定 7 类</span></span>
            <button class="ghost" @click="addRelation">新增关系</button>
          </div>
          <div class="panel-body">
            <div class="placeholder">人工关系标记逻辑占位：后续可支持从实体表拖拽连线生成关系。</div>
            <table>
              <thead>
                <tr>
                  <th style="width: 170px;">关系类型</th>
                  <th>起始实体</th>
                  <th>终点实体</th>
                  <th style="width: 70px;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(rel, idx) in relationships" :key="rel.id || idx">
                  <td>
                    <select v-model="rel.relation_type">
                      <option v-for="t in relationTypes" :key="t" :value="t">{{ relationTypeNames[t] || t }}</option>
                    </select>
                  </td>
                  <td>
                    <select v-model="rel.source_entity">
                      <option value="">请选择</option>
                      <option v-for="name in entityNames" :key="name" :value="name">{{ name }}</option>
                    </select>
                  </td>
                  <td>
                    <select v-model="rel.target_entity">
                      <option value="">请选择</option>
                      <option v-for="name in entityNames" :key="name" :value="name">{{ name }}</option>
                    </select>
                  </td>
                  <td><button @click="removeRelation(idx)">删除</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>

    <div v-else class="loading">正在加载数据，或未找到可复验文档。</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';

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

const entitiesDisplay = computed(() => {
  const text = currentChunk.value?.text || '';
  return entities.value
    .map((entity, originIdx) => {
      const name = (entity.entity_name || '').trim();
      const matched = Boolean(name && isEntityMatched(text, name));
      const isDuplicate = Boolean(name && entityNameCounts.value[name] > 1);
      return { entity, originIdx, matched, isDuplicate, sortName: name };
    })
    .sort((a, b) => {
      if (a.matched !== b.matched) return a.matched ? 1 : -1;
      if (a.sortName !== b.sortName) return a.sortName.localeCompare(b.sortName, 'zh-CN');
      return a.originIdx - b.originIdx;
    });
});

const displayChunkText = computed(() => formatChunkForDisplay(currentChunk.value?.text || ''));

const highlightedChunkHtml = computed(() => {
  return buildHighlightedHtml(displayChunkText.value, entities.value);
});

watch(currentIndex, bindCurrentChunk);

function entityFieldClass(item) {
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
      entityType: entity.entity_type || ''
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
      chunk = `<span class="entity-hl ${layerClass}" data-etype="${typeAttr}">${chunk}</span>`;
    }
    html += chunk;
  }
  return html;
}

onMounted(async () => {
  await loadDocuments();
});

async function loadDocuments() {
  const res = await fetch('/api/documents');
  const data = await res.json();
  documents.value = data.documents || [];
  if (documents.value.length > 0) {
    selectedDoc.value = documents.value[0].doc_key;
    await loadReviewData();
  }
}

async function loadReviewData() {
  if (!selectedDoc.value) return;
  const res = await fetch(`/api/review-data/${encodeURIComponent(selectedDoc.value)}`);
  const data = await res.json();
  meta.value = data.meta || {};
  chunks.value = data.chunks || [];
  entityTypes.value = data.entity_types || [];
  relationTypes.value = data.relation_types || [];
  relationTypeNames.value = data.relation_type_names || {};
  currentIndex.value = 0;
  bindCurrentChunk();
}

function bindCurrentChunk() {
  const ch = currentChunk.value;
  if (!ch) return;
  entities.value = JSON.parse(JSON.stringify(ch.entities || []));
  relationships.value = JSON.parse(JSON.stringify(ch.relationships || []));
  remark.value = ch.review?.remark || '';
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
  const res = await fetch(`/api/review-data/${encodeURIComponent(selectedDoc.value)}/${encodeURIComponent(ch.chunk_id)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  if (data.ok) {
    ch.entities = JSON.parse(JSON.stringify(entities.value));
    ch.relationships = JSON.parse(JSON.stringify(relationships.value));
    ch.review = data.review;
    message.value = `${ch.chunk_id} 已保存为 ${status}`;
  } else {
    message.value = '保存失败';
  }
}

function downloadOutput() {
  if (!selectedDoc.value) return;
  window.open(`/api/review-output-file/${encodeURIComponent(selectedDoc.value)}`, '_blank');
}
</script>
