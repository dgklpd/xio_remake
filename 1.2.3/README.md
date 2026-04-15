# Xio 1.2.3

## 项目简介
`Xio` 是一款以“出牌 + 装备”规则为核心的对战小游戏，包含微信小程序前端与 Python 后端。本版本加入联机大厅与房间式联机流程，支持创建房间、加入房间、准备与开战、对战结束自动销毁房间。

## 目录结构
- `xu-miniapp/`  
  微信小程序前端源码（UniApp + Vue）。
- `backend/`  
  Python 后端源码（FastAPI + WebSocket + SQLite）。
- `release/1.2.3/版本说明书.md`  
  版本说明与新增功能清单。

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

默认启动 HTTP + WebSocket 服务。

## 页面索引（关键入口）
- `xu-miniapp/src/pages/index/index.vue`  
  首页入口。
- `xu-miniapp/src/pages/online/lobby/index.vue`  
  联机大厅页（房间列表 / 创建 / 加入）。
- `xu-miniapp/src/pages/battle/BattlePage.vue`  
  对战页（含联机等待弹窗）。
