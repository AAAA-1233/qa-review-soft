# 问答数据集智能审核平台

一个基于计划书实现的前后端工作台，覆盖项目管理、导入识别、人工审核、AI 任务、Prompt、统计、导出和设置入口。

## 运行

```powershell
cd backend
C:\Users\28595\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pip install -r requirements.txt
C:\Users\28595\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
cd frontend
npm install
npm run build
npm run preview -- --port 4173
```

打开 `http://127.0.0.1:4173/`。

## 已实现

- React + TypeScript + Vite 前端骨架
- FastAPI + SQLite + SQLAlchemy 后端
- 项目管理与新建项目向导
- 数据集解析、字段识别和 ZIP 索引服务
- 图片问答样本审核台
- PASS / FAIL / SKIP / UNREVIEWED 状态
- 快捷键：`A`、`D`、`S`、方向键、`Space`、`Ctrl + Z`
- 审核结果写入 SQLite
- AI Provider 预设、自定义 Base URL、自定义模型名
- OpenAI-compatible / Anthropic Messages / Gemini generateContent 协议层
- AI 批量审核任务、暂停和继续
- Prompt 模板变量页
- 统计、导出和设置页面，导出 JSONL
- 桌面与移动响应式布局

## 后续接入边界

- WebSocket AI 进度
- Tauri Windows EXE 打包
