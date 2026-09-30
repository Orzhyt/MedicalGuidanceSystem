# 医疗挂号系统

基于 FastAPI 的医疗挂号模拟服务，覆盖 **医院 → 科室 → 医生 → 时段 → 预约** 的完整链路。
支持查询医院/医生列表、查询可预约时段、创建预约（含冲突处理）、查询/取消预约。

运行时使用 **内存 SQLite**，每次启动回到干净的演示状态（重启归零）；`data/medical.db` 仅作参考快照，运行时不读写。

---

## 功能特性

- **接口1**：查询 医院-科室-医生 树状列表（可查全部或单个医院）。
- **接口2**：查询某医生未来两周可预约时段，返回每个时段的号源容量、已约数、剩余数、是否约满。
- **接口3**：根据 `医生id + 日期 + 时段 + 病人编号` 创建预约；若冲突（已约满 / 非法时段 / 超出窗口）则失败，并返回当前可预约时段列表。
- **接口4**：按 `patient_id` 查询某病人的全部预约（只需病人 id）。
- **接口5**：取消预约，需 `预约id + 病人id` 且归属匹配才允许取消（软取消，立即释放号源）。
- **动态可预约窗口**：按系统时间计算，范围为 **明天起 14 天**，课程中任意日期运行都适用。
- **演示满号**：排班规则上预置 `demo_booked`，使每个医生都有几个"按时段"满号的规则（不绑定某一天，窗口内所有匹配日期都满），方便演示冲突。
- **重启归零**：运行时为内存库，API 写入只在本次会话生效；重启服务即恢复初始演示状态，不会累积脏数据。

---

## 技术栈

| 组件 | 版本要求 |
|---|---|
| Python | 3.11+ |
| FastAPI | ≥0.110 |
| Uvicorn | ≥0.27 |
| SQLAlchemy | ≥2.0 |
| Pydantic | v2（随 FastAPI 安装） |
| 数据库 | SQLite（运行时内存；`data/medical.db` 为参考快照） |

---

## 项目结构

```
MedicalGuidanceSystem/
├── main.py                  # FastAPI 入口，启动时建表 + 播种（内存库）
├── requirements.txt         # 依赖清单
├── .gitignore
├── data/
│   └── medical.db           # 参考快照（运行时不使用，由 scripts/export_db.py 生成）
├── scripts/
│   └── export_db.py         # 生成 data/medical.db 快照（手动运行）
├── static/
│   └── schedule.html        # 医生排期可视化页面（/schedule）
└── app/
    ├── database.py          # 内存引擎 / 会话 / Base / get_db
    ├── models.py            # ORM：Hospital/Department/Doctor/Schedule/Appointment
    ├── schemas.py           # Pydantic 请求/响应模型
    ├── crud.py              # 业务逻辑 + 可预约窗口 + 取消
    ├── seed.py              # 示例数据播种（含 demo_booked 满号）
    └── routers/
        ├── hospitals.py     # 接口1：医院-科室-医生树
        ├── doctors.py       # 接口2：医生可预约时段
        └── appointments.py  # 接口3/4/5：创建/查询/取消预约
```

---

## 环境准备

```bash
pip install -r requirements.txt
```

> 也可直接 `pip install "fastapi[standard]" uvicorn sqlalchemy`。

---

## 启动

```bash
python main.py                 # 默认 127.0.0.1:9090，可预约窗口起点=明天
python main.py --port 8080     # 自定义端口
PORT=8080 python main.py       # 用环境变量 PORT 自定义端口
python main.py --start-date 2026-10-10        # 指定可预约窗口起始日期
START_DATE=2026-10-10 python main.py          # 用环境变量指定起始日期
python main.py --host 0.0.0.0 --port 9090 --no-reload
```

启动后：

- 服务地址：`http://127.0.0.1:9090`
- 交互式 API 文档（Swagger UI）：`http://127.0.0.1:9090/docs`
- ReDoc 文档：`http://127.0.0.1:9090/redoc`
- **医生排期可视化页面**：`http://127.0.0.1:9090/schedule`

端口默认 9090，可通过 `--port` 参数或 `PORT` 环境变量覆盖；地址可通过 `--host` 或 `HOST` 环境变量覆盖；**可预约窗口起始日期**可通过 `--start-date` 或 `START_DATE` 环境变量指定（格式 `YYYY-MM-DD`），默认为启动当天的次日。启动时控制台会打印实际采用的起点。

每次启动在内存中建表并播种示例数据；**停止服务即清空**，再次启动回到初始状态。API 写入不会落盘，也不会修改 `data/medical.db`。

---

## 排期可视化页面

启动后浏览器访问 **`http://127.0.0.1:9090/schedule`**（端口随启动参数变化）即可打开排期查看页。该页面为**只读**，无需登录，不调用任何写接口。

### 功能概述

按 **医院 → 科室 → 医生** 逐级钻取，直观查看每位医生未来两周（明天起 14 天）的排期与余号，方便一眼看清哪个时段可约、哪个已满。

### 操作流程

1. 页面顶部"医院"下拉框自动加载所有医院（数据来自 `/api/hospitals`）。
2. 选择医院后，"科室"下拉框联动填充该院科室，并附"全部科室"选项。
3. 选择具体科室 → 展示该科室医生；选"全部科室" → 展示该院全部医生。
4. 每位医生渲染为一张卡片，含一张**两周日历网格**（周一~周日 × 2 周），按日历对齐到本周一。网格上方标题显示可预约窗口起止日期（含年），每个单元格显示"月/日"并以内含色块标注时段。

### 色块含义

日历每个单元格代表一天，内含上午（08:00-12:00）、下午（14:00-17:00）两个色块：

| 颜色 | 含义 | 判定 |
|---|---|---|
| 🟩 绿色 | 可约（余号充足） | `available == capacity` |
| 🟨 黄色 | 部分已约（仍有余号） | `0 < available < capacity` |
| 🟥 红色 | 已满 | `available == 0` |
| ⬜ 灰色 | 无排班 / 不在可预约窗口 | 该日无排班规则或日期超出窗口 |

> 鼠标悬停色块可查看时段、容量、已约、剩余等明细。卡片标题显示该医生"可约 X/Y 个时段"汇总。页面顶部有图例。

### 数据来源与刷新

- 医院/科室/医生列表：`GET /api/hospitals`（页面加载时拉取一次）。
- 每位医生时段：`GET /api/doctors/{id}/slots`（选定范围后并发拉取）。
- 反映的是当前可预约窗口（明天起 14 天），含 `demo_booked` 演示满号；窗口与满号随系统时间动态计算，无需改页面。
- 页面不缓存，每次选择都实时请求后端。

### 技术说明

- 纯前端 HTML + CSS + 原生 JS（`fetch`），无前端框架、无构建步骤、无额外依赖。
- 用相对路径 `/api/...` 调用后端，因此**任意端口/主机启动都能直接用**。
- 由 `main.py` 的 `GET /schedule` 通过 `FileResponse` 返回 `static/schedule.html`；未在 OpenAPI 文档中暴露（`include_in_schema=False`）。

---

## 数据模型

| 表 | 说明 | 关键字段 |
|---|---|---|
| `hospitals` | 医院 | id, name, level(等级), address, phone |
| `departments` | 科室 | id, hospital_id(FK), name, description |
| `doctors` | 医生 | id, department_id(FK), name, title(职称), specialty |
| `schedules` | 每周排班规则 | id, doctor_id(FK), weekday(0=周一…6=周日), start_time, end_time, capacity(号源数), demo_booked(演示预占号数) |
| `appointments` | 预约 | id, doctor_id(FK), slot_date, start_time, end_time, patient_id(病人编号), status, created_at |

**排班设计**：`schedules` 存"每周几的某时段放多少号"，不绑定具体日期；查询时按当前可预约窗口动态展开成具体时段。某时段余号 = `capacity - (真实已确认预约数 + demo_booked)`。

**演示满号**：`demo_booked` 是排班规则上的属性（按时段而非具体日期），窗口内每个匹配该 weekday+时段 的日期都会显示已占 `demo_booked` 个号。因此满号不会"过期"，任意日期运行都有效。

---

## 接口说明

### 接口1：查询 医院-科室-医生 列表

```
GET /api/hospitals                  # 全部医院（嵌套科室与医生）
GET /api/hospitals/{hospital_id}    # 单个医院
```

响应示例（节选）：

```json
[
  {
    "id": 1,
    "name": "云岭省星海市第一人民医院",
    "level": "三甲",
    "address": "云岭省星海市星海区人民路1号",
    "phone": "0571-88001000",
    "departments": [
      {
        "id": 1,
        "name": "内科",
        "doctors": [
          { "id": 1, "name": "张建国", "title": "主任医师", "specialty": "心血管内科" }
        ]
      }
    ]
  }
]
```

### 接口2：查询医生可预约时段（默认两周）

```
GET /api/doctors/{doctor_id}/slots?days=14
```

- `days`：查询未来天数，默认 14，范围 1~30；起点固定为**明天**。

响应示例（节选）：

```json
{
  "doctor": { "id": 1, "name": "张建国", "title": "主任医师", "specialty": "心血管内科" },
  "days": 14,
  "available_count": 6,
  "slots": [
    {
      "slot_date": "2026-10-01",
      "weekday": 3,
      "start_time": "08:00:00",
      "end_time": "12:00:00",
      "capacity": 3,
      "booked_count": 0,
      "available": 3,
      "is_full": false
    },
    {
      "slot_date": "2026-10-05",
      "weekday": 0,
      "start_time": "08:00:00",
      "end_time": "12:00:00",
      "capacity": 3,
      "booked_count": 3,
      "available": 0,
      "is_full": true
    }
  ]
}
```

> `booked_count` 已包含 `demo_booked` 演示预占。

### 接口3：创建预约

```
POST /api/appointments
```

请求体：

```json
{
  "doctor_id": 1,
  "slot_date": "2026-10-01",
  "start_time": "14:00:00",
  "patient_id": "P20260001"
}
```

**请求字段说明**：

| 字段 | 含义 | 备注 |
|---|---|---|
| `doctor_id` | 医生 id | 从接口1获取 |
| `slot_date` | 预约日期 | 必须在可预约窗口内（明天起 14 天） |
| `start_time` | **时段选择器**，指定当天约哪个时段 | 只能取 `"08:00:00"`（上午）或 `"14:00:00"`（下午），且必须在该医生当天的排班里 |
| `patient_id` | 病人编号/病历号 | 关联病人，不再使用姓名/电话 |

> **关于 `start_time`**：同一位医生同一天可能有上午、下午两个时段，光给 `doctor_id + slot_date` 无法确定约哪个号，必须用 `start_time` 指定。三者组合 `(doctor_id, slot_date, start_time)` 定位唯一号源，系统按 `slot_date` 的星期几 + `start_time` 匹配该医生的排班规则得到容量并校验。**建议先调接口2 `GET /api/doctors/{id}/slots` 拿到可选的 `slot_date + start_time`，再据此下单**，避免传错时段（如把上午时间传到只有下午班的日子）。传了不存在的时段会返回 `该时段不在医生的排班规则中`。

**成功响应**：

```json
{
  "success": true,
  "message": "预约成功",
  "appointment": {
    "id": 1,
    "hospital_name": "云岭省星海市第一人民医院",
    "department_name": "内科",
    "doctor_name": "张建国",
    "slot_date": "2026-10-01",
    "start_time": "14:00:00",
    "end_time": "17:00:00",
    "patient_id": "P20260001",
    "status": "confirmed"
  },
  "available_slots": []
}
```

**冲突响应**（已约满 / 非法时段 / 超出窗口）：`success=false`，`appointment=null`，并在 `available_slots` 返回当前可预约时段。

```json
{
  "success": false,
  "message": "该时段已约满，请选择其他时段",
  "appointment": null,
  "available_slots": [ /* 当前可预约时段列表 */ ]
}
```

可能的失败 `message`：

| 场景 | message |
|---|---|
| 医生不存在 | `医生不存在: id=...` |
| 日期早于窗口起点 | `预约日期不能早于可预约起始日（YYYY-MM-DD）` |
| 日期超出两周窗口 | `预约日期超出可预约窗口（YYYY-MM-DD）` |
| 时段不在排班规则中 | `该时段不在医生的排班规则中` |
| 该病人已约过该时段 | `该时段已预约过，不能重复提交` |
| 时段已约满 | `该时段已约满，请选择其他时段` |

### 接口4：按病人编号查询预约

```
GET /api/appointments?patient_id={patient_id}
```

返回该病人的全部预约（按 slot_date, start_time 排序）；无预约则返回空数组。

```json
[
  {
    "id": 1,
    "hospital_name": "云岭省星海市第一人民医院",
    "department_name": "内科",
    "doctor_name": "张建国",
    "slot_date": "2026-10-01",
    "start_time": "14:00:00",
    "end_time": "17:00:00",
    "patient_id": "P20260001",
    "status": "confirmed"
  }
]
```

> 查询只需 `patient_id`，返回该病人全部预约的完整信息（含医院-科室-医生-时间-状态）。已无"按预约 id 查详情"的接口。

### 接口5：取消预约

```
DELETE /api/appointments?appointment_id={appointment_id}&patient_id={patient_id}
```

预约 id 与病人 id **都放在 query 参数**，且二者归属匹配才允许取消（防止取消他人预约）：

- 预约不存在 → `404`。
- `patient_id` 与该预约的归属不匹配 → `403 无权取消: patient_id 与该预约不匹配`。
- 匹配则软取消：`status` 置为 `cancelled`，立即释放该时段号源（余号只统计 `confirmed`）；返回更新后的预约详情；已取消则原样返回（幂等）。

---

## 可预约窗口说明

- 窗口由 `app/crud.py` 的 `booking_window()` 返回：**起点**为启动时确定的日期，**终点 = 起点 + 13 天**，共 14 天。
- **起点在启动时固定一次**，之后不再随系统日期变化：
  - 默认 = 启动当天的次日（明天）。
  - 可通过 `--start-date YYYY-MM-DD` 或环境变量 `START_DATE` 指定任意一天为起点。
- **不重启服务时窗口保持不变**：即便跨到第二天、第三天，可预约窗口仍以启动时设定的起点为准，不会自动滚动。需要切换窗口请重启服务（可再带新的 `--start-date`）。
- 接口2 的时段列表与接口3 的预约校验都基于此窗口。
- 因此默认情况下**启动当天不可预约**，最早可约日期为次日；若显式指定了 `--start-date`，则以该日期为最早可约日。

---

## 示例数据说明

启动时 `app/seed.py` 会写入：

- 3 家三甲医院（虚构省市 **云岭省星海市**）：第一人民医院、市中心医院、第二人民医院。
- 8 个科室（内科、外科、妇产科、骨科、神经内科、儿科等）。
- 9 名医生（主任/副主任/主治医师，各有专长）。
- 每名医生的每周排班规则（上午 08:00-12:00 / 下午 14:00-17:00，号源容量 2~6 不等）。
- 演示满号（`demo_booked`）覆盖全部 9 名医生、共 17 个时段规则，每人 1-2 个：

| 医生 | 满号时段（窗口内每个匹配日期都满） |
|---|---|
| 张建国 | 周一上午、周三上午 |
| 李慧敏 | 周二上午、周四上午 |
| 王志强 | 周二上午、周三下午 |
| 赵丽华 | 周一下午、周五下午 |
| 陈伟民 | 周二上午、周四上午 |
| 刘海洋 | 周二下午 |
| 周明 | 周一上午、周四上午 |
| 吴小燕 | 周三上午、周一下午 |
| 孙建华 | 周一上午满、周五上午 5/6（剩1） |

---

## 持久化与重启

- **运行时**：内存 SQLite（`sqlite://` + `StaticPool`），所有表与数据在内存中；停止服务即清空。
- **重启归零**：每次启动重新建表 + 播种，API 在上次会话写入的预约不会保留。适合课程演示：每次都是一致的初始状态。
- **参考快照** `data/medical.db`：运行时不使用，仅提交到 git 作为默认数据的参考。由 `scripts/export_db.py` 生成（含基础数据 + 排班含 `demo_booked`，无预约行，日期无关、永不过期）。
- **修改默认数据**：编辑 `app/seed.py` 后运行 `python scripts/export_db.py` 刷新快照并提交。运行时服务不受影响（用内存库）。

---

## 快速验证

启动服务后，可用浏览器打开 `http://127.0.0.1:9090/docs` 直接在线测试全部接口；或用 curl：

```bash
# 查询医院树
curl http://127.0.0.1:9090/api/hospitals

# 查询医生1的两周时段
curl http://127.0.0.1:9090/api/doctors/1/slots

# 创建预约（只需病人编号 patient_id；start_time 必须是医生当天排班里的时段）
curl -X POST http://127.0.0.1:9090/api/appointments \
  -H "Content-Type: application/json" \
  -d '{"doctor_id":1,"slot_date":"2026-10-01","start_time":"14:00:00","patient_id":"P20260001"}'

# 按病人编号查询其预约（只需 patient_id）
curl "http://127.0.0.1:9090/api/appointments?patient_id=P20260001"

# 取消预约（预约id + 病人id 均放query，归属匹配才取消）
curl -X DELETE "http://127.0.0.1:9090/api/appointments?appointment_id=1&patient_id=P20260001"
```
