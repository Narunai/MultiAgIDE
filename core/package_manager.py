import os
import sys
import json
import time
import shutil
import zipfile
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple
import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = BASE_DIR / "profiles"
CONFIG_FILE = BASE_DIR / "config.json"
HISTORY_FILE = PROFILES_DIR / "slot_history.json"


def find_antigravity_ide() -> str:
    """ค้นหาไฟล์ Antigravity IDE.exe อัตโนมัติบนเครื่องนี้"""
    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local_app, "Programs", "Antigravity IDE", "Antigravity IDE.exe"),
        r"C:\Program Files\Antigravity IDE\Antigravity IDE.exe",
        r"C:\Program Files (x86)\Antigravity IDE\Antigravity IDE.exe",
        r"C:\Users\COMPUTER\AppData\Local\Programs\Antigravity IDE\Antigravity IDE.exe",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return candidates[0]


def find_chrome() -> str:
    """ค้นหา Google Chrome อัตโนมัติบนเครื่องนี้"""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return candidates[0]


def path_to_vscode_uri(file_path: str, encode_colon: bool = True) -> str:
    """แปลง Path บนเครื่องเป็น VS Code URI Format (เช่น file:///d%3A/...)"""
    p = str(file_path).replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        drive = p[0].lower()
        colon = "%3A" if encode_colon else ":"
        rest = p[2:]
        return f"file:///{drive}{colon}{rest}"
    return f"file:///{p}"


def generate_path_replacements(old_base: str, new_base: str) -> List[Tuple[str, str]]:
    """สร้างรายการคำสำหรับแปลง Path เดิมของเครื่องเก่าให้เป็น Path ของเครื่องใหม่"""
    old_base = os.path.normpath(str(old_base))
    new_base = os.path.normpath(str(new_base))
    if old_base.lower() == new_base.lower():
        return []

    replacements = []

    # 1. VS Code URI with %3A (lowercase and uppercase drive)
    uri_old_enc = path_to_vscode_uri(old_base, encode_colon=True)
    uri_new_enc = path_to_vscode_uri(new_base, encode_colon=True)
    replacements.append((uri_old_enc, uri_new_enc))
    if len(old_base) >= 1 and len(new_base) >= 1:
        replacements.append((
            uri_old_enc.replace("file:///" + old_base[0].lower(), "file:///" + old_base[0].upper()),
            uri_new_enc.replace("file:///" + new_base[0].lower(), "file:///" + new_base[0].upper())
        ))

    # 2. VS Code URI with : (colon)
    uri_old_col = path_to_vscode_uri(old_base, encode_colon=False)
    uri_new_col = path_to_vscode_uri(new_base, encode_colon=False)
    replacements.append((uri_old_col, uri_new_col))
    if len(old_base) >= 1 and len(new_base) >= 1:
        replacements.append((
            uri_old_col.replace("file:///" + old_base[0].lower(), "file:///" + old_base[0].upper()),
            uri_new_col.replace("file:///" + new_base[0].lower(), "file:///" + new_base[0].upper())
        ))

    # 3. Double backslash JSON escaped (D:\\Folder and d:\\Folder)
    json_old = old_base.replace("\\", "\\\\")
    json_new = new_base.replace("\\", "\\\\")
    replacements.append((json_old, json_new))
    if len(json_old) >= 1 and len(json_new) >= 1:
        replacements.append((
            json_old[0].lower() + json_old[1:],
            json_new[0].lower() + json_new[1:]
        ))
        replacements.append((
            json_old[0].upper() + json_old[1:],
            json_new[0].upper() + json_new[1:]
        ))

    # 4. Standard Windows backslash (D:\Folder and d:\Folder)
    replacements.append((old_base, new_base))
    if len(old_base) >= 1 and len(new_base) >= 1:
        replacements.append((
            old_base[0].lower() + old_base[1:],
            new_base[0].lower() + new_base[1:]
        ))
        replacements.append((
            old_base[0].upper() + old_base[1:],
            new_base[0].upper() + new_base[1:]
        ))

    # 5. Forward slash (D:/Folder and d:/Folder)
    slash_old = old_base.replace("\\", "/")
    slash_new = new_base.replace("\\", "/")
    replacements.append((slash_old, slash_new))
    if len(slash_old) >= 1 and len(slash_new) >= 1:
        replacements.append((
            slash_old[0].lower() + slash_old[1:],
            slash_new[0].lower() + slash_new[1:]
        ))
        replacements.append((
            slash_old[0].upper() + slash_old[1:],
            slash_new[0].upper() + slash_new[1:]
        ))

    # Remove duplicates while preserving order
    seen = set()
    unique_replacements = []
    for o, n in replacements:
        if o not in seen and o != n:
            seen.add(o)
            unique_replacements.append((o, n))
    return unique_replacements


class PackageManager:
    """
    ระบบ Export / Import Package สมบูรณ์แบบสำหรับ MultiAgIDE Studio
    - รวมทุกสล็อต, บัญชี Google, Auth Tokens, Sessions, Extensions, Workspaces และโปรเจกต์
    - ย้ายข้ามเครื่องได้ทันที นำเข้าแล้วกดใช้งานได้เลย 100% ไม่ต้องล็อกอินใหม่
    - Auto-Path Remapping: แปลง Path โครงสร้างเดิมเป็นเครื่องใหม่โดยอัตโนมัติ
    """

    TRANSIENT_CACHE_NAMES = {
        "cache", "code cache", "gpucache", "dawngraphitecache",
        "dawnwebgpucache", "crashpad", "blob_storage"
    }

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or BASE_DIR).resolve()
        self.profiles_dir = self.base_dir / "profiles"
        self.config_file = self.base_dir / "config.json"
        self.history_file = self.profiles_dir / "slot_history.json"

    def get_exportable_slots(self) -> List[dict]:
        """ดึงรายการสล็อตที่มีข้อมูลและโปรเจกต์พร้อมสำหรับการ Export"""
        slots_list = []
        history = {}
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                pass

        cfg = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                pass

        cfg_slots = {s["id"]: s for s in cfg.get("slots", [])}

        # รวบรวมสล็อตทั้งหมดจาก profiles_dir
        if self.profiles_dir.exists():
            for item in sorted(os.listdir(self.profiles_dir)):
                if item.startswith("slot_") and (self.profiles_dir / item).is_dir():
                    try:
                        sid = int(item.split("_")[1])
                    except ValueError:
                        continue

                    slot_dir = self.profiles_dir / item
                    ws_dir = slot_dir / "workspace"
                    projects = []
                    if ws_dir.exists():
                        for p in os.listdir(ws_dir):
                            if (ws_dir / p).is_dir() and not p.startswith("."):
                                projects.append(p)

                    hist = history.get(str(sid), {})
                    cfg_s = cfg_slots.get(sid, {})

                    slots_list.append({
                        "id": sid,
                        "name": cfg_s.get("name", f"Slot {sid}"),
                        "email": hist.get("email", "offline"),
                        "plan": hist.get("plan", "Free"),
                        "projects": projects,
                        "has_ide_profile": (slot_dir / "ide").exists(),
                        "notes": cfg_s.get("notes", "")
                    })

        # เรียงตาม id
        slots_list.sort(key=lambda x: x["id"])
        return slots_list

    def export_package(
        self,
        output_zip_path: str,
        slot_ids: Optional[List[int]] = None,
        include_workspaces: bool = True,
        exclude_transient_caches: bool = True,
        additional_folders: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> dict:
        """
        ส่งออกแพ็กเกจ MultiAgIDE (.zip หรือ .magpkg)
        รวมการตั้งค่า, ข้อมูล Auth Tokens ทั้งหมด, บัญชีผู้ใช้, และโปรเจกต์งาน
        """
        output_path = Path(output_zip_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        all_slots = self.get_exportable_slots()
        if slot_ids is not None:
            target_slots = [s for s in all_slots if s["id"] in slot_ids]
        else:
            target_slots = all_slots

        # เตรียม Manifest
        manifest = {
            "format": "MultiAgIDE-Package",
            "version": "1.0",
            "created_at": time.time(),
            "created_at_iso": datetime.datetime.now().isoformat(),
            "source_base_dir": str(self.base_dir),
            "slots_count": len(target_slots),
            "slots": target_slots,
            "include_workspaces": include_workspaces,
            "exclude_caches": exclude_transient_caches,
            "platform": sys.platform
        }

        # รวบรวมรายการไฟล์ที่จะบรรจุลง Zip
        files_to_pack = []

        # 1. config.json
        if self.config_file.exists():
            files_to_pack.append((self.config_file, "config.json"))

        # 2. slot_history.json
        if self.history_file.exists():
            files_to_pack.append((self.history_file, "profiles/slot_history.json"))

        # 3. ไฟล์ของแต่ละสล็อต
        for s in target_slots:
            sid = s["id"]
            slot_dir = self.profiles_dir / f"slot_{sid}"
            if not slot_dir.exists():
                continue

            for root, dirs, files in os.walk(slot_dir):
                rel_root = Path(root).relative_to(self.base_dir)

                # ถ้าเลือกข้ามแคชชั่วคราว ให้ข้ามโฟลเดอร์แคชเบราว์เซอร์
                if exclude_transient_caches:
                    dirs[:] = [d for d in dirs if d.lower() not in self.TRANSIENT_CACHE_NAMES]

                # ถ้าไม่รวม Workspace ให้ข้ามโฟลเดอร์ workspace
                if not include_workspaces and "workspace" in Path(root).parts:
                    continue

                for f in files:
                    fp = Path(root) / f
                    arcname = str((rel_root / f)).replace("\\", "/")
                    files_to_pack.append((fp, arcname))

        # 4. โฟลเดอร์เสริม (หากผู้ใช้ระบุเพิ่มเติม)
        if additional_folders:
            for extra in additional_folders:
                extra_path = Path(extra)
                if extra_path.exists():
                    if extra_path.is_file():
                        files_to_pack.append((extra_path, f"external_projects/{extra_path.name}"))
                    elif extra_path.is_dir():
                        for root, _, files in os.walk(extra_path):
                            rel = Path(root).relative_to(extra_path.parent)
                            for f in files:
                                fp = Path(root) / f
                                files_to_pack.append((fp, str(rel / f).replace("\\", "/")))

        total_files = len(files_to_pack) + 1  # +1 for manifest
        packed_count = 0
        total_uncompressed_bytes = 0

        # เริ่มต้นเขียน Zip
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # เขียน package_manifest.json เป็นไฟล์แรก
            manifest_str = json.dumps(manifest, indent=2, ensure_ascii=False)
            zf.writestr("package_manifest.json", manifest_str.encode("utf-8"))
            packed_count += 1
            if progress_callback:
                progress_callback(packed_count, total_files, "package_manifest.json")

            for src_path, arc_name in files_to_pack:
                try:
                    zf.write(src_path, arc_name)
                    total_uncompressed_bytes += src_path.stat().st_size
                except Exception as e:
                    print(f"Warning: skipped {src_path}: {e}")
                packed_count += 1
                if progress_callback and (packed_count % 20 == 0 or packed_count == total_files):
                    progress_callback(packed_count, total_files, arc_name)

        archive_size = output_path.stat().st_size
        return {
            "success": True,
            "output_path": str(output_path),
            "files_count": packed_count,
            "total_uncompressed_bytes": total_uncompressed_bytes,
            "archive_size_bytes": archive_size,
            "slots_exported": [s["id"] for s in target_slots],
            "manifest": manifest
        }

    def inspect_package(self, package_zip_path: str) -> dict:
        """ตรวจสอบข้อมูลแพ็กเกจโดยไม่ต้องแตกไฟล์ทั้งหมดออกมาก่อน"""
        zip_p = Path(package_zip_path).resolve()
        if not zip_p.exists():
            raise FileNotFoundError(f"Package file not found: {package_zip_path}")

        with zipfile.ZipFile(zip_p, "r") as zf:
            namelist = zf.namelist()
            manifest = None
            if "package_manifest.json" in namelist:
                with zf.open("package_manifest.json") as mf:
                    manifest = json.loads(mf.read().decode("utf-8"))

            uncompressed_size = sum(info.file_size for info in zf.infolist())

        return {
            "valid": manifest is not None,
            "manifest": manifest or {},
            "archive_path": str(zip_p),
            "archive_size_bytes": zip_p.stat().st_size,
            "uncompressed_size_bytes": uncompressed_size,
            "total_files": len(namelist),
            "created_at_iso": manifest.get("created_at_iso", "Unknown") if manifest else "Unknown",
            "source_base_dir": manifest.get("source_base_dir", "") if manifest else "",
            "slots": manifest.get("slots", []) if manifest else []
        }

    def import_package(
        self,
        package_zip_path: str,
        target_base_dir: Optional[Path] = None,
        selected_slot_ids: Optional[List[int]] = None,
        mode: str = "merge",  # "merge" หรือ "replace"
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> dict:
        """
        นำเข้าแพ็กเกจ MultiAgIDE (.zip หรือ .magpkg)
        พร้อมทำการ Auto-Path Remapping ให้เข้ากับ Path และการตั้งค่าบนเครื่องใหม่ทันที
        """
        zip_p = Path(package_zip_path).resolve()
        if not zip_p.exists():
            raise FileNotFoundError(f"Package file not found: {package_zip_path}")

        target_base = Path(target_base_dir or self.base_dir).resolve()
        target_profiles = target_base / "profiles"
        target_config = target_base / "config.json"
        target_history = target_profiles / "slot_history.json"

        target_profiles.mkdir(parents=True, exist_ok=True)

        inspection = self.inspect_package(package_zip_path)
        manifest = inspection.get("manifest", {})
        old_source_base = manifest.get("source_base_dir", "")

        # สร้างตารางคำสำหรับแปลง Path ข้ามเครื่อง
        replacements = []
        if old_source_base:
            replacements = generate_path_replacements(old_source_base, str(target_base))

        imported_slot_ids = set()

        with zipfile.ZipFile(zip_p, "r") as zf:
            infolist = zf.infolist()
            total_items = len(infolist)
            processed_items = 0

            # 1. แตกไฟล์ทั้งหมด
            for member in infolist:
                arc_name = member.filename
                if arc_name == "package_manifest.json":
                    processed_items += 1
                    continue

                # กรองเฉพาะสล็อตที่เลือก (หากระบุ)
                parts = arc_name.split("/")
                if len(parts) >= 2 and parts[0] == "profiles" and parts[1].startswith("slot_"):
                    try:
                        sid = int(parts[1].split("_")[1])
                        if selected_slot_ids is not None and sid not in selected_slot_ids:
                            processed_items += 1
                            continue
                        imported_slot_ids.add(sid)
                    except ValueError:
                        pass

                # ถอดไฟล์ออกมายัง target_base
                out_path = target_base / arc_name
                out_path.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(member) as src_f, open(out_path, "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f)

                processed_items += 1
                if progress_callback and (processed_items % 25 == 0 or processed_items == total_items):
                    progress_callback(processed_items, total_items, arc_name)

        # 2. ปรับแต่ง config.json ให้ตรวจพบ Antigravity IDE บนเครื่องนี้อัตโนมัติ
        if target_config.exists():
            try:
                with open(target_config, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)

                # ถ้าเป็นโหมด merge ให้อัปเดตเฉพาะสล็อตที่นำเข้า โดยคงสล็อตเดิมไว้
                if mode == "merge" and manifest.get("slots"):
                    existing_slots = {s["id"]: s for s in cfg_data.get("slots", [])}
                    for pkg_s in manifest["slots"]:
                        sid = pkg_s["id"]
                        if selected_slot_ids is not None and sid not in selected_slot_ids:
                            continue
                        existing_slots[sid] = {
                            "id": sid,
                            "name": pkg_s.get("name", f"Slot {sid}"),
                            "visible": True,
                            "notes": pkg_s.get("notes", "")
                        }
                    cfg_data["slots"] = [existing_slots[k] for k in sorted(existing_slots.keys())]
                    cfg_data["max_slots"] = len(cfg_data["slots"])

                # ตรวจหาไฟล์ IDE บนเครื่องเป้าหมาย ถ้าพาธเดิมไม่มีอยู่จริง
                curr_ide = cfg_data.get("ide_path", "")
                if not os.path.exists(curr_ide):
                    detected_ide = find_antigravity_ide()
                    if os.path.exists(detected_ide):
                        cfg_data["ide_path"] = detected_ide

                curr_chrome = cfg_data.get("chrome_path", "")
                if not os.path.exists(curr_chrome):
                    detected_chrome = find_chrome()
                    if os.path.exists(detected_chrome):
                        cfg_data["chrome_path"] = detected_chrome

                # บันทึก config.json ใหม่
                with open(target_config, "w", encoding="utf-8") as f:
                    json.dump(cfg_data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error updating target config.json: {e}")

        # 3. ทำการ Auto-Path Remapping สำหรับสล็อตทั้งหมดที่นำเข้า
        remapped_count = 0
        if replacements:
            for sid in imported_slot_ids:
                slot_ide_dir = target_profiles / f"slot_{sid}" / "ide"
                if not slot_ide_dir.exists():
                    continue

                # 3.1 Remap storage.json
                storage_file = slot_ide_dir / "User" / "globalStorage" / "storage.json"
                if storage_file.exists():
                    if self._remap_text_file(storage_file, replacements):
                        remapped_count += 1

                # 3.2 Remap workspaceStorage/*/workspace.json
                ws_storage_dir = slot_ide_dir / "User" / "workspaceStorage"
                if ws_storage_dir.exists():
                    for root, _, files in os.walk(ws_storage_dir):
                        for f in files:
                            if f == "workspace.json":
                                if self._remap_text_file(Path(root) / f, replacements):
                                    remapped_count += 1

                # 3.3 Remap state.vscdb (SQLite)
                vscdb_file = slot_ide_dir / "User" / "globalStorage" / "state.vscdb"
                if vscdb_file.exists():
                    if self._remap_sqlite_vscdb(vscdb_file, replacements):
                        remapped_count += 1

        return {
            "success": True,
            "imported_slot_ids": sorted(list(imported_slot_ids)),
            "slots_count": len(imported_slot_ids),
            "remapped_files": remapped_count,
            "target_dir": str(target_base)
        }

    def _remap_text_file(self, file_path: Path, replacements: List[Tuple[str, str]]) -> bool:
        """แทนที่ Path ในไฟล์ข้อความ (JSON หรือ Text)"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            changed = False
            for old_str, new_str in replacements:
                if old_str in content:
                    content = content.replace(old_str, new_str)
                    changed = True

            if changed:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True
        except Exception as e:
            print(f"Error remapping text file {file_path}: {e}")
        return False

    def _remap_sqlite_vscdb(self, db_path: Path, replacements: List[Tuple[str, str]]) -> bool:
        """แทนที่ Path ในฐานข้อมูล SQLite ItemTable ของ state.vscdb"""
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM ItemTable")
            rows = cur.fetchall()

            updates = []
            for k, v in rows:
                if isinstance(v, str):
                    new_v = v
                    changed = False
                    for old_str, new_str in replacements:
                        if old_str in new_v:
                            new_v = new_v.replace(old_str, new_str)
                            changed = True
                    if changed:
                        updates.append((new_v, k))
                elif isinstance(v, (bytes, bytearray)):
                    new_v = bytes(v)
                    changed = False
                    for old_str, new_str in replacements:
                        old_b = old_str.encode("utf-8")
                        new_b = new_str.encode("utf-8")
                        if old_b in new_v:
                            new_v = new_v.replace(old_b, new_b)
                            changed = True
                    if changed:
                        updates.append((new_v, k))

            if updates:
                cur.executemany("UPDATE ItemTable SET value=? WHERE key=?", updates)
                conn.commit()
                conn.close()
                return True
            conn.close()
        except Exception as e:
            print(f"Error remapping sqlite DB {db_path}: {e}")
        return False
