# MultiAgIDE Studio

**Multi-Account Antigravity IDE Workspace Orchestrator**  
ระบบบริหารจัดการ จัดสรรหน้าจอ และควบคุมหลายบัญชี Google สำหรับ **Antigravity IDE** รองรับตั้งแต่ 1 ถึง 12+ บัญชี พร้อมระบบแยก Profile, Auth Tokens, Sessions, และ Workspaces อย่างเด็ดขาด พร้อมความสามารถในการส่งออก (Export) และนำเข้า (Import) เพื่อย้ายเครื่องทำงานได้ทันที 100%

---

## Key Features

1. **ระบบแยกบัญชี Google 100% (Isolated Multi-User Profiles):**
   - รองรับบัญชีไม่จำกัด (เริ่มต้น 12 สล็อต และกด `+ Add Slot` ได้ต่อเนื่อง)
   - แยก User Data Directory, Session, Google OAuth Tokens, State Cache และ History ของแต่ละสล็อตออกจากกันเด็ดขาด
   - ปลอดภัยจากระบบหลัก: แยกขาดจาก Antigravity ปกติของเครื่อง (`AppData\Roaming\Antigravity IDE`) 100%

2. **ระบบสลับหน้าจอ Display 1 สำหรับสล็อต 7 เป็นต้นไป (Display 1 Alternating Slots):**
   - สล็อต 1 ถึง 6 กระจายตามตำแหน่ง Display 1 ถึง 6 บนหน้าจอ
   - สล็อตที่ 7 เป็นต้นไป (สล็อต 7, 8, 9, 10, ...) จะแชร์พิกัดหน้าจอกับ Display 1 (สล็อต 1) อัตโนมัติ โดยระบบจะสลับเปิด/ซ่อนให้อัตโนมัติเพื่อไม่ให้หน้าต่างบดบังทับซ้อนกัน

3. **คลิกเรียกหน้าต่างงานขึ้นมาด้านหน้าสุดทันที (Click-to-Bring-Forward):**
   - คลิกที่หมายเลขสล็อต (`#1`, `#2`, `#3`...) หรือคลิกบนการ์ด เพื่อดึงหน้าต่าง Antigravity IDE ของสล็อตนั้นขึ้นมาด้านหน้าสุด (Unhide + Restore + Foreground) ทันทีโดยไม่ต้องคอยเล็งปุ่ม Res หรือ Max
   - หากสล็อตนั้นปิดอยู่ การคลิกจะสั่งเปิดสล็อตและผูก Workspace ให้อัตโนมัติ

4. **ระบบ Export / Import Package สมบูรณ์แบบ (Portable Migration Engine):**
   - **Export Package (`.zip` / `.magpkg`):** รวมทุกสล็อต, บัญชี Google, Auth Tokens, ส่วนขยาย, ประวัติแชท, และโฟลเดอร์โปรเจกต์งานทั้งหมดออกมาเป็นไฟล์แพ็กเกจเดียว
   - **Auto-Path Remapping:** เมื่อนำเข้า (Import) บนเครื่องใหม่ ระบบจะแปลง Path เดิม (เช่น `D:\...` ไปเป็น `C:\...`) ทั้งใน `storage.json`, `workspaceStorage`, `state.vscdb` (SQLite) และ `config.json` ให้อัตโนมัติ 100%
   - **Auto-Detect Local IDE:** ค้นหาไฟล์ `Antigravity IDE.exe` บนเครื่องใหม่ตามโฟลเดอร์ AppData หรือ Program Files อัตโนมัติ ทำให้กดใช้งานได้ทันทีโดยไม่ต้องล็อกอินใหม่

5. **ระบบนับถอยหลัง Cooldown 5 ชั่วโมงตามเวลาจริง (Real-Time Cooldown Countdown):**
   - เมื่อปิดโปรแกรมหรือล็อกอินกลับมา เวลา Cooldown จะหักลบตามเวลาจริงของนาฬิการะบบ
   - มีระบบแจ้งเตือนแบนเนอร์และ Windows Toast Notification: *"อีเมลนี้พร้อมใช้งานอีกครั้ง"* เมื่อเวลาครบ

6. **Ultra-Minimal Modern Dark Theme:**
   - ดีไซน์ Dark-Gray (#121214 / #18181b), Typography คมชัด, นโยบาย Zero-Emoji / Zero-Icon
   - DWM Immersive Dark Title Bar กลมกลืนกับระบบปฏิบัติการ Windows 11 / 10

---

## วิธีการเปิดใช้งาน (How to Run)

### 1. เปิดโปรแกรม Dashboard
- ดับเบิ้ลคลิกไฟล์ `launch.bat` หรือรัน:
  ```powershell
  python main.py
  ```

### 2. ส่งออกแพ็กเกจเพื่อย้ายเครื่อง (Export Package)
- **ผ่านหน้า Dashboard:** กดปุ่ม **Export** ที่มุมขวาล่าง เลือกระบุสล็อตและปลายทางไฟล์ `.zip`
- **ผ่านไฟล์ Batch:** ดับเบิ้ลคลิก `export.bat` หรือรัน:
  ```powershell
  python export_package.py
  ```

### 3. นำเข้าแพ็กเกจบนเครื่องใหม่ (Import Package)
- **ผ่านหน้า Dashboard:** กดปุ่ม **Import** ที่มุมขวาล่าง เลือกไฟล์ `.zip` หรือ `.magpkg` แล้วกด **Start Import**
- **ผ่านไฟล์ Batch:** ดับเบิ้ลคลิก `import.bat` หรือรัน:
  ```powershell
  python import_package.py "path\to\package.zip"
  ```
- เมื่อนำเข้าเสร็จ สล็อตและโปรเจกต์ทั้งหมดจะพร้อมใช้งานทันที

---

## โครงสร้างโปรเจกต์ (Project Structure)

```
MutiAgIDE/
├── core/
│   ├── config_manager.py       # จัดการคอนฟิก Path และการเพิ่ม/ลบสล็อต
│   ├── layout_calculator.py    # คำนวณพิกัด Grid หน้าจอ และ Display 1 สำหรับสล็อต 7+
│   ├── window_controller.py    # Win32 API Engine (ควบคุมพิกัด, Unhide, Bring to front)
│   ├── process_manager.py      # สั่งเปิด/ปิด, ตรวจจับ HWND, และ Real-time Cooldown
│   ├── package_manager.py      # ระบบ Export/Import และ Auto-Path Remapping ข้ามเครื่อง
│   ├── quota_service.py        # ดึงโควตา Gemini และ Reset Time จาก Language Server
│   └── slot_history_manager.py # บันทึกประวัติสล็อตและเวลา Cooldown ตามเวลาจริง
├── ui/
│   ├── styles.py               # Minimalist Dark-Gray Theme (Zero Emoji)
│   ├── dark_title_bar.py       # Windows DWM Immersive Dark Title Bar API
│   ├── slot_card.py            # การ์ดสล็อต (รองรับการคลิกหมายเลขเพื่อดึงหน้าต่างขึ้นหน้าสุด)
│   ├── quota_pill.py           # แถบแสดงโควตาเรียบแบน
│   ├── package_dialogs.py      # หน้าต่าง Export / Import Package
│   └── dashboard_window.py     # หน้าต่างแดชบอร์ดหลัก ปรับความสูงไดนามิกตามสล็อต
├── profiles/                   # โปรไฟล์แยกอิสระ 100%
│   ├── slot_1/ { ide/, workspace/, logs/ }
│   ├── ...
│   ├── slot_12/ { ide/, workspace/, logs/ }
│   └── slot_history.json       # ประวัติและโควตาล่าสุด
├── config.json                 # การตั้งค่าสล็อตและพิกัดเลย์เอาต์
├── launch.bat                  # ตัวเปิดโปรแกรม Dashboard
├── export.bat                  # ตัวส่งออกแพ็กเกจคลิกเดียว
├── import.bat                  # ตัวนำเข้าแพ็กเกจคลิกเดียว
├── export_package.py           # สคริปต์ส่งออกแพ็กเกจแบบ CLI
├── import_package.py           # สคริปต์นำเข้าแพ็กเกจแบบ CLI
├── main.py                     # Entry point
└── README.md                   # เอกสารประกอบการใช้งาน
```
