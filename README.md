# FFmpeg Shuiyin

一个轻量级的 Web + 后端平台，利用原生 FFmpeg 实现多视频批量水印和导出。相比 ffmpeg.wasm，本项目采用轻后端架构，在 CPU 上充分利用多核心性能，并为未来的 GPU/核显加速预留接口。

## 功能特性

- ✅ 支持多种视频格式的批量导入，默认导出为 MP4，可切换 MOV/MKV/GIF/WebM
- ✅ 文字与 PNG 透明图两种水印模式，支持位置、偏移、透明度、字体等参数
- ✅ 内建线程队列，按配置自动并行跑满 CPU 核心，后续可扩展核显 / GPU
- ✅ 现代化 Web 管理台：任务提交、状态列表、日志查看、监控占位
- ✅ 轻松打包成单个可执行文件（PyInstaller），方便分发

## 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── __main__.py        # 直接运行启动 uvicorn
│   │   ├── config.py          # 配置 & 目录管理
│   │   ├── ffmpeg_queue.py    # FFmpeg 任务队列
│   │   ├── main.py            # FastAPI 路由
│   │   ├── models.py          # 队列模型
│   │   ├── schemas.py         # Pydantic schema
│   │   └── watermark.py       # 水印命令生成
│   └── requirements.txt
├── frontend/
│   ├── assets/
│   │   ├── app.js             # Web 管理台逻辑
│   │   └── styles.css         # UI 样式
│   └── index.html             # 单页应用入口
├── scripts/
│   └── build_exe.py           # PyInstaller 打包助手
├── storage/                   # 运行时会自动生成上传/输出目录
├── LICENSE
└── README.md
```

## 环境准备

- Python 3.10+
- 系统已安装 FFmpeg（`ffmpeg` 命令可用）
- 服务器建议：10 核心 / 20 线程 CPU、50GB 内存（可在高级设置中调整并行度）

### 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
pip install -r backend/requirements.txt
```

## 本地运行

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

浏览器打开 `http://localhost:8000` 即可进入管理台。

## 配置说明

- `.env`（可选）：覆盖默认配置，例如
  ```env
  FFMPEGSHUIYIN_MAX_PARALLEL_JOBS=4
  FFMPEGSHUIYIN_STORAGE=/data/ffmpegshuiyin
  FFMPEGSHUIYIN_ALLOW_GPU=true
  ```
- Web 高级设置中可以调整：
  - 并行任务数（默认 2）
  - 默认导出格式
  - 自定义 FFmpeg 二进制路径
  - GPU/核显入口已预留，后续启用即可

## 队列与性能

- 后端通过 `FFmpegQueue` 维护一个线程池，根据 `max_parallel_jobs` 自动扩容/缩容
- 每个任务可以包含多个视频文件，串行处理，日志实时写入
- 默认使用 CPU x264 编码，可通过参数选择 `h264_qsv`（核显）或 `h264_nvenc`（NVIDIA），需要在配置中开启 GPU 支持

## 打包为可执行文件

1. 安装依赖
   ```bash
   pip install pyinstaller
   ```
2. 运行脚本
   ```bash
   python scripts/build_exe.py
   ```
3. 生成的可执行文件位于 `dist/ffmpegshuiyin/`

如需自定义 `spec` 文件，可编辑 `ffmpegshuiyin.spec` 并运行：

```bash
python scripts/build_exe.py --spec path/to/ffmpegshuiyin.spec
```

## 后续规划

- GPU / 核显队列调度策略与性能可视化
- WebSocket 实时日志、进度推送
- 更丰富的水印模板与预览

欢迎在此基础上继续扩展与优化。
