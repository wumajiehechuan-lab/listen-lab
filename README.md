# 精听 · 英语听读素材库

一个本地部署的英语听读素材生成与管理 Web 应用：上传一段英文视频，自动完成语音识别转写（句级英文字幕）、AI 翻译与重点词提取，生成「左屏视频 + 下屏字幕 + 右栏词汇」的精听听读页面，并支持将页面合成导出为独立视频。

## ✨ 功能特性

- **视频导入**：独立导入窗口，选择文件夹后上传视频，后台流水线自动生成素材
- **精听听读页面**（Apple 风格三栏版式）：
  - 左侧**视频栏** —— 冻结固定，不随鼠标滚动
  - 底部**字幕栏** —— 句级英文字幕 + 中文对照，可独立滚动；播放时当前句高亮并自动滚动定位
  - 右侧**词汇栏** —— 重点单词卡片，可点击跳转到对应播放位置
- **字幕同步**：随视频播放，字幕光标高亮移动；重点词在字幕中蓝色加粗下划线提亮
- **页面导出为视频**：ffmpeg + Pillow 将精听页面逐帧合成为独立 MP4，英文字幕/重点词/词汇栏随播放同步提亮，可下载
- **数据持久化**：SQLite 存储文件夹、素材、字幕、重点词，刷新与重启不丢失
- **树状文件导航**：左侧文件夹树，支持新建 / 重命名 / 删除文件夹与素材
- **模型接入配置页**：页面内可视化配置，无需手改 `.env`；LLM 侧支持多服务商预设一键切换

## 🖥️ 页面版式

```
┌─────────────────────────────────────────────────────────────┐
│  精听 · 英语听读素材库        [＋导入] [导出] [模型设置]      │
├─────────────┬──────────────────────────────────┬─────────────┤
│  素材库     │  视频栏（冻结，不随滚动）          │  核心词汇   │
│  ├ 每日新闻 │                                  │  affecting  │
│  └ 精听素材 │  ┌────────────────────────────┐  │  breach     │
│              │  │      （视频画面）          │  │  hackers    │
│  （文件夹    │  └────────────────────────────┘  │  operate    │
│  树导航）    │  ┌────────────────────────────┐  │             │
│              │  │  字幕栏（可滚动，随播放高亮）│  │             │
│              │  └────────────────────────────┘  │             │
└─────────────┴──────────────────────────────────┴─────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd listen-lab

# 创建虚拟环境（任选其一）
uv venv                     # 优先推荐
conda create -n listen-lab python=3.10

# 安装 Python 依赖
# （conda 环境下保持 .venv 以外的解释器激活后再执行 uv pip install）
uv pip install -r requirements.txt
```

> 桌面端（Windows）还需确保 `ffmpeg` 已加入 PATH；系统级 / C 库依赖（如需）用 conda 安装。

### 2. 配置模型

复制并编辑 `.env`，填入 API 密钥（也可在 Web 页面「模型设置」中可视化配置，保存即时生效，无需重启）：

```ini
# 火山引擎语音识别（录音文件识别极速版，视频转录用）
VOLC_APP_ID=your_volc_app_id
VOLC_ACCESS_TOKEN=your_volc_access_token

# LLM（OpenAI 兼容接口，翻译 + 重点词提取用）
LLM_PROVIDER=deepseek
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

**LLM 服务商预设**（网页「模型设置 → 大语言模型」下拉切换）：

| 预设 | Base URL | 默认模型 | 说明 |
|---|---|---|---|
| DeepSeek 官方 | `https://api.deepseek.com` | `deepseek-chat` | 按量计费 |
| 火山方舟 Coding Plan | `https://ark.cn-beijing.volces.com/api/coding/v3` | `doubao-seed-2.0-code` | 包月套餐，适合素材较多的场景 |
| 阿里百炼 Coding Plan | `https://coding.dashscope.aliyuncs.com/v1` | （手填） | 注意官方条款限制应用后端调用 |
| 腾讯混元 | `https://api.hunyuan.cloud.tencent.com/v1` | `hunyuan-lite` | 按量计费 |
| 自定义 | 任意 OpenAI 兼容端点 | 任意 | 可接入任何兼容服务 |

> 语音识别（ASR）需单独开通火山引擎按量服务，Coding Plan 不含 ASR。

### 3. 启动服务

```bash
python run.py
```

浏览器打开 <http://127.0.0.1:8000>。

### 4. 使用

1. 点右上角「＋ 导入视频」→ 选择文件夹、上传英文视频，等待自动生成（转录 + 翻译 + 重点词）
2. 在左侧素材树中点击素材打开精听页面
3. 播放视频，字幕随播放高亮；点击字幕 / 单词卡可跳转
4. 点「导出视频」将页面合成为独立 MP4，随后「下载 MP4」保存

## 📁 核心文件结构

```
listen-lab/
├── run.py                     # 启动入口
├── requirements.txt           # Python 依赖
├── .env                       # API 密钥与服务商配置
├── app/
│   ├── main.py                # FastAPI 应用与路由挂载
│   ├── config.py              # 运行时配置（含页面设置写入）
│   ├── database.py            # SQLite 会话
│   ├── models.py              # 数据模型（文件夹/素材/字幕/重点词）
│   ├── api/
│   │   ├── tree.py            # 文件夹树导航 API
│   │   ├── materials.py       # 素材详情 / 上传 / 状态
│   │   ├── export.py          # 导出合成视频 / 下载
│   │   └── settings.py        # 模型配置读取与保存
│   └── services/
│       ├── pipeline.py        # 素材生成流水线编排
│       ├── asr.py             # 火山语音识别（句级时间戳）
│       ├── llm.py             # 翻译 + 重点词提取（OpenAI 兼容）
│       └── video_export.py    # 精听页面合成导出视频
├── static/                    # 前端（原生 HTML/CSS/JS）
│   ├── index.html
│   ├── css/style.css          # Apple 风格样式
│   └── js/                    # app / player / upload / settings
└── data/                      # SQLite 数据库与媒体/导出文件
```

## 🛠️ 技术栈

- **后端**：FastAPI + uvicorn + SQLAlchemy（SQLite）
- **前端**：原生 HTML / CSS / JavaScript（无前端框架）
- **语音识别**：火山引擎录音文件识别（句级时间戳）
- **LLM**：OpenAI 兼容接口（DeepSeek / 火山方舟 / 阿里百炼 / 腾讯混元）
- **视频合成**：Pillow 帧渲染 + ffmpeg
- **界面风格**：Apple / HIG 设计 tokens

## ⚠️ 说明

- 生成素材、导出视频均为本地后台任务，耗时取决于视频长度与 API 响应
- 所有 API 密钥仅存于本地 `.env`，不出现在代码或日志中