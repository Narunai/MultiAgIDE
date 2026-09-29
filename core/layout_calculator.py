import ctypes
from ctypes import wintypes
from typing import List, Dict


class RECT(ctypes.Structure):
    _fields_ = [
        ('left', wintypes.LONG),
        ('top', wintypes.LONG),
        ('right', wintypes.LONG),
        ('bottom', wintypes.LONG)
    ]


class LayoutCalculator:
    def __init__(self):
        self.user32 = ctypes.windll.user32

    def get_working_area(self) -> Dict[str, int]:
        """ดึงขนาด Working Area ของหน้าจอ (หัก Taskbar ออกแล้ว)"""
        rect = RECT()
        SPI_GETWORKAREA = 0x0030
        success = self.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        if success:
            return {
                "x": rect.left,
                "y": rect.top,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top
            }
        return {"x": 0, "y": 0, "width": 1536, "height": 816}

    def compute_slot_rects(self, visible_slots: List[int], total_area: Dict[str, int] = None, reserve_deck_width: int = 380) -> Dict[int, Dict[str, int]]:
        """
        คำนวณพิกัด (x, y, width, height) สำหรับสล็อต Antigravity IDE
        โดยเว้นพื้นที่ฝั่งขวาไว้สำหรับ Control Deck (reserve_deck_width)

        กฎการจัดหน้าต่าง:
        - หน้าจอรองรับการจัดวางหลักได้ 1 ถึง 6 สล็อต (Display 1 ถึง Display 6)
        - สำหรับสล็อตตั้งแต่ Account 7 เป็นต้นไป (slot_id >= 7) จะใช้พิกัดตำแหน่งเดียวกับ Display 1 (Slot 1)
          เพื่อให้สามารถสลับกันเปิดปิดใช้งานที่ตำแหน่งเดียวกันได้
        """
        if total_area is None:
            total_area = self.get_working_area()

        ax = total_area["x"]
        ay = total_area["y"]
        # พื้นที่ทำงานสำหรับ IDE (หัก Control Deck ออก)
        aw = max(600, total_area["width"] - reserve_deck_width)
        ah = total_area["height"]

        if not visible_slots:
            return {}

        # แยกสล็อตกลุ่ม Display 1 (Slot 1 และ Slot 7 เป็นต้นไป)
        d1_slots = [s for s in visible_slots if s == 1 or s >= 7]
        other_slots = [s for s in visible_slots if 2 <= s <= 6]

        # สร้างรายการสล็อตจำลองเพื่อคำนวณตำแหน่ง Grid หลัก (1 ถึง 6)
        primary_slots = []
        if d1_slots:
            primary_slots.append(1)
        for s in sorted(other_slots):
            primary_slots.append(s)

        count = len(primary_slots)
        base_rects = {}

        if count == 1:
            # 1 สล็อต: เต็มพื้นที่ฝั่ง IDE (3/4 จอ)
            base_rects[primary_slots[0]] = {"x": ax, "y": ay, "width": aw, "height": ah}

        elif count == 2:
            # 2 สล็อต: แบ่งครึ่งซ้าย-ขวา 50% / 50%
            w = aw // 2
            base_rects[primary_slots[0]] = {"x": ax, "y": ay, "width": w, "height": ah}
            base_rects[primary_slots[1]] = {"x": ax + w, "y": ay, "width": aw - w, "height": ah}

        elif count == 3:
            # 3 สล็อต: 3 คอลัมน์เท่ากัน
            w1 = aw // 3
            w2 = aw // 3
            w3 = aw - (w1 + w2)
            base_rects[primary_slots[0]] = {"x": ax, "y": ay, "width": w1, "height": ah}
            base_rects[primary_slots[1]] = {"x": ax + w1, "y": ay, "width": w2, "height": ah}
            base_rects[primary_slots[2]] = {"x": ax + w1 + w2, "y": ay, "width": w3, "height": ah}

        elif count == 4:
            # 4 สล็อต: 2 แถว x 2 คอลัมน์ (Quad Grid 2x2)
            w_left = aw // 2
            w_right = aw - w_left
            h_top = ah // 2
            h_bottom = ah - h_top

            base_rects[primary_slots[0]] = {"x": ax, "y": ay, "width": w_left, "height": h_top}
            base_rects[primary_slots[1]] = {"x": ax + w_left, "y": ay, "width": w_right, "height": h_top}
            base_rects[primary_slots[2]] = {"x": ax, "y": ay + h_top, "width": w_left, "height": h_bottom}
            base_rects[primary_slots[3]] = {"x": ax + w_left, "y": ay + h_top, "width": w_right, "height": h_bottom}

        elif count == 5:
            # 5 สล็อต: 3 ช่องบน, 2 ช่องล่าง
            h_top = ah // 2
            h_bottom = ah - h_top
            w_top = aw // 3
            w_top_last = aw - (w_top * 2)
            w_bot = aw // 2
            w_bot_last = aw - w_bot

            base_rects[primary_slots[0]] = {"x": ax, "y": ay, "width": w_top, "height": h_top}
            base_rects[primary_slots[1]] = {"x": ax + w_top, "y": ay, "width": w_top, "height": h_top}
            base_rects[primary_slots[2]] = {"x": ax + (w_top * 2), "y": ay, "width": w_top_last, "height": h_top}
            base_rects[primary_slots[3]] = {"x": ax, "y": ay + h_top, "width": w_bot, "height": h_bottom}
            base_rects[primary_slots[4]] = {"x": ax + w_bot, "y": ay + h_top, "width": w_bot_last, "height": h_bottom}

        elif count >= 6:
            # 6 สล็อต: 2 แถว x 3 คอลัมน์ (2x3 Matrix Grid)
            h_top = ah // 2
            h_bottom = ah - h_top
            w_col1 = aw // 3
            w_col2 = aw // 3
            w_col3 = aw - (w_col1 + w_col2)

            slots_to_map = primary_slots[:6]
            base_rects[slots_to_map[0]] = {"x": ax, "y": ay, "width": w_col1, "height": h_top}
            base_rects[slots_to_map[1]] = {"x": ax + w_col1, "y": ay, "width": w_col2, "height": h_top}
            base_rects[slots_to_map[2]] = {"x": ax + w_col1 + w_col2, "y": ay, "width": w_col3, "height": h_top}
            base_rects[slots_to_map[3]] = {"x": ax, "y": ay + h_top, "width": w_col1, "height": h_bottom}
            base_rects[slots_to_map[4]] = {"x": ax + w_col1, "y": ay + h_top, "width": w_col2, "height": h_bottom}
            base_rects[slots_to_map[5]] = {"x": ax + w_col1 + w_col2, "y": ay + h_top, "width": w_col3, "height": h_bottom}

        results = {}
        for s in other_slots:
            if s in base_rects:
                results[s] = base_rects[s]

        d1_rect = base_rects.get(1)
        if d1_rect:
            for s in d1_slots:
                results[s] = d1_rect

        return results

