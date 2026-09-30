# 医疗挂号系统

基于 FastAPI 的医疗挂号模拟服务，覆盖 **医院 → 科室 → 医生 → 时段 → 预约** 的完整链路。
支持查询医院/医生列表、查询医生可预约时段、创建预约（含时间冲突处理）、查询预约详情，使用 SQLite 持久化。

---

## 功能特性

- **接口1**：查询 医院-科室-医生 树状列表（可查全部或单个医院）。
- **接口2**：查询某医生未来两周可预约时段，返回每个时段的号源容量、已约数、剩余数、是否约满。
- **接口3**：根据传入的 `医生id + 日期 + 时段` 创建预约；若时间冲突（已约满 / 非法时段 / 超出窗口）则失败，并返回当前可预约时段列表。
- **接口4**：根据预约 id 查询预约详情（含医院-科室-医生-时间-患者信息）。
- **动态可预约窗口**：每次启动按系统时间计算，可预约范围为 **明天起 14 天**，课程中任意日期运行都适用。
- **演示满号**：启动时自动在当前窗口内为若干医生预置已约满时段，方便演示冲突场景；这些演示数据每次启动按当前窗口刷新，不影响真实预约。
- **SQLite 持久化**：数据库文件位于 `data/medical.db`，启动时自动建表与播种。

---

## 技术栈

| 组件 | 版本要求 |
|---|---|
| Python | 3.11+ |
| FastAPI | ≥0.110 |
| Uvicorn | ≥0.27 |
| SQLAlchemy | ≥2.0 |
| Pydantic | v2（随 FastAPI 安装） |
| 数据库 | SQLite（文件持久化） |

---

## 项目结构

```
MedicalGuidanceSystem/
├── main.py                  # FastAPI 入口，启动时建表 + 播种
├── requirements.txt         # 依赖清单
├── .gitignore
├── data/
│   └── medical.db           # SQLite 数据库（首次启动自动生成）
└── app/
    ├── database.py          # 引擎 / 会话 / Base / get_db 依赖
    ├── models.py            # ORM 模型：Hospital/Department/Doctor/Schedule/Appointment
    ├── schemas.py           # Pydantic 请求/响应模型
    ├── crud.py              # 业务逻辑 + 可预约窗口计算
    ├── seed.py              # 示例数据播种 + 演示满号刷新
    └── routers/
        ├── hospitals.py     # 接口1：医院-科室-医生树
        ├── doctors.py       # 接口2：医生可预约时段
        └── appointments.py  # 接口3、4：创建/查询预约
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

首次启动会在 `data/` 下生成 `medical.db` 并写入示例数据。

---

## 数据模型

| 表 | 说明 | 关键字段 |
|---|---|---|
| `hospitals` | 医院 | id, name, level(等级), address, phone |
| `departments` | 科室 | id, hospital_id(FK), name, description |
| `doctors` | 医生 | id, department_id(FK), name, title(职称), specialty |
| `schedules` | 每周排班规则 | id, doctor_id(FK), weekday(0=周一…6=周日), start_time, end_time, capacity(号源数) |
| `appointments` | 预约 | id, doctor_id(FK), slot_date, start_time, end_time, patient_name, patient_phone, status, is_demo, created_at |

**排班设计**：`schedules` 存"每周几的某时段放多少号"，不绑定具体日期；查询时按当前可预约窗口动态展开成具体时段，并统计 `appointments` 中已确认预约数得到余号。

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
    "name": "北京协和医院",
    "level": "三甲",
    "address": "北京市东城区帅府园1号",
    "phone": "010-69151188",
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
  "available_count": 8,
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
    "id": 16,
    "hospital_name": "北京协和医院",
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

**冲突响应**（时段已约满 / 非法时段 / 超出可预约窗口）：`success=false`，`appointment=null`，并在 `available_slots` 返回当前可预约时段供选择。

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

---

## 可预约窗口说明

- 窗口由 `app/crud.py` 的 `booking_window()` 计算：**起点 = 系统日期 + 1 天（明天），终点 = 起点 + 13 天**，共 14 天。
- 接口2 的时段列表与接口3 的预约校验都基于此窗口，每次请求按当前系统时间实时计算。
- 因此**今天不可预约**，最早可约日期为明天。

---

## 示例数据说明

启动时 `app/seed.py` 会写入：

- 3 家三甲医院：北京协和医院、上海瑞金医院、杭州市第一人民医院。
- 8 个科室（内科、外科、妇产科、骨科、神经内科、儿科等）。
- 9 名医生（主任/副主任/主治医师，各有专长）。
- 每名医生的每周排班规则（上午 08:00-12:00 / 下午 14:00-17:00，号源容量 2~6 不等）。
- 演示用已约满时段（`is_demo=true`），每次启动按当前窗口刷新，确保任意日期运行都能看到满号与冲突演示。涉及医生：张建国、王志强、周明、孙建华。

基础数据仅首次写入（幂等）；演示预约每次启动刷新，且只操作 `is_demo=true` 的行，**不会删除真实用户预约**。

---

## 持久化

- 数据库：SQLite，文件 `data/medical.db`。
- 启动时若文件不存在则自动创建并播种；已存在则复用（基础数据不重复写入）。
- 通过 API 创建的预约会持久化到该文件，重启后保留。

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
```
