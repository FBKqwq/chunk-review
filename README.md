# Chunk 人工复验 Demo（Vite 本地依赖离线版）

这是一个最小可运行 demo，用于对 PDF 切分后的 chunk 和 LLM 预抽取 KG JSON 进行人工复验。

本版已取消 CDN Vue 引入，前端改为 **Vite + Vue3 本地依赖版**：

- `frontend/package.json`：前端依赖声明
- `frontend/node_modules/`：已随包提供，可离线运行前端构建产物或本地 Vite dev server
- `frontend/dist/`：已构建好的静态页面，由 Flask 直接托管

## 目录结构

```text
chunk_review_demo/
├── backend/
│   ├── app.py              # Flask API 服务，同时托管 frontend/dist
│   ├── parser.py           # 解析 chunk.json 与 kg.json
│   ├── parse_chunks.py     # 命令行解析脚本
│   ├── save_review.py      # 命令行结果初始化/导出脚本
│   ├── storage.py          # 人工复验结果落盘逻辑
│   └── requirements.txt
├── frontend/
│   ├── package.json        # Vite + Vue3 本地依赖配置
│   ├── package-lock.json
│   ├── node_modules/       # 已打包，避免运行页面依赖 CDN
│   ├── index.html
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.js
│   │   └── style.css
│   └── dist/               # 已构建好的离线静态页面
├── data/
│   ├── input/
│   │   ├── chunk/          # 放置 *.chunk.json
│   │   └── kg_json/        # 放置 *.kg.json
│   └── output/             # 保存 *.review.json
└── docs/
```

## 数据文件命名要求

同一个 PDF 对应的两个文件名必须同 stem：

```text
data/input/chunk/《白塞综合征诊疗规范》.chunk.json
data/input/kg_json/《白塞综合征诊疗规范》.kg.json
```

替换为其他 PDF 时，保证：

```text
XXX.chunk.json
XXX.kg.json
```

## 推荐运行方式：Flask 直接托管已构建页面

这种方式不需要访问外网，也不需要启动 Vite dev server。

```bash
cd chunk_review_demo
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\app.py
```

macOS/Linux：

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

说明：Flask 会优先读取 `frontend/dist/index.html`，所以页面中的 Vue 代码已经是本地构建产物，不再请求 CDN。

## 前端开发模式：Vite 本地依赖运行

只在你要改前端页面时使用。需要开两个终端。

终端 1：启动后端 API。

```bash
cd chunk_review_demo
python backend/app.py
```

终端 2：启动 Vite。

```bash
cd chunk_review_demo/frontend
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

`vite.config.js` 已配置代理：

```js
proxy: {
  '/api': 'http://127.0.0.1:5000'
}
```

所以前端访问 `/api/...` 会自动转发到 Flask 后端。

## 修改前端后重新构建

```bash
cd chunk_review_demo/frontend
npm run build
```

构建后刷新：

```text
http://127.0.0.1:5000
```

## 功能说明

### 1. 前端页面

页面采用 Vue3，实现：

- 左右两栏，各占 50%。
- 左侧上方展示当前 chunk 完整文本，占左侧 80%。
- 左侧下方展示 PDF、doc_id、chunk_id、页码、章节、span 等基础信息，并提供：
  - 保存：标记当前 chunk 为 `pass`
  - 解析错误：标记当前 chunk 为 `error`
- 右侧上方展示实体表：
  - 实体类型：固定 8 类，下拉选择
  - 实体名称：可编辑
- 右侧下方展示关系表：
  - 关系类型：固定 7 类，下拉选择
  - 起始实体：来自当前 chunk 实体名称
  - 终点实体：来自当前 chunk 实体名称
- 人工标记原文 span、拖拽连线等逻辑暂做占位。

### 2. 解析脚本

```bash
python backend/parse_chunks.py --doc "《白塞综合征诊疗规范》" --out data/output/parsed_demo.json
```

该脚本会读取：

```text
data/input/chunk/*.chunk.json
data/input/kg_json/*.kg.json
```

并合并为前端可消费的结构。

### 3. 结果输出脚本

```bash
python backend/save_review.py --doc "《白塞综合征诊疗规范》"
```

复验结果会保存到：

```text
data/output/《白塞综合征诊疗规范》.review.json
```

输出 JSON 分为三部分：

```json
{
  "base_info": {},
  "extractions": {
    "CH0001": {
      "entities": [],
      "relationships": []
    }
  },
  "review": {
    "CH0001": {
      "chunk_id": "CH0001",
      "section_title": "前言/概述",
      "page_start": 1,
      "page_end": 1,
      "status": "pass",
      "remark": "",
      "updated_at": "2026-xx-xxTxx:xx:xx"
    }
  }
}
```

## 当前 demo 的工程边界

- 这是人工复验 MVP，不包含用户登录、权限控制、多人并发锁、数据库。
- 当前保存策略为 JSON 文件落盘，适合小样验证；正式系统建议改为 SQLite/PostgreSQL/MySQL。
- 当前实体类型固定为 8 类；示例 KG 中的 `Etiology` 暂映射到“疾病”，正式版本建议将 Schema 扩展为 9 类或明确病因归属。
- 当前关系类型固定为示例 KG 中的 7 类：
  - `has_sub_disease`
  - `manifests_as`
  - `requires_test`
  - `follows_treatment`
  - `implements_by`
  - `causes`
  - `explained_by`
