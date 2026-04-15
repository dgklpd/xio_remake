# 联机房间功能文档

## 1. 功能概述

本模块为当前项目新增了完整的双人房联机后端能力，目标是支持：

- A 端创建房间
- B 端输入房间号加入
- 双端 `ready` 后开始实时对战
- 对战过程通过 WebSocket 同步出牌、回合状态与结算
- 整场对战最多进行 `30` 小局
- 小局上限达到后自动结束整场并销毁房间
- 玩家断线后可在短时间内原席位重连

本阶段未实现：

- 微信用户登录与用户库
- 持久化战绩
- 观战 / 聊天 / 排行榜

## 2. 设计原则

- 房间元数据使用 `SQLite + aiosqlite`
- 实时战斗状态保存在内存中的 `RoomSession`
- 使用 `session_token` 识别房主 / 客位身份
- 不依赖用户系统，但数据模型已预留微信用户字段
- 房间生命周期与战斗生命周期都由 `RoomManager + RoomSession` 统一调度

## 3. 当前目录结构

最终保留的联机模块文件如下：

- `backend/online/__init__.py`
  - 联机模块统一导出
- `backend/online/config.py`
  - 联机配置，包含数据库路径、房间号规则等
- `backend/online/models.py`
  - 房间、座位、身份、房间视图模型
- `backend/online/schema.sql`
  - `rooms` 表结构定义
- `backend/online/room_code.py`
  - 房间号生成、规范化、校验
- `backend/online/repository.py`
  - `SQLite` 读写封装
- `backend/online/service.py`
  - 房间服务层，处理建房、加房、ready、连接状态等
- `backend/online/manager.py`
  - 房间内存管理器，维护 `room_code -> RoomSession`
- `backend/online/session.py`
  - 单个双人房的实时战斗会话、广播、终局、断线重连
- `backend/online/init_db.py`
  - 初始化联机数据库
- `backend/online/data/rooms.sqlite3`
  - 联机房间数据库文件
- `backend/online/README.md`
  - 当前文档

本次同时修改的现有文件：

- `backend/app/api.py`
  - 接入联机 HTTP / WebSocket 接口
- `backend/requirements.txt`
  - 新增联机与测试依赖

## 4. 数据库设计

当前仅使用一张主表：`rooms`

关键字段包括：

- `room_code`
- `status`
- `host_token`
- `guest_token`
- `host_user_id`
- `guest_user_id`
- `host_name`
- `guest_name`
- `host_avatar`
- `guest_avatar`
- `host_connected`
- `guest_connected`
- `host_ready`
- `guest_ready`
- `created_at`
- `updated_at`
- `expires_at`

说明：

- `host_user_id / guest_user_id` 当前允许为空，后续可直接接微信 `openid / unionid`
- `host_token / guest_token` 是当前联机身份识别的核心

## 5. 运行时结构

### 5.1 RoomRepository

负责：

- 初始化 `SQLite` 表
- 建房 / 加房 / 查询房间
- 更新房间状态
- 更新连接状态
- 更新 `ready` 状态
- 删除过期房间

### 5.2 OnlineRoomService

负责：

- 建房
- 加房
- 查询房间状态
- 设置房间状态
- 设置 `ready`
- 设置连接状态
- 离房 / 关房

### 5.3 RoomManager

负责：

- 管理内存中的 `RoomSession`
- 为每个房间分配单独的实时会话
- 房间关闭后回收内存 session

### 5.4 RoomSession

负责：

- 双端连接注册 / 断开
- `ready` 状态同步
- 对战开始
- 出牌同步
- 超时补默认牌
- 回合结算
- 30 小局终局
- 房间结束广播
- 断线重连与超时关闭

## 6. 房间与战斗状态

### 6.1 房间状态

- `waiting`
  - 房间已创建，等待客人加入
- `full`
  - 双方已在房间，等待开始
- `playing`
  - 联机对战中
- `finished`
  - 整场对战已结束
- `closed`
  - 房间已关闭

### 6.2 战斗限制

- 整场最多 `30` 小局
- 每个小局内部沿用现有规则引擎回合推进
- 一旦小局累计达到 `30`
  - 发送 `battle_finished`
  - 房间状态切到 `finished`
  - 再发送 `room_closed`
  - 删除房间并回收 session

## 7. 新开放接口

### 7.1 HTTP 接口

#### `POST /online/rooms`

创建房间。

请求体：

```json
{
  "identity": {
    "display_name": "Host",
    "avatar_url": "",
    "auth_provider": "guest",
    "external_user_id": null,
    "is_guest": true
  }
}
```

返回：

- `seat`
- `session_token`
- `room`

#### `POST /online/rooms/{room_code}/join`

加入房间。

请求体结构与建房相同。

返回：

- `seat`
- `session_token`
- `room`

#### `GET /online/rooms/{room_code}`

查询房间当前状态。

#### `POST /online/rooms/{room_code}/ready`

设置 `ready` 状态。

请求体：

```json
{
  "seat": "host",
  "ready": true
}
```

#### `POST /online/rooms/{room_code}/leave`

主动离房。

请求体：

```json
{
  "seat": "guest"
}
```

### 7.2 WebSocket 接口

#### `ws /ws/online/rooms/{room_code}?seat=host|guest&session_token=...`

联机对战主 WebSocket。

连接时必须携带：

- `room_code`
- `seat`
- `session_token`

#### 客户端可发送动作

- `ping`
- `ready_room`
- `play_card`
- `restart_match`
- `get_room_state`

#### 服务端会推送动作

- `room_state`
- `battle_state`
- `round_resolved`
- `battle_finished`
- `player_disconnected`
- `player_reconnected`
- `room_closed`
- `error`

## 8. 重连机制

当前实现的断线重连规则：

- 玩家断线时不会立即离房
- 服务端会将该座位标记为 `connected = false`
- 同时广播：
  - `room_state`
  - `player_disconnected`
- 默认重连宽限时间：`60 秒`
- 玩家在宽限期内用原 `seat + session_token` 重连：
  - 取消断线计时器
  - 恢复 `connected = true`
  - 重连方收到当前 `room_state`
  - 如果战斗中，重连方还会收到当前 `battle_state`
  - 其他玩家会收到 `player_reconnected`
- 超时未回来：
  - 广播 `room_closed`
  - 原因 `reconnect_timeout`
  - 删除数据库房间
  - 清理内存 session

## 9. 与现有单机模式的关系

当前单机 WebSocket 入口仍保留：

- `ws /ws/battle`

联机能力是新增的一套并行系统，不会覆盖单机模式。

两者共享：

- 规则引擎
- 卡牌元数据序列化逻辑
- 战斗状态结构

## 10. 本次综合测试结果

本次已经完成完整联机后端全链路回归，覆盖：

- 房间创建
- 房间加入
- 房间状态查询
- 双端 `ready`
- 联机战斗启动
- 双端出牌同步
- 回合结算广播
- 30 小局终局
- 房间结束与销毁
- 断线后宽限期内重连恢复
- 超时未重连自动关闭

本次执行通过的验证包括：

- 编译检查：`python -m compileall backend/app backend/online`
- 房间 API 闭环测试：通过
- 联机战斗同步测试：通过
- 30 小局终局测试：通过
- 断线重连成功 / 超时关闭测试：通过

关键结果摘要：

- `can_start_after_both_ready = True`
- `battle_started = True`
- `round_resolved = True`
- `match_finished = True`
- `host_battle_finished_winner = self`
- `guest_battle_finished_winner = enemy`
- `host_observed_reconnect = True`
- `room_closed_for_timeout = True`

## 11. 后续建议

下一阶段建议优先开始前端联机接入：

- 房间创建页
- 房间加入页
- 房间等待页
- 联机战斗页接入新 WS
- `session_token / room_code / seat` 的本地缓存与重连逻辑

如果后续要接微信用户系统，建议新增 `backend/users/` 模块，并把 `PlayerIdentity` 与微信登录结果进行绑定即可，无需推翻当前联机房间结构。
