# OCS 本地 AI 题库

给 **OCS 网课助手** 用的本地题库服务：按「本地题库 → 言溪题库 → DeepSeek」的顺序答题，命中后自动写回本地题库。刷得越多，命中率越高，AI 调用越少。

> 纯 Python 标准库实现，不需要 `pip install`，下载即用。数据全部保存在本机。

```
OCS 请求  →  本地题库（SQLite）  →  命中？直接返回
                     ↓ 未收录
              言溪题库  →  命中？返回并缓存
                     ↓ 未收录
              DeepSeek 作答  →  格式归一化  →  写回题库  →  返回 OCS
```

## 功能

- **本地题库优先**：重复题目零成本、毫秒级返回，不消耗 token
- **言溪题库上游**：你原有的言溪题库作为第二层，命中后缓存到本地，下次连言溪也不用查
- **DeepSeek 兜底**：支持 `deepseek-chat` / `deepseek-reasoner`，也兼容任意 OpenAI 格式接口
- **自动沉淀**：言溪和 AI 答过的题自动入库，支持手动修正、检索、删除
- **答案归一化**：单选题返回选项文本、多选题用 `#` 分隔、判断题返回「正确/错误」，对选项打乱更鲁棒
- **低置信度拒答**：模型没把握时返回「未找到」，避免错题污染题库
- **管理后台**：概览统计、快速测试、题库管理、导入导出、连接测试、一键复制 OCS 配置
- **零依赖**：Windows 双击 `启动.bat` 即可

## 快速开始

### 1. 启动服务

**Windows**：双击 `启动.bat`（脚本会优先使用 `py -3`，避免被 Microsoft Store 的 python 占位程序误导）

**命令行**：

```bash
py -3 app.py        # Windows
python app.py       # macOS / Linux
```

启动后会自动打开管理后台 <http://127.0.0.1:8787>，命令行窗口需要保持运行。

> 需要 Python 3.10+。如果提示找不到 Python，请到 [python.org](https://www.python.org/downloads/) 安装，安装时勾选 “Add Python to PATH”。

### 2. 配置题库来源

**DeepSeek（AI 兜底）**

1. 打开 <https://platform.deepseek.com/api_keys> 创建 Key（`sk-` 开头）
2. 进入后台「设置」→ 粘贴 Key → 保存
3. 点「测试连接」，看到「连接正常」即可

也可以不用后台，直接设置环境变量（优先级高于配置文件）：

```bash
set DEEPSEEK_API_KEY=sk-xxxx        # Windows CMD
export DEEPSEEK_API_KEY=sk-xxxx     # macOS / Linux
```

**言溪题库（可选，已有言溪题库时推荐）**

1. 在言溪题库后台拿到 token
2. 后台「设置 → 言溪题库」→ 填 Token → 打开「启用言溪题库」→ 保存

之后本地未收录的题会先查言溪：命中就直接返回，并把答案缓存进本地题库；言溪也没有时才调用 DeepSeek。

### 3. 接入 OCS

后台首页点「复制 OCS 配置」，或直接复制下面这段（默认端口 8787）：

```json
[
  {
    "name": "本地题库（言溪 + DeepSeek）",
    "homepage": "http://127.0.0.1:8787",
    "url": "http://127.0.0.1:8787/api/search",
    "method": "post",
    "type": "fetch",
    "contentType": "json",
    "headers": { "Content-Type": "application/json" },
    "data": {
      "title": "${title}",
      "options": "${options}",
      "type": "${type}"
    },
    "handler": "return (res) => res.code === 1 ? [res.question, res.answer] : [res.msg, undefined]"
  }
]
```

打开 **OCS 网课助手 → 通用 → 全局设置 → 题库配置**，粘贴、保存。然后随便答一道题验证。

> **只保留这一条配置。** 如果 OCS 里原来还配了言溪或其他题库，请删掉。OCS 会并行请求数组里的所有题库，两个答案不一致时可能随机选中其中一个；而且即使言溪已经答对，每一题仍会再调用一次 AI。本服务已经在内部按优先级串好了。

> 使用油猴脚本版 OCS 时，如果请求被拦截，需要在脚本头部加 `@connect 127.0.0.1`，或使用官方的「全域名通用版」。Chrome 插件版一般可直接访问 localhost。

## 关闭服务

- **Windows**：双击 `停止.bat`，会自动找到并结束监听 8787 的进程
- **命令行启动的**：在运行窗口按 `Ctrl+C`，或直接关闭窗口
- **确认是否已关闭**：打开 <http://127.0.0.1:8787/api/health>，打不开就是已停止
- 关闭服务不会删除题库和配置，下次双击 `启动.bat` 会接着用

> OCS 插件本身不是这个服务，它只是发起请求的浏览器扩展。如果也不想让 OCS 工作，到 `chrome://extensions` 停用它即可。

## 工作原理

OCS 通过 `${title}` / `${options}` / `${type}` 三个占位符发起请求，本服务依次尝试：

1. **精确命中**：题干归一化（去题型标签、题号、标点、空白）后查 SQLite；同时校验缓存答案是否还能匹配当前选项，选项被换掉会自动重新作答。
2. **相似题**（可选，默认关闭）：题干相似度 ≥ 94% 才命中，避免误匹配。
3. **言溪题库**：本地未收录时请求言溪，命中后直接返回并缓存；言溪的 `code=0`（未收录）会继续往下走，请求失败也只记录错误，不阻塞后面的 AI。
4. **DeepSeek**：带上题型、题干和选项请求模型，要求返回 JSON（答案 + 置信度 + 简短理由）。
5. **答案归一化**：按 OCS 的匹配规则转换答案格式。
6. **回写题库**：言溪或 AI 的答案写入本地，记录 token、耗时、来源。

### 答案格式（对应 OCS 的匹配逻辑）

| 题型 | 返回格式 | 示例 |
| --- | --- | --- |
| 单选 | 选项文本 | `光合作用` |
| 多选 | 选项文本，`#` 分隔 | `选项一#选项三` |
| 判断 | `正确` / `错误` | `正确` |
| 填空 | 多个空用 `#` 分隔 | `光合作用#叶绿体` |

> OCS 4.x 对单选题优先按「答案文本 ≈ 选项文本」匹配，因此返回选项文本比返回字母更稳；选项顺序被打乱也不会受影响。

## 题库导入

「题库」页 → 导入，支持 JSON 或 CSV。

JSON：

```json
[
  { "question": "1+1=?", "answer": "2", "type": "single" },
  { "question": "光合作用的场所是？", "answer": "叶绿体", "options": "A. 线粒体\nB. 叶绿体", "type": "single" }
]
```

CSV（表头至少包含 `question`、`answer`）：

```csv
question,answer,options,type
1+1=?,2,,single
光合作用的场所是？,叶绿体,"A. 线粒体
B. 叶绿体",single
```

字段说明：`question` / `answer` 必填，`options` / `type` / `confidence` 可选。题目会按归一化文本去重，重复导入会覆盖旧答案。

## HTTP 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/search` | OCS 题库接口，参数 `title`、`options`、`type` |
| GET | `/api/bank` | 题库列表，支持 `q`、`type`、`source`、`page`、`page_size` |
| POST | `/api/bank` | 手动新增题目 |
| PUT/DELETE | `/api/bank/{id}` | 修改 / 删除题目 |
| POST | `/api/bank/import` | 批量导入 |
| GET | `/api/bank/export?format=json\|csv` | 导出题库 |
| GET | `/api/stats` | 统计信息 |
| GET/POST | `/api/config` | 读取 / 保存配置（Key 始终打码返回） |
| POST | `/api/ping` | 测试 DeepSeek 连通性 |
| POST | `/api/test` | 快速测试一道题（不写库） |
| GET | `/api/health` | 健康检查 |

`/api/search` 返回示例：

```json
{
  "code": 1,
  "question": "中国现存规模最大的古代宫殿建筑群是？",
  "answer": "故宫",
  "source": "bank",
  "confidence": 0.95,
  "cached": true,
  "elapsed_ms": 3
}
```

未命中时返回 `{"code": 0, "msg": "原因"}`，OCS 会展示 `msg` 并跳过该题。

## 配置项

配置文件：`data/config.json`（自动生成，Key 以明文保存在本机）。

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `api_key` | 空 | DeepSeek API Key |
| `base_url` | `https://api.deepseek.com` | 兼容 OpenAI 格式的接口地址 |
| `model` | `deepseek-chat` | 模型名 |
| `temperature` | `0.2` | 越低越稳定 |
| `max_tokens` | `800` | 单次回答上限 |
| `timeout` | `60` | 请求超时（秒） |
| `ai_enabled` | `true` | AI 兜底开关 |
| `cache_enabled` | `true` | 本地题库缓存 |
| `fuzzy_match` | `false` | 相似题模糊匹配 |
| `min_confidence` | `0.3` | 低于该置信度不返回、不入库 |
| `yanxi_enabled` | `false` | 是否启用言溪题库 |
| `yanxi_token` | 空 | 言溪题库 Token |
| `yanxi_url` | `https://tk.enncy.cn/query` | 言溪接口地址 |
| `yanxi_timeout` | `15` | 言溪请求超时（秒） |
| `port` | `8787` | 监听端口 |

改端口：

```bash
python app.py --port 9000
```

改完记得把 OCS 配置里的 `8787` 全部替换成 `9000`。

## 常见问题

**OCS 提示题库请求失败 / 跨域**
先确认 <http://127.0.0.1:8787/api/health> 能打开。油猴脚本版需要 `@connect 127.0.0.1`；Chrome 插件版通常无需配置。localhost 在 Chrome 中属于安全来源，https 网课页面也能请求。

**双击 启动.bat 没反应，窗口一闪而过**
多半是 `python` 指向了 Microsoft Store 的占位程序（`WindowsApps\python.exe`，0 字节），执行会直接返回 9009。新版 `启动.bat` 已经优先使用 `py -3`，失败时会暂停并显示错误。若仍失败，打开 cmd 运行 `py -3 --version` 确认；没有 Python 就到 python.org 安装并勾选 “Add Python to PATH”。

**OCS 已经用了旧的言溪配置**
把 OCS 题库配置整段替换成首页「复制 OCS 配置」的内容，不要两条并存，否则会并行请求、答案冲突。

**答案匹配不上**
本服务返回选项文本，OCS 会做归一化匹配。图片选项、特殊标号可能失败，可在「题库」页手动改这道题的答案。

**我原来的言溪题库还要单独配置吗**
不用。在「设置 → 言溪题库」里填 Token 并启用即可，本服务会在本地未收录时自动查它。**不要在 OCS 里同时保留言溪和本服务两条配置**：OCS 会并行请求所有题库，答案冲突时可能选错，而且言溪答对时也会白调一次 AI。

**言溪题库请求失败会影响答题吗**
不会。言溪超时或 Token 失效时只会记录错误，然后继续走 DeepSeek；可以在「最近答题」里看到具体原因。

**准确率**
本地题库和言溪命中基本是准的；`deepseek-chat` 在公共课/常见教材题上大约 80–90%，冷门专业课偏低。切 `deepseek-reasoner` 更准，但每题慢 5–20 秒、费用更高。答错的题手动改一次，之后固定命中。

**费用**
每题几百 token，DeepSeek 单价很低；命中本地题库或言溪时完全不花 AI 费用。首页可以看到今日 token 消耗。

**Key / Token 安全**
DeepSeek Key 和言溪 Token 都只写入本机 `data/config.json`，接口返回时打码，不会上传到任何地方。不要分享 `data` 目录或后台截图。

**能在手机 / 平板上用吗**
服务默认只监听 `127.0.0.1`。改成 `python app.py --host 0.0.0.0` 后局域网可访问，但**没有鉴权**，不要暴露到公网；非 localhost 的 http 地址在 https 页面里会被浏览器拦截，需要反向代理加 HTTPS。

## 项目结构

```
OCSshuati/
├── app.py                  # 启动入口
├── ocs_bank/
│   ├── server.py           # HTTP 路由、静态资源
│   ├── service.py          # 答题主流程（本地 → 言溪 → DeepSeek）
│   ├── deepseek.py         # DeepSeek 调用与提示词
│   ├── yanxi.py            # 言溪题库客户端
│   ├── question.py         # 选项解析、答案归一化
│   ├── db.py               # SQLite 题库与统计
│   └── config.py           # 配置读写
├── web/                    # 管理后台（原生 HTML/CSS/JS）
├── data/                   # 运行时生成：bank.db、config.json
├── 启动.bat
├── 停止.bat
└── start.sh
```

## 参考

- [OCS 网课助手](https://docs.ocsjs.com/docs/other/api) — 题库配置协议（AnswererWrapper）
- [ocsjs-ai-answer-service](https://github.com/LynnGuo666/ocsjs-ai-answer-service)、[OcsAiAnswerer](https://github.com/wokaonb/OcsAiAnswerer) — 早期 AI 题库实现思路

本项目为独立实现，补充了本地题库、缓存校验、答案归一化、置信度拒答和管理后台。

## License

MIT
