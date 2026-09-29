# MultiAgIDE Studio

**Multi-Account Antigravity IDE & Google Chrome Workspace Orchestrator**  
โปรแกรมบริหารจัดการและจัดระเบียบหน้าจอสำหรับ **Antigravity IDE** และ **Google Chrome** รองรับสูงสุด 6 บัญชี Google พร้อมกัน โดยแยก Profile, Session และสภาพแวดล้อม (Environment) จากกันอย่างเด็ดขาด

---

## 🚀 คุณสมบัติเด่น (Key Features)

1. **ระบบแยกบัญชี Google 100% (Isolated Multi-User Profiles):**
   - รองรับสูงสุด 6 บัญชี (Slot 1 ถึง Slot 6)
   - แต่ละสล็อตจะมี Antigravity IDE 1 ตัว และ Google Chrome 1 หน้าต่าง
   - แยก Session, Cache, Login Token อิสระถาวร ล็อกอินบัญชี Google ครั้งเดียว ระบบจะจำสถานะไว้ตลอดไป ไม่ต้องตั้งค่าใหม่

2. **ระบบจัดหน้าจอไดนามิกอัตโนมัติ (Dynamic Grid & Auto-Tiling):**
   - คำนวณขนาดและพิกัดหน้าจอแบบเรียลไทม์ (หัก Taskbar ออกอัตโนมัติ)
   - พรีเซ็ต 1 คลิก:
     - **1 จอ (Focus):** ขยายเต็มหน้าจอ 100%
     - **2 จอ (Split 50/50):** แบ่งครึ่งซ้าย-ขวา
     - **3 จอ (Trio Columns):** แบ่ง 3 คอลัมน์เท่ากัน
     - **4 จอ (Quad 2x2):** แบ่ง 4 ช่อง 4 มุม
     - **6 จอ (Matrix 2x3):** แสดงผล 6 สล็อตพร้อมกันเต็มหน้าจอ
   - **ปุ่ม Snap All:** ดึงหน้าต่างที่เคลื่อนย้ายกลับเข้าพิกัด Grid สวยงามในคลิกเดียว

3. **การควบคุมรายสล็อต (Per-Slot Controls):**
   - **🔍 ปุ่มเต็มจอ (Maximize):** ขยายเฉพาะสล็อตที่เลือกให้เต็มจอ 100% และคลิกซ้ำเพื่อคืนสู่ Grid เดิม
   - **👁️ ปุ่มซ่อน/แสดง (Hide/Show):** เมื่อสั่งซ่อนสล็อตใด สล็อตที่เหลือจะคำนวณพื้นที่และขยายตัวเติมเต็มหน้าจออัตโนมัติ (Responsive Rearranging)
   - **⚡ สลับ IDE / Chrome (Quick Switch):** สลับหน้าต่างที่อยู่ด้านหน้าขึ้นมาทันที
   - **📂 เปิดโฟลเดอร์:** เปิดไดเรกทอรีจัดเก็บข้อมูลของโปรไฟล์นั้นใน Windows Explorer

4. **โหมดแถบลอยตัว (Mini Floating Dock):**
   - ย่อหน้าต่างคอนโซลหลักเป็นแถบเล็กๆ ติดไว้ที่ขอบบนหน้าจอ (Always-On-Top) เพื่อไม่ให้บดบังพื้นที่เขียนโค้ด

---

## 🛠️ วิธีการเปิดใช้งาน (How to Run)

### วิธีที่ 1: ดับเบิ้ลคลิกจาก Desktop Shortcut
- บนเดสก์ท็อปของคุณจะมีไอคอน **`MultiAgIDE Studio`** ดับเบิ้ลคลิกเพื่อเปิดโปรแกรมได้ทันที

### วิธีที่ 2: รันผ่านไฟล์ `launch.bat`
- เข้าไปที่โฟลเดอร์ `d:\ProJectNextLevel\MutiAgIDE`
- ดับเบิ้ลคลิกไฟล์ `launch.bat`

### วิธีที่ 3: รันผ่าน Terminal / PowerShell
```powershell
cd d:\ProJectNextLevel\MutiAgIDE
python main.py
```

---

## 📂 โครงสร้างไดเรกทอรีโปรเจกต์

```
d:\ProJectNextLevel\MutiAgIDE\
├── core/
│   ├── config_manager.py       # จัดการคอนฟิก Path และ Profiles
│   ├── layout_calculator.py    # คำนวณพิกัด Grid หน้าจอ 1-6 จอ
│   ├── window_controller.py    # Win32 API Engine สำหรับย้าย/ปรับขนาด/ซ่อนหน้าต่าง
│   └── process_manager.py      # สั่งเปิด/ปิด และจับคู่ HWND
├── ui/
│   ├── styles.py               # Dark Glassmorphic Theme (QSS)
│   ├── slot_card.py            # การ์ดควบคุมสล็อต 1 ถึง 6
│   ├── floating_dock.py        # แถบควบคุมขนาดกะทัดรัด (Mini Dock)
│   └── dashboard_window.py     # หน้าต่างแดชบอร์ดหลัก
├── profiles/                   # ข้อมูลเซสชันของแต่ละบัญชี
│   ├── slot_1/ { ide/, chrome/ }
│   ├── ...
│   └── slot_6/ { ide/, chrome/ }
├── config.json                 # ไฟล์บันทึกการตั้งค่า
├── launch.bat                  # ตัวเปิดโปรแกรมคลิกเดียว
├── main.py                     # Entry point
└── README.md                   # เอกสารประกอบการใช้งาน
```
