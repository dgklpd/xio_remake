# 《蓄》Uni-app 小程序前端骨架

基于官方 Uni-app Vue 3 + TypeScript CLI 模板初始化，目标平台优先面向微信小程序。

## 当前已完成

- 使用官方推荐命令创建：`npx degit dcloudio/uni-preset-vue#vite-ts`
- 保持 `Vue 3 + <script setup> + TypeScript`
- 首页替换为《蓄》对战界面骨架
- 预置了可复用的战斗展示组件与类型定义

## 本地启动

```bash
npm install
npm run dev:mp-weixin
```

产物目录为：

```bash
dist/dev/mp-weixin
```

将该目录导入微信开发者工具即可预览。

## 发布构建

```bash
npm run build:mp-weixin
```

## 下一阶段建议

1. 接入真实对局状态：手牌、血量、蓄能量、阶段流转。
2. 把拖拽出牌和拍手判定接到战场区。
3. 按规则补充受击、粉碎、阵亡、超率升级等 CSS 动效。

## 注意

- 微信小程序 `appid` 仍需你填写到 `src/manifest.json`。
- 目前首页数据均为静态占位，便于下一步逐层替换为真实状态管理。
