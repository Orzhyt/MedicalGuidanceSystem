# 医疗挂号系统

基于 FastAPI 的医疗挂号模拟服务，覆盖 **医院 → 科室 → 医生 → 时段 → 预约** 的完整链路。
支持查询医院/医生列表、查询可预约时段、创建预约（含冲突处理）、查询/取消预约。

运行时使用 **内存 SQLite**，每次启动回到干净的演示状态（重启归零）；`data/medical.db` 仅作参考快照，运行时不读写。

---

## 功能特性

- **接口1**：查询 医院-科室-医生 树状列表（可查全部或单个医院）。
- **接口2**：查询某医生未来两周可预约时段，返回每个时段的号源容量、已约数、剩余数、是否约满。
- **接口3**：根据 `医生id + 日期 + 时段` 创建预约；若冲突（已约满 / 非法时段 / 超出窗口）则失败，并返回当前可预约时段列表。
- **接口4**：根据预约 id 查询预约详情（含医院-科室-医生-时间-患者）。
- **接口5**：`DELETE` 取消预约（软取消，立即释放号源）。
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
python main.py
```

启动后：

- 服务地址：`http://127.0.0.1:8000`
- 交互式 API 文档（Swagger UI）：`http://127.0.0.1:8000/docs`
- ReDoc 文档：`http://127.0.0.1:8000/redoc`

每次启动在内存中建表并播种示例数据；**停止服务即清空**，再次启动回到初始状态。API 写入不会落盘，也不会修改 `data/medical.db`。

---

## 数据模型

| 表 | 说明 | 关键字段 |
|---|---|---|
| `hospitals` | 医院 | id, name, level(等级), address, phone |
| `departments` | 科室 | id, hospital_id(FK), name, description |
| `doctors` | 医生 | id, department_id(FK), name, title(职称), specialty |
| `schedules` | 每周排班规则 | id, doctor_id(FK), weekday(0=周一…6=周日), start_time, end_time, capacity(号源数), demo_booked(演示预占号数) |
| `appointments` | 预约 | id, doctor_id(FK), slot_date, start_time, end_time, patient_name, patient_phone, status, created_at |

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
  "start_time": "08:00:00",
  "patient_name": "张三",
  "patient_phone": "13900000002"
}
```

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
    "start_time": "08:00:00",
    "end_time": "12:00:00",
    "patient_name": "张三",
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
| 日期早于明天 | `预约日期不能早于明天` |
| 日期超出两周窗口 | `预约日期超出可预约窗口（YYYY-MM-DD）` |
| 时段不在排班规则中 | `该时段不在医生的排班规则中` |
| 时段已约满 | `该时段已约满，请选择其他时段` |

### 接口4：查询预约详情

```
GET /api/appointments/{appointment_id}
```

返回该预约的医院-科室-医生-时间-患者完整信息；不存在则 `404`。

### 接口5：取消预约

```
DELETE /api/appointments/{appointment_id}
```

软取消：将 `status` 置为 `cancelled`，立即释放该时段号源（因余号只统计 `confirmed`）。返回更新后的预约详情（`status=cancelled`）；不存在则 `404`；已取消则原样返回（幂等）。

---

## 可预约窗口说明

- 窗口由 `app/crud.py` 的 `booking_window()` 计算：**起点 = 系统日期 + 1 天（明天），终点 = 起点 + 13 天**，共 14 天。
- 接口2 的时段列表与接口3 的预约校验都基于此窗口，每次请求按当前系统时间实时计算。
- 因此**今天不可预约**，最早可约日期为明天。

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

启动服务后，可用浏览器打开 `http://127.0.0.1:8000/docs` 直接在线测试全部接口；或用 curl：

```bash
# 查询医院树
curl http://127.0.0.1:8000/api/hospitals

# 查询医生1的两周时段
curl http://127.0.0.1:8000/api/doctors/1/slots

# 创建预约
curl -X POST http://127.0.0.1:8000/api/appointments \
  -H "Content-Type: application/json" \
  -d '{"doctor_id":1,"slot_date":"2026-10-01","start_time":"08:00:00","patient_name":"张三","patient_phone":"13900000002"}'

# 查询预约
curl http://127.0.0.1:8000/api/appointments/1

# 取消预约
curl -X DELETE http://127.0.0.1:8000/api/appointments/1
```
