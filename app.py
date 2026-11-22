import streamlit as st
import pandas as pd
import os
import io
import base64
import smtplib
from PIL import Image
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime

st.set_page_config(page_title="Xóm Trọ Minh Quân", page_icon="🏠", layout="wide")

ROOMS_FILE = "rooms.csv"
HISTORY_FILE = "history.csv"
CONFIG_FILE = "config.csv"

FEEDBACK_FILE = "feedback.csv"

def backup_meter_photo(room_name, b64_img):
    try:
        df_p = read_table("meter_photos", "meter_photos.csv")
        if df_p is None:
            return
        if df_p.empty or "Phòng" not in df_p.columns or "Ảnh công tơ" not in df_p.columns:
            df_p = pd.DataFrame(columns=["Phòng", "Ảnh công tơ"])
        df_p = df_p[df_p["Phòng"].astype(str) != str(room_name)]
        if b64_img:
            df_p = pd.concat([df_p, pd.DataFrame([{"Phòng": str(room_name), "Ảnh công tơ": str(b64_img)}])], ignore_index=True)
        write_table(df_p, "meter_photos", "meter_photos.csv")
    except Exception:
        pass



def render_notification_bell_and_history(df_fb, is_admin=True, room_filter=None):
    if df_fb is None or df_fb.empty:
        st.markdown("""
        <div class="floating-bell-alert" title="Chuông thông báo phản hồi">
            <span class="floating-bell-icon idle">🔔</span>
            <span>Thông báo</span>
            <span class="floating-bell-badge">0</span>
        </div>
        """, unsafe_allow_html=True)
        return

    view_fb = df_fb.copy()
    if room_filter:
        view_fb = view_fb[view_fb["Phòng"].astype(str) == str(room_filter)]

    if is_admin:
        new_count = int((view_fb["Trạng thái"] == "Mới gửi").sum()) if not view_fb.empty else 0
    else:
        # Khách thuê thấy nốt đỏ cảnh báo nếu có phản hồi mới từ chủ trọ hoặc đang xử lý
        new_count = int(((view_fb["Phản hồi của chủ trọ"].astype(str).str.strip() != "") & (view_fb["Trạng thái"] != "Đã xử lý xong")).sum()) if not view_fb.empty else 0

    if new_count > 0:
        rooms_str = ", ".join(view_fb[view_fb["Trạng thái"] == "Mới gửi"]["Phòng"].astype(str).unique().tolist()) if is_admin else (room_filter or "Phòng của bạn")
        label_txt = f"Phản hồi mới ({rooms_str})" if is_admin else "Cập nhật mới"
        st.markdown(f"""
        <div class="floating-bell-alert" title="Có thông báo phản hồi mới">
            <span class="floating-red-dot"></span>
            <span class="floating-bell-icon has-alert">🔔</span>
            <span>{label_txt}</span>
            <span class="floating-bell-badge">{new_count}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="floating-bell-alert" title="Chuông thông báo phản hồi">
            <span class="floating-bell-icon idle">🔔</span>
            <span>Thông báo</span>
            <span class="floating-bell-badge">0</span>
        </div>
        """, unsafe_allow_html=True)

    # Hiển thị lịch sử đầy đủ thời gian ngay trên giao diện để dễ theo dõi
    if not view_fb.empty:
        exp_title = f"🔔 Lịch sử thông báo phản hồi đầy đủ thời gian ({len(view_fb)} mục)" + (f" — 🔴 {new_count} cảnh báo mới" if new_count > 0 else "")
        with st.expander(exp_title, expanded=(new_count > 0)):
            for _, r_item in view_fb.iterrows():
                tg = r_item.get("Thời gian", "")
                p_name = r_item.get("Phòng", "")
                k_name = r_item.get("Khách thuê", "")
                nd = r_item.get("Nội dung phản hồi", "")
                tt = r_item.get("Trạng thái", "")
                tl = str(r_item.get("Phản hồi của chủ trọ", "")).strip()
                is_new_item = (is_admin and tt == "Mới gửi") or ((not is_admin) and tl != "" and tt != "Đã xử lý xong")
                dot_prefix = "🔴 " if is_new_item else "⚪ "
                reply_line = f"<br/><span style='color:#047857;'>↳ <strong>Chủ trọ trả lời:</strong> {tl}</span>" if tl else ""
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.88); border-left:4px solid {'#ef4444' if is_new_item else '#0ea5e9'}; border-radius:10px; padding:10px 14px; margin-bottom:8px; font-size:13.5px; color:#0f172a;">
                    {dot_prefix}<strong>[{tg}]</strong> — <strong>{p_name}</strong> ({k_name}) • <span style="font-weight:700; color:{'#dc2626' if tt=='Mới gửi' else '#0284c7'};">{tt}</span>
                    <div style="margin-top:4px;">📝 {nd}{reply_line}</div>
                </div>
                """, unsafe_allow_html=True)

def load_feedback():
    df_fb = read_table("feedback", FEEDBACK_FILE)
    expected_cols = ["Thời gian", "Phòng", "Khách thuê", "Nội dung phản hồi", "Trạng thái", "Phản hồi của chủ trọ"]
    if df_fb is None:
        return pd.DataFrame(columns=expected_cols)
    if not df_fb.empty:
        for c in expected_cols:
            if c not in df_fb.columns:
                df_fb[c] = ""
        return df_fb[expected_cols].fillna("").astype(str)
    return pd.DataFrame(columns=expected_cols)

def save_feedback(df_fb):
    write_table(df_fb, "feedback", FEEDBACK_FILE)

def send_admin_reply_email(to_email, room_name, tenant_name, issue_text, status_text, reply_text):
    sender_email, app_password = get_email_credentials()
    if not sender_email or not app_password:
        return False, "Chưa cấu hình [email] trong Secrets."
    if not to_email or "@" not in str(to_email):
        return False, "Phòng này chưa có địa chỉ Email khách."
    try:
        msg = MIMEMultipart()
        msg["From"] = f"Xóm Trọ Minh Quân <{sender_email}>"
        msg["To"] = str(to_email).strip()
        msg["Subject"] = f"💬 [Phản hồi từ Chủ trọ] {room_name} - Xóm Trọ Minh Quân"

        reply_section = reply_text.strip() if str(reply_text).strip() else "(Chủ trọ đã cập nhật trạng thái xử lý yêu cầu của bạn)"
        body = f"""📢 THÔNG BÁO PHẢN HỒI TỪ CHỦ TRỌ XÓM TRỌ MINH QUÂN
📍 Địa chỉ: Thôn Mẫn Xá - Xã Yên Phong - Tỉnh Bắc Ninh
🏠 Phòng: {room_name} ({tenant_name})
📌 Trạng thái xử lý: {status_text}
------------------------
📝 Nội dung bạn đã gửi:
{issue_text}

💬 Phản hồi của Chủ trọ:
{reply_section}
------------------------
🌐 Bạn có thể theo dõi trực tiếp tại: {DEFAULT_APP_URL}
Cảm ơn anh/chị đã thông báo cho Xóm Trọ Minh Quân!"""
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, str(to_email).strip(), msg.as_string())
        return True, "Đã gửi email thông báo cho khách thành công!"
    except Exception as e:
        return False, str(e)

def send_feedback_to_admin(room_name, tenant_name, feedback_text):
    sender_email, app_password = get_email_credentials()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # 1. Lưu phản hồi vào sheet riêng "feedback" trên Google Sheets (không đụng vào sheet rooms/history)
    df_fb = load_feedback()
    new_fb = pd.DataFrame([{
        "Thời gian": now_str,
        "Phòng": room_name,
        "Khách thuê": tenant_name,
        "Nội dung phản hồi": feedback_text,
        "Trạng thái": "Mới gửi",
        "Phản hồi của chủ trọ": ""
    }])
    save_feedback(pd.concat([new_fb, df_fb], ignore_index=True))

    # 2. Gửi email thông báo trực tiếp tới hộp thư của Chủ trọ (sender_email)
    if not sender_email or not app_password:
        return True, "Đã lưu phản hồi lên hệ thống (chưa gửi email vì chưa cấu hình [email])."

    try:
        msg = MIMEMultipart()
        msg["From"] = f"Hệ Thống Xóm Trọ Minh Quân <{sender_email}>"
        msg["To"] = sender_email
        msg["Subject"] = f"🔔 [Phản hồi mới] {room_name} ({tenant_name}) - Xóm Trọ Minh Quân"

        body = f"""🔔 THÔNG BÁO PHẢN HỒI MỚI TỪ KHÁCH THUÊ
🏠 Phòng: {room_name}
👤 Khách thuê: {tenant_name}
🕒 Thời gian gửi: {now_str}
------------------------
📝 NỘI DUNG PHẢN HỒI / BÁO SỰ CỐ:
{feedback_text}
------------------------
🌐 Chủ trọ có thể xem và cập nhật trạng thái xử lý trực tiếp tại trang quản trị: {DEFAULT_APP_URL}
"""
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, sender_email, msg.as_string())
        return True, "Đã gửi thông báo qua Email cho chủ trọ thành công!"
    except Exception as e:
        return True, f"Đã lưu phản hồi trên web nhưng gửi email gặp lỗi: {e}"


DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "minhquan2026"
DEFAULT_APP_URL = "https://xom-tro-minh-quan-pxg4pzand8apstxfa7aw66.streamlit.app"

# ==========================================
# DỮ LIỆU GỐC TỪ FILE DATA.XLSX (10 PHÒNG: T5 - T11/2026)
# ==========================================
INITIAL_DATA_RECORDS = [
    {"Phòng": "Phòng P101", "Khách thuê": "Hoàng Bách", "Email": "", "Seri": "16060311", "Pass": "101123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": 5736, "T6": 5862, "T7": 5953, "T8": 6044, "T9": 6132, "T10": 6235, "T11": 6305},
    {"Phòng": "Phòng P102", "Khách thuê": "Hoàng Cường", "Email": "", "Seri": "16060320", "Pass": "102123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": 5111, "T6": 5385, "T7": 5443, "T8": 5551, "T9": 5664, "T10": 5780, "T11": 5890},
    {"Phòng": "Phòng P103", "Khách thuê": "Mạnh Dũng", "Email": "", "Seri": "16060317", "Pass": "103123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": None, "T6": 2727, "T7": 2821, "T8": 2914, "T9": 3094, "T10": 3177, "T11": 3188},
    {"Phòng": "Phòng P104", "Khách thuê": "_", "Email": "", "Seri": "24341817", "Pass": "104123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": None, "T6": None, "T7": 0, "T8": 88, "T9": 115, "T10": 175, "T11": 192},
    {"Phòng": "Phòng P105", "Khách thuê": "Minh Quân", "Email": "", "Seri": "-", "Pass": "105123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": None, "T6": None, "T7": None, "T8": None, "T9": None, "T10": None, "T11": None},
    {"Phòng": "Phòng P106", "Khách thuê": "Quỳnh Anh", "Email": "", "Seri": "16060281", "Pass": "106123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": 4535, "T6": 4645, "T7": 4762, "T8": 4926, "T9": 5058, "T10": 5211, "T11": 5270},
    {"Phòng": "Phòng P107", "Khách thuê": "Mùi Thị Lệ", "Email": "", "Seri": "16060313", "Pass": "107123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": 2145, "T6": 2354, "T7": 2540, "T8": 2754, "T9": 2938, "T10": 3132, "T11": 3338},
    {"Phòng": "Phòng P108", "Khách thuê": "Nguyễn Huyền", "Email": "", "Seri": "16072426", "Pass": "108123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": None, "T6": None, "T7": None, "T8": None, "T9": None, "T10": None, "T11": 3394},
    {"Phòng": "Phòng P109", "Khách thuê": "Thanh Thư", "Email": "", "Seri": "16060328", "Pass": "109123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": 2781, "T6": 2808, "T7": 2828, "T8": 2848, "T9": 2879, "T10": 2902, "T11": 2929},
    {"Phòng": "Phòng P110", "Khách thuê": "Thanh Nhàn", "Email": "", "Seri": "15143276", "Pass": "110123", "Gia": 1000000, "Nuoc": 0, "Rac": 0, "AN": 0, "T5": None, "T6": None, "T7": None, "T8": None, "T9": None, "T10": 2075, "T11": 2179},
]

def build_seeded_tables(gia_dien=3500):
    rooms_rows = []
    hist_rows = []
    month_pairs = [
        ("T5", "T6", "06/2026"),
        ("T6", "T7", "07/2026"),
        ("T7", "T8", "08/2026"),
        ("T8", "T9", "09/2026"),
        ("T9", "T10", "10/2026"),
    ]

    for r in INITIAL_DATA_RECORDS:
        for m_prev, m_curr, ky_label in month_pairs:
            v_curr = r[m_curr]
            if v_curr is not None:
                v_prev = r[m_prev] if r[m_prev] is not None else v_curr
                kwh = max(0, int(v_curr - v_prev))
                t_dien = kwh * gia_dien
                t_dv = r["Nuoc"] + r["Rac"] + r["AN"]
                tong = r["Gia"] + t_dien + t_dv
                note_init = "Chỉ số đầu kỳ nhận phòng" if r[m_prev] is None else ""
                hist_rows.append({
                    "Kỳ thu": ky_label,
                    "Ngày chốt": "Đồng bộ từ sổ Excel",
                    "Phòng": r["Phòng"],
                    "Khách thuê": r["Khách thuê"],
                    "Email khách": r["Email"],
                    "Seri công tơ": r["Seri"],
                    "Tiền phòng": r["Gia"],
                    "Điện cũ": int(v_prev),
                    "Điện mới": int(v_curr),
                    "Tiền nước": r["Nuoc"],
                    "Tiền rác": r["Rac"],
                    "An ninh": r["AN"],
                    "Tiền khác": 0,
                    "Ghi chú": note_init,
                    "Đã thu": True,
                    "Số kWh": kwh,
                    "Tiền điện": t_dien,
                    "Dịch vụ (Nước+Rác+AN)": t_dv,
                    "Tổng cộng": tong,
                    "Đơn giá điện": gia_dien,
                })

        v11 = r["T11"]
        v10 = r["T10"]
        if v11 is not None:
            dien_cu_11 = int(v10) if v10 is not None else int(v11)
            dien_moi_11 = int(v11)
        else:
            dien_cu_11 = 0
            dien_moi_11 = 0

        rooms_rows.append({
            "Phòng": r["Phòng"],
            "Khách thuê": r["Khách thuê"],
            "Email khách": r["Email"],
            "Mật khẩu phòng": r["Pass"],
            "Seri công tơ": r["Seri"],
            "Tiền phòng": r["Gia"],
            "Điện cũ": dien_cu_11,
            "Điện mới": dien_moi_11,
            "Tiền nước": r["Nuoc"],
            "Tiền rác": r["Rac"],
            "An ninh": r["AN"],
            "Tiền khác": 0,
            "Ghi chú": "Mới vào kỳ 11/2026" if (v11 is not None and v10 is None) else "",
            "Đã thu": False,
            "Ảnh công tơ": "",
        })

    df_rooms_seeded = pd.DataFrame(rooms_rows)
    df_hist_seeded = pd.DataFrame(hist_rows)
    if not df_hist_seeded.empty:
        df_hist_seeded = df_hist_seeded.iloc[::-1].reset_index(drop=True)
    return df_rooms_seeded, df_hist_seeded

def get_admin_credentials():
    try:
        user = st.secrets["auth"]["admin_user"]
        pwd = str(st.secrets["auth"]["admin_pass"])
        return user, pwd
    except Exception:
        return DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS

def get_email_credentials():
    try:
        sender = str(st.secrets["email"]["sender_email"]).strip()
        app_pwd = str(st.secrets["email"]["app_password"]).replace(" ", "").strip()
        if sender and app_pwd:
            return sender, app_pwd
    except Exception:
        pass
    return None, None

def compress_image_to_base64(uploaded_file, max_width=560, quality=52):
    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if w > max_width:
            new_h = int(h * (max_width / w))
            img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
        for q_try in [quality, 42, 32, 24]:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=q_try, optimize=True)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            if len(b64_str) <= 42000:
                return f"data:image/jpeg;base64,{b64_str}"
        img = img.resize((400, int(img.size[1] * (400 / img.size[0]))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=30, optimize=True)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64_str[:42000]}"
    except Exception as e:
        st.error(f"Lỗi xử lý ảnh: {e}")
        return ""

def send_invoice_email(to_email, subject, body_text, meter_img_b64=""):
    sender_email, app_password = get_email_credentials()
    if not sender_email or not app_password:
        return False, "Chưa cấu hình [email] trong Secrets của Streamlit Cloud."
    try:
        msg = MIMEMultipart()
        msg["From"] = f"Xóm Trọ Minh Quân <{sender_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        if meter_img_b64 and meter_img_b64.startswith("data:image"):
            try:
                raw_b64 = meter_img_b64.split(",", 1)[1]
                img_bytes = base64.b64decode(raw_b64)
                img_part = MIMEImage(img_bytes, _subtype="jpeg")
                img_part.add_header("Content-Disposition", "attachment", filename="anh_cong_to_dien.jpg")
                msg.attach(img_part)
            except Exception:
                pass

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True, "Thành công"
    except Exception as e:
        return False, str(e)

def build_invoice_message(row_p, thang_ghi, gia_dien):
    seri_line = f" (Công tơ: {row_p['Seri công tơ']})" if str(row_p.get('Seri công tơ', '')).strip() else ""
    khac_line = ""
    if int(row_p.get('Tiền khác', 0)) != 0 or str(row_p.get('Ghi chú', '')).strip():
        note_txt = f" ({row_p['Ghi chú']})" if str(row_p.get('Ghi chú', '')).strip() else ""
        khac_line = f"\n• Khoản khác{note_txt}: {int(row_p.get('Tiền khác', 0)):,.0f} đ"

    trang_thai = "✅ Đã thanh toán" if row_p.get("Đã thu", False) else "⏳ Chưa thanh toán"
    photo_note = "\n📸 Ảnh chụp chỉ số công tơ điện đã được đính kèm & hiển thị trực tiếp trên web!" if str(row_p.get("Ảnh công tơ", "")).strip() else ""

    return f"""📢 THÔNG BÁO TIỀN PHÒNG XÓM TRỌ MINH QUÂN - KỲ {thang_ghi}
📍 Địa chỉ: Thôn Mẫn Xá - Xã Yên Phong - Tỉnh Bắc Ninh
🏠 Phòng: {row_p['Phòng']} ({row_p['Khách thuê']}){seri_line}
📌 Trạng thái: {trang_thai}
------------------------
• Tiền thuê phòng: {int(row_p['Tiền phòng']):,.0f} đ
• Chỉ số điện: {int(row_p['Điện cũ']):,.0f} ➔ {int(row_p['Điện mới']):,.0f} ({int(row_p['Số kWh']):,.0f} kWh)
• Tiền điện ({gia_dien:,.0f}đ/kWh): {int(row_p['Tiền điện']):,.0f} đ
• Tiền nước: {int(row_p['Tiền nước']):,.0f} đ
• Tiền rác: {int(row_p['Tiền rác']):,.0f} đ
• Phí an ninh: {int(row_p['An ninh']):,.0f} đ{khac_line}
------------------------
💰 TỔNG CỘNG CẦN THANH TOÁN: {int(row_p['Tổng cộng']):,.0f} đ{photo_note}

🌐 Xem ảnh công tơ & tra cứu lịch sử online tại: {DEFAULT_APP_URL}
🔑 Mật khẩu phòng của bạn: {row_p['Mật khẩu phòng']}

Anh/chị vui lòng thanh toán sớm giúp Xóm Trọ Minh Quân nhé. Xin cảm ơn!"""

def advance_month_str(thang_ghi):
    try:
        parts = str(thang_ghi).strip().split("/")
        if len(parts) == 2:
            m = int(parts[0])
            y = int(parts[1])
            if m == 12:
                return f"01/{y + 1}"
            return f"{m + 1:02d}/{y}"
    except Exception:
        pass
    return thang_ghi

@st.cache_resource
def get_gspread_client_cached():
    try:
        if "gcp_service_account" in st.secrets and "sheet_url" in st.secrets:
            import gspread
            from google.oauth2.service_account import Credentials
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes
            )
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def get_gsheet_client():
    try:
        gc = get_gspread_client_cached()
        if gc is not None and "sheet_url" in st.secrets:
            return gc.open_by_url(st.secrets["sheet_url"])
    except Exception:
        pass
    return None

@st.cache_data(ttl=12, show_spinner=False)
def _fetch_gsheet_records(sheet_name):
    sh = get_gsheet_client()
    if sh is None:
        return None
    import gspread
    try:
        ws = sh.worksheet(sheet_name)
        return ws.get_all_records()
    except gspread.WorksheetNotFound:
        return []

def read_table(sheet_name, csv_file):
    sh = get_gsheet_client()
    if sh is not None:
        try:
            records = _fetch_gsheet_records(sheet_name)
            if records is None:
                return None
            if records:
                return pd.DataFrame(records)
            return pd.DataFrame()
        except Exception as e:
            st.warning(f"⚠️ Đang đồng bộ lại kết nối Google Sheets ({sheet_name}): {e}")
            return None
    else:
        if os.path.exists(csv_file):
            return pd.read_csv(csv_file)
        return pd.DataFrame()

def write_table(df, sheet_name, csv_file):
    sh = get_gsheet_client()
    if sh is not None:
        try:
            try:
                ws = sh.worksheet(sheet_name)
            except Exception:
                ws = sh.add_worksheet(title=sheet_name, rows="1000", cols="25")
            ws.clear()
            data_to_write = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            ws.update(values=data_to_write, value_input_option="RAW")
            _fetch_gsheet_records.clear()
            return
        except Exception as e:
            st.error(f"Lỗi ghi Google Sheets: {e}")
    df.to_csv(csv_file, index=False)

if "editor_key" not in st.session_state:
    st.session_state.editor_key = 0
if "role" not in st.session_state:
    st.session_state.role = None
if "customer_room" not in st.session_state:
    st.session_state.customer_room = None

# ==========================================
# GIAO DIỆN MÀU SẮC SINH ĐỘNG & HIỆN ĐẠI
# ==========================================
st.markdown("""
<style>
    :root {
        --loft-bg-img: url("data:image/jpeg;base64,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