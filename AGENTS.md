# AGENTS.md — paper-organizer

> 这份文件是给 AI 编码助手（Cursor、Claude Code、Copilot 等）的上下文说明。
> 阅读本文件后再动任何代码。

---

## 项目简介

`paper-organizer` 是一个运行在本地 Linux 环境的自动化脚本，
负责监控一个"临时 papers 文件夹"，将其中命名混乱的学术 PDF
（通常是 DOI 号或随机字符串）重命名为**中文可读标题**，
并将摘要摘要写入一个统一的 `_index.md` 索引文件。

**核心假设：**

- 用户每天下载若干论文到 `~/Downloads/papers/`
- 大部分是泛读材料，少数会被手动移走
- 偶尔需要回翻"读过的那篇有用的论文"，所以文件名可读性比原始名称重要
- 不联网查询时也要能工作（纯本地 LLM 降级处理）

## 目录结构

```
paper-organizer/
├── AGENTS.md              ← 本文件
├── README.md
├── organizer.py           ← 主逻辑入口（Python）
├── lib/
│   ├── extractor.py       ← 元数据提取（PDF 文字 / DOI / CrossRef）
│   ├── llm.py             ← Ollama 调用封装（翻译 + 摘要）
│   ├── renamer.py         ← 文件重命名 + 幂等状态管理
│   └── index_writer.py    ← _index.md 写入逻辑
├── config.toml            ← 用户配置（路径、模型、行为开关）
├── .processed             ← 已处理文件的哈希记录（勿手动编辑）
└── logs/
    └── organizer.log
```

---

## 数据流

```
inbox/ 中的 .pdf 文件
        │
        ▼
[1] extractor.py
    ├─ 路径 A：pdf2doi 识别 DOI → CrossRef API → 结构化元数据
    │          （title, abstract, year, authors）
    └─ 路径 B：PyMuPDF 提取首页最大字号文字块 → 猜测标题
               （无网络 / 无 DOI 时的降级方案）
        │
        ▼
[2] llm.py  （仅在需要时调用，见"调用策略"节）
    ├─ 任务 A：将英文标题翻译为中文（≤30 字，适合作文件名）
    └─ 任务 B：用 2-3 句中文总结核心贡献
               （可在 config.toml 中关闭）
        │
        ▼
[3] renamer.py
    ├─ 生成新文件名：{year}_{zh_title}.pdf
    ├─ 检查 .processed 哈希，跳过已处理文件
    └─ 执行 os.rename()，更新 .processed
        │
        ▼
[4] index_writer.py
    └─ 追加写入 inbox/_index.md
```

---

## 各模块职责

### `organizer.py`（入口）

- 解析 `config.toml`
- 遍历 `inbox_dir` 下所有 `.pdf` 文件
- 对每个文件：加载哈希缓存 → 调用 extractor → 调用 llm → 调用 renamer → 调用 index_writer
- 异常时记录 log，**不中断整体流程**（单文件失败不影响其他文件）
- 支持 `--dry-run` 标志：只打印拟操作，不实际重命名

### `lib/extractor.py`

**优先级顺序（从高到低）：**

1. **DOI 路径**：调用 `pdf2doi` 库提取 DOI，再请求
   `https://api.crossref.org/works/{doi}` 拿结构化数据。
   CrossRef 返回的 `abstract` 字段通常带 JATS XML 标签，需要清洗。
2. **PyMuPDF 路径**：`fitz.open()` → `page.get_text("dict")`
   → 按 `span["size"]` 降序排列 → 取首页最大字号文字作为标题。
   不做 OCR（绝大多数下载 PDF 有嵌入文字）。
   只有检测到文字密度极低时才提示用户考虑 OCR，**脚本本身不内置 OCR**。

**返回格式（统一 TypedDict）：**

```python
class PaperMeta(TypedDict):
    title: str          # 原始英文标题
    abstract: str       # 摘要原文（可为空字符串）
    year: str           # 出版年份（可为 "未知"）
    source: str         # "crossref" | "pymupdf" | "unknown"
```

### `lib/llm.py`

**调用策略——避免不必要的推理开销：**

| 情况                        | 行为                                                 |
| --------------------------- | ---------------------------------------------------- |
| CrossRef 有标题 + 摘要      | 调用 LLM 翻译标题 + 生成摘要                         |
| CrossRef 有标题，无摘要     | 仅调用 LLM 翻译标题                                  |
| PyMuPDF 猜测的标题          | 调用 LLM 翻译（质量可能较低，文件名加 `[ocr]` 标记） |
| LLM 不可用（Ollama 未启动） | 降级：使用原始英文标题，截断到 50 字符               |

**模型选择建议（写在 config.toml，不硬编码）：**

- 翻译标题：`qwen2.5:1.5b` 即可
- 摘要提炼：推荐 `qwen2.5:3b` 或 `phi3.5:3.8b`

**Prompt 设计原则：**

- 要求以 JSON 格式返回，使用 `format="json"` 参数
- 标题翻译 Prompt 明确要求"不超过 30 字、适合用作文件名、不含特殊符号"
- 不要在一次调用里同时要求翻译 + 总结（拆开调用更可控）

### `lib/renamer.py`

- 文件名规则：`{year}_{zh_title}.pdf`，其中 `zh_title` 经过 `sanitize()` 清洗（移除 `\ / * ? : " < > |`，截断到 60 字符）
- **幂等性**：用 `MD5(文件内容前 4KB)` 作为已处理标识，存入 `.processed`（JSON 格式，`{md5: new_filename}`）。脚本每次运行先加载该文件，跳过已处理条目。
- 重名冲突：若目标路径已存在，追加 `_2`、`_3` 后缀，不覆盖。

### `lib/index_writer.py`

写入 `inbox/_index.md`，格式如下：

```markdown
## {year}\_{zh_title}

- **原标题**: {original_title}
- **来源**: {source}（crossref / pymupdf）
- **核心贡献**: {summary}
- **处理时间**: {timestamp}

---
```

- 文件不存在时自动创建，带固定 Header。
- 每次追加到文件末尾，**不重写全文**（避免并发问题）。
- 若 `config.toml` 中 `write_index = false`，跳过此步骤。

---

## config.toml 字段说明

```toml
[paths]
inbox_dir   = "~/papers/inbox"   # 监控目录
log_file    = "~/papers/organizer.log"

[llm]
enabled          = true
translate_model  = "qwen3.5:0.8b"
summary_model    = "qwen3.5:9b"
ollama_host      = "http://localhost:11434"

[behavior]
write_index      = true    # 是否写 _index.md
add_summary      = true    # 是否生成摘要（关闭后只做重命名）
crossref_timeout = 5       # CrossRef API 超时秒数
dry_run          = false   # true 时只打印，不实际操作
```

---

## 错误处理约定

- 所有模块抛出自定义异常，统一在 `organizer.py` 顶层 `try/except` 捕获
- 捕获后：写 log（级别 WARNING）+ 跳过该文件，**继续处理下一个**
- 网络超时（CrossRef）：降级到 PyMuPDF 路径，无需退出
- Ollama 不可用（ConnectionRefusedError）：降级到英文文件名，全程记录 WARNING
- 任何情况下**不修改原始 PDF 内容**，只做重命名

---

## 包管理器：uv

本项目使用 [uv](https://github.com/astral-sh/uv) 作为现代 Python 包管理器。

### 常用命令

#### 初始化和依赖管理

```bash
# 创建虚拟环境并安装依赖
uv sync

# 添加新依赖
uv add <package-name>

# 添加开发依赖
uv add --dev <package-name>

# 移除依赖
uv remove <package-name>

# 更新依赖
uv sync --upgrade
```

#### 运行项目

```bash
# 直接运行 Python 脚本
uv run python main.py

# 运行特定 Python 命令
uv run python -c "import ollama; print(ollama.__version__)"
```

#### 虚拟环境管理

```bash
# 使用 uv 运行时自动激活
uv run <command>
```

#### 测试

```bash
# 单元测试
uv run pytest tests/ -v

# 干跑（不实际重命名）
uv run python organizer.py --dry-run

# 指定单个文件调试
uv run python organizer.py --file ~/papers/10.1234_some.pdf
```
