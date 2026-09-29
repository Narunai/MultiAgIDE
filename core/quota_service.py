import datetime
import json
import ssl
import time
import urllib.request
from typing import Dict, List, Optional, Tuple
import psutil


class QuotaInfo:
    def __init__(self):
        self.connected: bool = False
        self.email: str = "offline"
        self.plan: str = "Free"
        self.gemini_pct: int = 100
        self.rolling_5h_pct: int = 100
        self.reset_5h_str: str = "--"
        self.weekly_str: str = "--"
        self.reset_5h_ts: float = 0
        self.weekly_ts: float = 0
        self.third_party_weekly_pct: int = 100
        self.third_party_5h_pct: int = 100
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
        ดึงข้อมูล Quota และ Token ประจำสล็อตนั้นแบบ 100% Strict Isolation
        - ห้ามจับโปรเซสของ Antigravity ทั่วไปในเครื่องเด็ดขาด
        - ต้องเป็นโปรเซสที่ถูกเปิดขึ้นมาภายใต้สล็อตนี้เท่านั้น
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
            info.email = "offline"
            return info

        user_status, quota_summary = self._query_server_data(ports, csrf_token)
        if not user_status and not quota_summary:
            info.connected = False
            info.email = "offline"
            return info

        self._parse_quota_data(info, user_status, quota_summary)
        info.connected = True
        info.last_updated = time.time()
        self.cache[slot_id] = info
        return info

    def _find_language_server_for_slot(self, slot_id: int, ide_root_pid: Optional[int] = None) -> Optional[psutil.Process]:
        """
        ค้นหา Language Server ที่สังกัดสล็อตนี้เท่านั้น (Strict Slot Matching)
        กรองและตัด Antigravity ปกติของระบบออก 100%
        """
        target_tag = f"slot_{slot_id}"

        # 1. ตรวจสอบจาก PID ลูกหลานของ IDE ที่สล็อตนี้เป็นคนสั่งเปิด
        if ide_root_pid and psutil.pid_exists(ide_root_pid):
            try:
                parent = psutil.Process(ide_root_pid)
                # ตรวจสอบว่าโปรเซสต้นทางไม่ใช่ Antigravity ปกติ
                p_cmd = " ".join(parent.cmdline() or []).lower()
                if target_tag in p_cmd:
                    for child in parent.children(recursive=True):
                        if "language_server" in child.name().lower():
                            return child
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 2. ตรวจสอบโปรเซส language_server ทุกตัวในเครื่อง
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info['name'].lower()
                if "language_server" not in name:
                    continue

                cmd_str = " ".join(p.cmdline() or []).lower()

                # กฎเหล็ก: ถ้าเป็น Antigravity ปกติของเครื่อง (AppData\Roaming\Antigravity IDE) ให้ข้ามทันที
                if "appdata\\roaming\\antigravity" in cmd_str:
                    continue

                # ต้องมี tag 'slot_{slot_id}' ชัดเจนใน arguments
                if target_tag in cmd_str:
                    return p

                # ตรวจสอบสายบรรพบุรุษ (Parent / Ancestors)
                curr = p
                has_slot_tag = False
                is_system_ide = False

                while curr and curr.ppid() != 0:
                    parent = curr.parent()
                    if not parent:
                        break
                    curr = parent
                    parent_cmd = " ".join(curr.cmdline() or []).lower()

                    if "appdata\\roaming\\antigravity" in parent_cmd:
                        is_system_ide = True
                        break

                    if target_tag in parent_cmd:
                        has_slot_tag = True
                        break

                if has_slot_tag and not is_system_ide:
                    return p

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # ไม่ใช่โปรเซสของสล็อตนี้ -> คืนค่า None เสมอ (ห้ามสุ่มหรือเดาเด็ดขาด)
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

    def _query_server_data(self, ports: List[int], csrf_token: Optional[str]) -> Tuple[Optional[dict], Optional[dict]]:
        """
        เรียก Connect RPC API บน localhost เพื่อดึงข้อมูล UserStatus และ RetrieveUserQuotaSummary
        """
        status_payload = json.dumps({
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
                ctx = self.ssl_ctx if proto == "https" else None
                base_url = f"{proto}://127.0.0.1:{port}"

                user_status = None
                quota_summary = None

                # 1. ลองดึง RetrieveUserQuotaSummary (เป็นทางการและแม่นยำที่สุด)
                try:
                    summary_url = f"{base_url}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
                    req = urllib.request.Request(summary_url, data=b"{}", headers=headers)
                    with urllib.request.urlopen(req, context=ctx, timeout=0.8) as resp:
                        if resp.status == 200:
                            quota_summary = json.loads(resp.read().decode("utf-8"))
                except Exception:
                    pass

                # 2. ลองดึง GetUserStatus
                try:
                    status_url = f"{base_url}/exa.language_server_pb.LanguageServerService/GetUserStatus"
                    req = urllib.request.Request(status_url, data=status_payload, headers=headers)
                    with urllib.request.urlopen(req, context=ctx, timeout=0.8) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            user_status = data.get("userStatus")
                except Exception:
                    pass

                if user_status or quota_summary:
                    return user_status, quota_summary

        return None, None

    def _parse_iso_to_ts(self, r_time_str: str) -> float:
        try:
            dt = datetime.datetime.fromisoformat(r_time_str.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return 0

    def _format_time_remaining(self, r_time_str: str, now: datetime.datetime, show_days: bool = True) -> str:
        try:
            dt = datetime.datetime.fromisoformat(r_time_str.replace("Z", "+00:00"))
            if dt <= now:
                return "Ready"
            diff = dt - now
            sec = int(diff.total_seconds())
            days = sec // 86400
            hours = (sec % 86400) // 3600
            mins = (sec % 3600) // 60

            if show_days and days > 0:
                return f"{days}d {hours:02d}h"
            elif hours > 0:
                return f"{hours}h {mins:02d}m"
            elif mins > 0:
                return f"{mins}m"
            else:
                return "Ready"
        except Exception:
            return "--"

    def _parse_quota_data(self, info: QuotaInfo, user_status: Optional[dict], quota_summary: Optional[dict]):
        now = datetime.datetime.now(datetime.timezone.utc)

        if user_status:
            info.email = user_status.get("email", "Unknown")
            plan_info = user_status.get("planStatus", {}).get("planInfo", {})
            info.plan = plan_info.get("planName", "Pro")

        summary_parsed = False
        if quota_summary and "response" in quota_summary:
            groups = quota_summary.get("response", {}).get("groups", [])
            for g in groups:
                d_name = g.get("displayName", "").lower()
                buckets = g.get("buckets", [])

                if "gemini" in d_name:
                    for b in buckets:
                        bid = b.get("bucketId", "")
                        win = b.get("window", "")
                        frac = b.get("remainingFraction")
                        r_time = b.get("resetTime")

                        if bid == "gemini-weekly" or win == "weekly":
                            if frac is not None:
                                info.gemini_pct = int(frac * 100)
                            if r_time:
                                info.weekly_str = self._format_time_remaining(r_time, now, show_days=True)
                                info.weekly_ts = self._parse_iso_to_ts(r_time)
                                summary_parsed = True

                        elif bid == "gemini-5h" or win == "5h":
                            if frac is not None:
                                info.rolling_5h_pct = int(frac * 100)
                            if r_time:
                                info.reset_5h_str = self._format_time_remaining(r_time, now, show_days=False)
                                info.reset_5h_ts = self._parse_iso_to_ts(r_time)

                elif "claude" in d_name or "gpt" in d_name or "3p" in d_name:
                    for b in buckets:
                        bid = b.get("bucketId", "")
                        win = b.get("window", "")
                        frac = b.get("remainingFraction")
                        if (bid == "3p-weekly" or win == "weekly") and frac is not None:
                            info.third_party_weekly_pct = int(frac * 100)
                        elif (bid == "3p-5h" or win == "5h") and frac is not None:
                            info.third_party_5h_pct = int(frac * 100)

        # Fallback หาก RetrieveUserQuotaSummary ไม่ให้ข้อมูล weekly
        if not summary_parsed and user_status:
            model_configs = user_status.get("cascadeModelConfigData", {}).get("clientModelConfigs", [])
            gemini_fractions = []
            short_reset_times = []
            weekly_reset_times = []

            for m in model_configs:
                label = m.get("label", "").lower()
                q_info = m.get("quotaInfo", {})
                frac = q_info.get("remainingFraction")
                r_time = q_info.get("resetTime")

                if frac is not None:
                    if "gemini" in label:
                        gemini_fractions.append(frac)
                    if r_time:
                        try:
                            dt = datetime.datetime.fromisoformat(r_time.replace("Z", "+00:00"))
                            diff = (dt - now).total_seconds()
                            if diff > 86400:
                                weekly_reset_times.append(dt)
                            elif diff > 0:
                                short_reset_times.append(dt)
                        except Exception:
                            pass

            if gemini_fractions:
                min_frac = min(gemini_fractions)
                info.gemini_pct = int(min_frac * 100)
                info.rolling_5h_pct = int(min_frac * 100)

            if short_reset_times:
                earliest_5h = min(short_reset_times)
                info.reset_5h_ts = earliest_5h.timestamp()
                diff = earliest_5h - now
                sec = int(diff.total_seconds())
                h = sec // 3600
                m = (sec % 3600) // 60
                info.reset_5h_str = f"{h}h {m:02d}m" if h > 0 or m > 0 else "Ready"
            else:
                info.reset_5h_str = "Ready"
                info.reset_5h_ts = 0

            if weekly_reset_times:
                earliest_weekly = min(weekly_reset_times)
                info.weekly_ts = earliest_weekly.timestamp()
                diff = earliest_weekly - now
                d = diff.days
                h = (diff.seconds) // 3600
                info.weekly_str = f"{d}d {h:02d}h" if d > 0 else f"{h}h"
            else:
                info.weekly_str = "Ready"
                info.weekly_ts = 0
