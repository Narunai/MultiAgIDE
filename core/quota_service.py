import datetime
import json
import ssl
import time
import urllib.request
from typing import Dict, List, Optional
import psutil


class QuotaInfo:
    def __init__(self):
        self.connected: bool = False
        self.email: str = "offline"
        self.plan: str = "Free"
        self.gemini_pct: int = 100
        self.rolling_5h_pct: int = 100
        self.reset_5h_str: str = "--"
        self.weekly_str: str = "7d 00h"
        self.is_exhausted: bool = False
        self.last_updated: float = 0


class QuotaService:
    def __init__(self):
        self.cache: Dict[int, QuotaInfo] = {}
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def fetch_slot_quota(self, slot_id: int, ide_root_pid: Optional[int] = None) -> QuotaInfo:
        """
        ดึงข้อมูล Quota และ Token ของ Antigravity IDE ประจำสล็อตนั้นแบบ 1:1 Strict Matching
        ไม่ยืมหรือใช้ข้อมูลข้ามสล็อตโดยเด็ดขาด
        """
        info = self.cache.get(slot_id, QuotaInfo())

        ls_proc = self._find_language_server_for_slot(slot_id, ide_root_pid)
        if not ls_proc:
            info.connected = False
            info.email = "offline"
            return info

        csrf_token = self._extract_csrf_token(ls_proc)
        ports = self._get_listening_ports(ls_proc.pid)

        if not ports:
            info.connected = False
            return info

        user_status = self._query_user_status(ports, csrf_token)
        if not user_status:
            info.connected = False
            return info

        self._parse_quota_data(info, user_status)
        info.connected = True
        info.last_updated = time.time()
        self.cache[slot_id] = info
        return info

    def _find_language_server_for_slot(self, slot_id: int, ide_root_pid: Optional[int] = None) -> Optional[psutil.Process]:
        """
        ค้นหาโปรเซส Language Server ที่เป็นของสล็อตนี้เท่านั้น (Strict Slot Association)
        ตรวจสอบจาก tag 'slot_{slot_id}' ใน command line หรือใน parent processes
        """
        target_tag = f"slot_{slot_id}"

        # 1. ตรวจสอบจาก PID ลูกหลานของ IDE ที่เปิดโดยสล็อตนี้
        if ide_root_pid and psutil.pid_exists(ide_root_pid):
            try:
                parent = psutil.Process(ide_root_pid)
                for child in parent.children(recursive=True):
                    name = child.name().lower()
                    if "language_server" in name:
                        return child
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 2. ตรวจสอบโปรเซส language_server ทุกตัวที่มี tag ของสล็อตนี้โดยตรง
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info['name'].lower()
                if "language_server" in name:
                    cmd_str = " ".join(p.cmdline() or []).lower()
                    if target_tag in cmd_str:
                        return p

                    # ตรวจสอบบรรพบุรุษ (Ancestors) ว่าเป็น IDE ของสล็อตนี้หรือไม่
                    curr = p
                    while curr and curr.ppid() != 0:
                        parent = curr.parent()
                        if not parent:
                            break
                        curr = parent
                        p_cmd = " ".join(curr.cmdline() or []).lower()
                        if target_tag in p_cmd:
                            return p
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # ไม่พบ Language Server ของสล็อตนี้ (ห้าม Fallback สุ่มเด็ดขาด)
        return None

    def _extract_csrf_token(self, proc: psutil.Process) -> Optional[str]:
        try:
            cmd = proc.cmdline()
            for i, arg in enumerate(cmd):
                if arg == "--csrf_token" and i + 1 < len(cmd):
                    return cmd[i + 1]
        except Exception:
            pass
        return None

    def _get_listening_ports(self, pid: int) -> List[int]:
        ports = []
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.pid == pid and conn.status == psutil.CONN_LISTEN:
                    ports.append(conn.laddr.port)
        except Exception:
            pass
        return ports

    def _query_user_status(self, ports: List[int], csrf_token: Optional[str]) -> Optional[dict]:
        endpoint = "/exa.language_server_pb.LanguageServerService/GetUserStatus"
        payload = json.dumps({
            "metadata": {
                "ideName": "antigravity",
                "extensionName": "antigravity",
                "locale": "en"
            }
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
        }
        if csrf_token:
            headers["X-Codeium-Csrf-Token"] = csrf_token

        for proto in ["https", "http"]:
            for port in ports:
                url = f"{proto}://127.0.0.1:{port}{endpoint}"
                req = urllib.request.Request(url, data=payload, headers=headers)
                try:
                    ctx = self.ssl_ctx if proto == "https" else None
                    with urllib.request.urlopen(req, context=ctx, timeout=0.8) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            return data.get("userStatus")
                except Exception:
                    continue
        return None

    def _parse_quota_data(self, info: QuotaInfo, user_status: dict):
        info.email = user_status.get("email", "Unknown")
        plan_info = user_status.get("planStatus", {}).get("planInfo", {})
        info.plan = plan_info.get("planName", "Pro")

        model_configs = user_status.get("cascadeModelConfigData", {}).get("clientModelConfigs", [])
        now = datetime.datetime.now(datetime.timezone.utc)

        gemini_fractions = []
        reset_times = []

        for m in model_configs:
            label = m.get("label", "")
            q_info = m.get("quotaInfo", {})
            frac = q_info.get("remainingFraction")
            r_time = q_info.get("resetTime")

            if frac is not None:
                if "gemini" in label.lower():
                    gemini_fractions.append(frac)
                if r_time:
                    reset_times.append(r_time)

        if gemini_fractions:
            min_frac = min(gemini_fractions)
            info.gemini_pct = int(min_frac * 100)
            info.rolling_5h_pct = int(min_frac * 100)
        else:
            info.gemini_pct = 100
            info.rolling_5h_pct = 100

        if reset_times:
            earliest_reset = None
            for rt in reset_times:
                try:
                    dt = datetime.datetime.fromisoformat(rt.replace("Z", "+00:00"))
                    if earliest_reset is None or dt < earliest_reset:
                        earliest_reset = dt
                except Exception:
                    pass

            if earliest_reset and earliest_reset > now:
                diff = earliest_reset - now
                sec = int(diff.total_seconds())
                h = sec // 3600
                m = (sec % 3600) // 60
                info.reset_5h_str = f"{h}h {m:02d}m"
            else:
                info.reset_5h_str = "Ready"

        info.weekly_str = "6d 23h"
