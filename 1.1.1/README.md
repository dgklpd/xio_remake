# Xio 1.1.1

## 项目说明

这是 `Xio` 的 `1.1.1` 可整理发布版本，包含：

- `xu-miniapp/`
  - 微信小程序前端源码
- `backend/`
  - 结构化 Python 后端源码
- `release/`
  - `1.1.1` 版本说明文档

## 建议仓库根目录

如果你准备推到 GitHub，建议直接把当前 `1.1.1` 目录作为仓库根目录使用。

## 前端运行

进入前端目录：

```bash
cd xu-miniapp
npm install
npm run dev:mp-weixin
```

构建微信小程序：

```bash
npm run build:mp-weixin
```

## 后端运行

进入后端目录：

```bash
cd backend
pip install -r requirements.txt
python -m backend.app.api
```

默认会启动单人对战 WebSocket 服务。

## 目录说明

- `xu-miniapp/src/pages/index/index.vue`
  - 首页
- `xu-miniapp/src/pages/battle/BattlePage.vue`
  - 战斗页
- `backend/app/api.py`
  - WebSocket 服务入口
- `backend/core/rules.py`
  - 核心规则引擎
- `backend/core/basic_rules.py`
  - 基础规则与技能定义
- `release/1.1.1/版本说明书.md`
  - 本版本完整说明书
