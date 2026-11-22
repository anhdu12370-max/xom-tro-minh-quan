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

def load_feedback():
    df_fb = read_table("feedback", FEEDBACK_FILE)
    expected_cols = ["Thời gian", "Phòng", "Khách thuê", "Nội dung phản hồi", "Trạng thái", "Phản hồi của chủ trọ"]
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

def compress_image_to_base64(uploaded_file, max_width=720, quality=65):
    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if w > max_width:
            new_h = int(h * (max_width / w))
            img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        # Giới hạn dưới 48,000 ký tự để vừa khít 1 ô Google Sheets (tối đa 50,000 ký tự)
        if len(b64_str) > 48000:
            buf = io.BytesIO()
            img = img.resize((480, int(img.size[1] * (480 / img.size[0]))), Image.Resampling.LANCZOS)
            img.save(buf, format="JPEG", quality=50, optimize=True)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64_str}"
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

def get_gsheet_client():
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
            client = gspread.authorize(creds)
            return client.open_by_url(st.secrets["sheet_url"])
    except Exception:
        pass
    return None

def read_table(sheet_name, csv_file):
    sh = get_gsheet_client()
    if sh is not None:
        try:
            ws = sh.worksheet(sheet_name)
            records = ws.get_all_records()
            if records:
                return pd.DataFrame(records)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()
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
            ws.update(data_to_write)
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
    /* Nền gradient pastel sinh động, tươi sáng */
    .stApp {
        background: linear-gradient(135deg, #e0f2fe 0%, #f0fdf4 45%, #fef3c7 100%);
        background-attachment: fixed;
    }

    /* Thanh Sidebar nổi bật */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #eff6ff 60%, #ecfdf5 100%);
        border-right: 2px solid #bae6fd;
    }

    /* Banner tiêu đề rực rỡ */
    .hero-banner {
        background: linear-gradient(120deg, #2563eb 0%, #0ea5e9 50%, #10b981 100%);
        color: white;
        padding: 22px 28px;
        border-radius: 18px;
        box-shadow: 0 10px 25px rgba(37, 99, 235, 0.22);
        margin-bottom: 20px;
    }
    .hero-banner h1 {
        color: white !important;
        margin: 0;
        font-size: 28px;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .hero-banner p {
        color: #e0f2fe !important;
        margin: 6px 0 0 0;
        font-size: 15px;
    }

    /* Thẻ chỉ số (Metric Cards) sống động */
    .metric-card {
        border-radius: 16px;
        padding: 18px 20px;
        border-left: 6px solid #3b82f6;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
        margin-bottom: 12px;
        transition: transform 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
    }
    .metric-card.electric {
        border-left-color: #f59e0b;
        background: linear-gradient(135deg, #fffbeb 0%, #fde68a 100%);
    }
    .metric-card.service {
        border-left-color: #06b6d4;
        background: linear-gradient(135deg, #ecfeff 0%, #a5f3fc 100%);
    }
    .metric-card.room {
        border-left-color: #6366f1;
        background: linear-gradient(135deg, #eef2ff 0%, #c7d2fe 100%);
    }
    .metric-card.total {
        border-left-color: #10b981;
        background: linear-gradient(135deg, #ecfdf5 0%, #a7f3d0 100%);
    }
    .metric-title {
        font-size: 13px;
        font-weight: 800;
        color: #334155;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 900;
        color: #0f172a;
    }
    .metric-sub {
        font-size: 12px;
        font-weight: 600;
        color: #475569;
        margin-top: 4px;
    }

    /* Thẻ phòng hiển thị ảnh công tơ */
    .meter-card {
        background: rgba(255, 255, 255, 0.92);
        border: 1.5px solid #bae6fd;
        border-radius: 16px;
        padding: 14px;
        box-shadow: 0 4px 14px rgba(14, 165, 233, 0.1);
        margin-bottom: 14px;
    }
    .meter-badge {
        display: inline-block;
        background: linear-gradient(90deg, #0284c7, #0d9488);
        color: white;
        font-weight: 700;
        font-size: 12px;
        padding: 3px 10px;
        border-radius: 999px;
        margin-bottom: 6px;
    }


    /* Chuông thông báo đỏ nổi ở góc trên bên phải màn hình khi có phản hồi mới */
    @keyframes bell-shake {
        0%, 100% { transform: rotate(0deg); }
        15% { transform: rotate(14deg); }
        30% { transform: rotate(-14deg); }
        45% { transform: rotate(10deg); }
        60% { transform: rotate(-10deg); }
        75% { transform: rotate(4deg); }
    }
    .floating-bell-alert {
        position: fixed;
        top: 64px;
        right: 22px;
        z-index: 999999;
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: #ffffff;
        padding: 10px 16px;
        border-radius: 999px;
        box-shadow: 0 8px 22px rgba(220, 38, 38, 0.45);
        border: 2px solid #ffffff;
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 800;
        font-size: 13.5px;
        cursor: default;
    }
    .floating-bell-icon {
        display: inline-block;
        font-size: 18px;
        animation: bell-shake 1.4s infinite;
    }
    .floating-bell-badge {
        background-color: #ffffff;
        color: #dc2626;
        font-weight: 900;
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 999px;
    }

    /* Tùy chỉnh Tabs nổi bật */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255, 255, 255, 0.7);
        padding: 6px;
        border-radius: 14px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        font-weight: 700;
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)

def load_config():
    df_cfg = read_table("config", CONFIG_FILE)
    if not df_cfg.empty and "gia_dien" in df_cfg.columns and "thang_ghi" in df_cfg.columns:
        return int(float(df_cfg.iloc[0]["gia_dien"])), str(df_cfg.iloc[0]["thang_ghi"])
    default_gia = 3500
    default_thang = "11/2026"
    save_config(default_gia, default_thang)
    return default_gia, default_thang

def save_config(gia_dien, thang_ghi):
    df_cfg = pd.DataFrame([{"gia_dien": int(gia_dien), "thang_ghi": str(thang_ghi)}])
    write_table(df_cfg, "config", CONFIG_FILE)

def load_rooms():
    default_cols = {
        "Phòng": "Phòng mới",
        "Khách thuê": "",
        "Email khách": "",
        "Mật khẩu phòng": "123456",
        "Seri công tơ": "",
        "Tiền phòng": 1000000,
        "Điện cũ": 0,
        "Điện mới": 0,
        "Tiền nước": 0,
        "Tiền rác": 0,
        "An ninh": 0,
        "Tiền khác": 0,
        "Ghi chú": "",
        "Đã thu": False,
        "Ảnh công tơ": "",
    }
    ordered_cols = [
        "Phòng", "Khách thuê", "Email khách", "Mật khẩu phòng", "Seri công tơ", "Tiền phòng",
        "Điện cũ", "Điện mới", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác", "Ghi chú", "Đã thu", "Ảnh công tơ"
    ]
    df = read_table("rooms", ROOMS_FILE)

    # Nếu đang rỗng hoặc chỉ có 2 phòng mẫu cũ (Phòng 101, Phòng 102) thì tự động nạp 10 phòng thật từ data.xlsx
    is_sample_only = (
        not df.empty
        and len(df) == 2
        and set(df["Phòng"].astype(str).tolist()) == {"Phòng 101", "Phòng 102"}
    )

    if df.empty or is_sample_only:
        df_seeded, df_hist_seeded = build_seeded_tables(gia_dien=3500)
        write_table(df_seeded, "rooms", ROOMS_FILE)
        existing_hist = read_table("history", HISTORY_FILE)
        if existing_hist.empty and not df_hist_seeded.empty:
            write_table(df_hist_seeded, "history", HISTORY_FILE)
        save_config(3500, "11/2026")
        return df_seeded[ordered_cols]

    changed = False
    for col, default_val in default_cols.items():
        if col not in df.columns:
            df[col] = default_val
            changed = True
    df = df[ordered_cols]
    df["Phòng"] = df["Phòng"].astype(str)
    df["Khách thuê"] = df["Khách thuê"].fillna("").astype(str)
    df["Email khách"] = df["Email khách"].fillna("").astype(str).str.strip()
    df["Mật khẩu phòng"] = df["Mật khẩu phòng"].fillna("123456").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["Seri công tơ"] = df["Seri công tơ"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["Ghi chú"] = df["Ghi chú"].fillna("").astype(str)
    df["Ảnh công tơ"] = df["Ảnh công tơ"].fillna("").astype(str)
    for num_col in ["Tiền phòng", "Điện cũ", "Điện mới", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác"]:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0).astype(int)
    df["Đã thu"] = df["Đã thu"].apply(lambda x: str(x).strip().lower() in ["true", "1", "yes"])
    if changed:
        write_table(df, "rooms", ROOMS_FILE)
    return df

def load_history():
    df_h = read_table("history", HISTORY_FILE)
    if not df_h.empty:
        for num_col in ["Tiền phòng", "Điện cũ", "Điện mới", "Số kWh", "Tiền điện", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác", "Dịch vụ (Nước+Rác+AN)", "Tổng cộng", "Đơn giá điện"]:
            if num_col in df_h.columns:
                df_h[num_col] = pd.to_numeric(df_h[num_col], errors="coerce").fillna(0)
        for str_col in ["Phòng", "Seri công tơ", "Ghi chú", "Email khách"]:
            if str_col in df_h.columns:
                df_h[str_col] = df_h[str_col].fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
    return df_h

def save_history(df_h):
    write_table(df_h, "history", HISTORY_FILE)

# ==========================================
# MÀN HÌNH ĐĂNG NHẬP (HÌNH NỀN DẠNG DÃY PHÒNG TRỌ ẤM ÁP & HIỆN ĐẠI)
# ==========================================
def render_login_screen(df_rooms):
    st.markdown("""
    <style>
        /* Hình nền kiến trúc dãy nhà trọ hiện đại, ấm áp phủ toàn màn hình khi đăng nhập */
        .stApp {
            background-image:
                linear-gradient(135deg, rgba(15, 23, 42, 0.52) 0%, rgba(30, 58, 138, 0.42) 50%, rgba(6, 78, 59, 0.48) 100%),
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 900'%3E%3Cdefs%3E%3ClinearGradient id='sky' x1='0' y1='0' x2='0' y2='1'%3E%3Cstop offset='0%25' stop-color='%2338bdf8'/%3E%3Cstop offset='55%25' stop-color='%23bae6fd'/%3E%3Cstop offset='100%25' stop-color='%23fef3c7'/%3E%3C/linearGradient%3E%3ClinearGradient id='wall1' x1='0' y1='0' x2='0' y2='1'%3E%3Cstop offset='0%25' stop-color='%23fffbeb'/%3E%3Cstop offset='100%25' stop-color='%23fde68a'/%3E%3C/linearGradient%3E%3ClinearGradient id='wall2' x1='0' y1='0' x2='0' y2='1'%3E%3Cstop offset='0%25' stop-color='%23f8fafc'/%3E%3Cstop offset='100%25' stop-color='%23e2e8f0'/%3E%3C/linearGradient%3E%3ClinearGradient id='roof' x1='0' y1='0' x2='1' y2='0'%3E%3Cstop offset='0%25' stop-color='%231e3a8a'/%3E%3Cstop offset='100%25' stop-color='%230284c7'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='1600' height='900' fill='url(%23sky)'/%3E%3Ccircle cx='1320' cy='160' r='70' fill='%23fde047' opacity='0.85'/%3E%3C!-- Mây trời --%3E%3Cg fill='%23ffffff' opacity='0.75'%3E%3Ccircle cx='260' cy='150' r='36'/%3E%3Ccircle cx='300' cy='140' r='46'/%3E%3Ccircle cx='348' cy='152' r='34'/%3E%3Ccircle cx='880' cy='115' r='30'/%3E%3Ccircle cx='918' cy='108' r='40'/%3E%3Ccircle cx='958' cy='118' r='28'/%3E%3C/g%3E%3C!-- Sân gạch & cây xanh --%3E%3Crect x='0' y='730' width='1600' height='170' fill='%23cbd5e1'/%3E%3Crect x='0' y='720' width='1600' height='16' fill='%2394a3b8'/%3E%3C!-- Tòa dãy phòng trọ 2 tầng bên trái & phải --%3E%3Crect x='110' y='250' width='1380' height='470' rx='12' fill='url(%23wall2)' stroke='%2394a3b8' stroke-width='3'/%3E%3Cpolygon points='85,255 800,145 1515,255' fill='url(%23roof)'/%3E%3Crect x='110' y='480' width='1380' height='18' fill='%23334155'/%3E%3C!-- Lan can tầng 2 --%3E%3Crect x='110' y='432' width='1380' height='8' fill='%23475569'/%3E%3Cg stroke='%2364748b' stroke-width='4'%3E%3Cline x1='150' y1='432' x2='150' y2='480'/%3E%3Cline x1='210' y1='432' x2='210' y2='480'/%3E%3Cline x1='270' y1='432' x2='270' y2='480'/%3E%3Cline x1='330' y1='432' x2='330' y2='480'/%3E%3Cline x1='390' y1='432' x2='390' y2='480'/%3E%3Cline x1='450' y1='432' x2='450' y2='480'/%3E%3Cline x1='1150' y1='432' x2='1150' y2='480'/%3E%3Cline x1='1210' y1='432' x2='1210' y2='480'/%3E%3Cline x1='1270' y1='432' x2='1270' y2='480'/%3E%3Cline x1='1330' y1='432' x2='1330' y2='480'/%3E%3Cline x1='1390' y1='432' x2='1390' y2='480'/%3E%3Cline x1='1450' y1='432' x2='1450' y2='480'/%3E%3C/g%3E%3C!-- Các ô cửa phòng trọ Tầng 2 (sáng đèn ấm áp) --%3E%3Cg%3E%3Crect x='160' y='295' width='75' height='137' rx='4' fill='%2392400e'/%3E%3Crect x='255' y='310' width='95' height='80' rx='6' fill='%23fef08a' stroke='%230284c7' stroke-width='4'/%3E%3Crect x='410' y='295' width='75' height='137' rx='4' fill='%2392400e'/%3E%3Crect x='505' y='310' width='95' height='80' rx='6' fill='%23fef08a' stroke='%230284c7' stroke-width='4'/%3E%3Crect x='1000' y='295' width='75' height='137' rx='4' fill='%2392400e'/%3E%3Crect x='1095' y='310' width='95' height='80' rx='6' fill='%23fef08a' stroke='%230284c7' stroke-width='4'/%3E%3Crect x='1250' y='295' width='75' height='137' rx='4' fill='%2392400e'/%3E%3Crect x='1345' y='310' width='95' height='80' rx='6' fill='%23fef08a' stroke='%230284c7' stroke-width='4'/%3E%3C/g%3E%3C!-- Các ô cửa phòng trọ Tầng 1 --%3E%3Cg%3E%3Crect x='160' y='535' width='80' height='185' rx='4' fill='%2378350f'/%3E%3Crect x='260' y='550' width='95' height='85' rx='6' fill='%23fde047' stroke='%230284c7' stroke-width='4'/%3E%3Crect x='410' y='535' width='80' height='185' rx='4' fill='%2378350f'/%3E%3Crect x='510' y='550' width='95' height='85' rx='6' fill='%23fde047' stroke='%230284c7' stroke-width='4'/%3E%3Crect x='1000' y='535' width='80' height='185' rx='4' fill='%2378350f'/%3E%3Crect x='1100' y='550' width='95' height='85' rx='6' fill='%23fde047' stroke='%230284c7' stroke-width='4'/%3E%3Crect x='1250' y='535' width='80' height='185' rx='4' fill='%2378350f'/%3E%3Crect x='1350' y='550' width='95' height='85' rx='6' fill='%23fde047' stroke='%230284c7' stroke-width='4'/%3E%3C/g%3E%3C!-- Cây xanh trang trí hai bên sân trọ --%3E%3Cg%3E%3Crect x='52' y='620' width='16' height='100' fill='%2378350f'/%3E%3Ccircle cx='60' cy='590' r='48' fill='%2310b981'/%3E%3Ccircle cx='35' cy='615' r='34' fill='%23059669'/%3E%3Ccircle cx='85' cy='615' r='34' fill='%23059669'/%3E%3Crect x='1532' y='620' width='16' height='100' fill='%2378350f'/%3E%3Ccircle cx='1540' cy='590' r='48' fill='%2310b981'/%3E%3Ccircle cx='1515' cy='615' r='34' fill='%23059669'/%3E%3Ccircle cx='1565' cy='615' r='34' fill='%23059669'/%3E%3C/g%3E%3C/svg%3E");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }

        /* Khung đăng nhập kính mờ (Glassmorphism) nổi bật trên nền dãy phòng trọ */
        [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {
            background: rgba(255, 255, 255, 0.90);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            padding: 26px 28px 30px 28px;
            border-radius: 24px;
            box-shadow: 0 20px 50px rgba(15, 23, 42, 0.35);
            border: 1.5px solid rgba(255, 255, 255, 0.85);
        }
    </style>
    """, unsafe_allow_html=True)

    col_left, col_mid, col_right = st.columns([1, 1.55, 1])
    with col_mid:
        st.markdown("""
        <div class="hero-banner" style="text-align: center;">
            <h1>🏠 Xóm Trọ Minh Quân</h1>
            <p style="font-weight: 700; color: #ffffff !important; font-size: 16px; margin-top: 4px;">📍 Thôn Mẫn Xá - Xã Yên Phong - Tỉnh Bắc Ninh</p>
            <p>Cổng thông tin tra cứu hóa đơn, ảnh công tơ điện & quản lý phòng trọ trực tuyến</p>
        </div>
        """, unsafe_allow_html=True)

        login_tab_cus, login_tab_adm = st.tabs(["👤 Khách thuê (Xem hóa đơn & Ảnh đồng hồ)", "🔑 Chủ trọ (Admin)"])

        with login_tab_cus:
            st.info("Chọn phòng của bạn và nhập **Mật khẩu phòng** do chủ trọ cung cấp để xem tiền phòng, ảnh đồng hồ điện & lịch sử.")
            if df_rooms.empty:
                st.warning("Chưa có danh sách phòng. Vui lòng liên hệ chủ trọ.")
            else:
                room_list = df_rooms["Phòng"].tolist()
                selected_room = st.selectbox("Chọn phòng của bạn:", room_list)
                room_pass_input = st.text_input("Mật khẩu phòng:", type="password", placeholder="Nhập mật khẩu phòng...")
                if st.button("🔓 Đăng nhập xem phòng", type="primary", use_container_width=True):
                    matched_row = df_rooms[df_rooms["Phòng"] == selected_room].iloc[0]
                    correct_pass = str(matched_row["Mật khẩu phòng"]).strip()
                    if room_pass_input.strip() == correct_pass:
                        st.session_state.role = "customer"
                        st.session_state.customer_room = selected_room
                        st.rerun()
                    else:
                        st.error("❌ Sai mật khẩu phòng! Vui lòng kiểm tra lại hoặc liên hệ chủ trọ.")

        with login_tab_adm:
            st.info("Khu vực dành riêng cho **Chủ trọ** quản lý, cập nhật ảnh công tơ, nhập số điện và chốt sổ.")
            admin_u_in = st.text_input("Tài khoản Admin:", placeholder="Nhập tài khoản...")
            admin_p_in = st.text_input("Mật khẩu Admin:", type="password", placeholder="Nhập mật khẩu...")
            if st.button("🔑 Đăng nhập Quản trị", type="primary", use_container_width=True):
                adm_user, adm_pass = get_admin_credentials()
                if admin_u_in.strip() == adm_user and admin_p_in.strip() == adm_pass:
                    st.session_state.role = "admin"
                    st.session_state.customer_room = None
                    st.rerun()
                else:
                    st.error("❌ Tài khoản hoặc mật khẩu Admin không chính xác!")

# ==========================================
# GIAO DIỆN KHÁCH THUÊ (CHỈ XEM)
# ==========================================
def render_customer_view(df_rooms, gia_dien, thang_ghi):
    my_room_name = st.session_state.customer_room
    matched = df_rooms[df_rooms["Phòng"] == my_room_name]
    if matched.empty:
        st.error("Không tìm thấy dữ liệu phòng của bạn. Vui lòng đăng nhập lại.")
        if st.button("Quay lại đăng nhập"):
            st.session_state.role = None
            st.rerun()
        return

    row = matched.iloc[0]
    so_kwh = max(0, int(row["Điện mới"]) - int(row["Điện cũ"]))
    tien_dien = so_kwh * gia_dien
    tien_dv = int(row["Tiền nước"]) + int(row["Tiền rác"]) + int(row["An ninh"])
    tien_khac = int(row.get("Tiền khác", 0))
    ghi_chu = str(row.get("Ghi chú", "")).strip()
    seri_ct = str(row.get("Seri công tơ", "")).strip()
    anh_ct = str(row.get("Ảnh công tơ", "")).strip()
    tong_cong = int(row["Tiền phòng"]) + tien_dien + tien_dv + tien_khac

    with st.sidebar:
        st.header("👤 Tài khoản Khách thuê")
        seri_info = f"\n\n🔌 Seri công tơ: **{seri_ct}**" if seri_ct else ""
        st.success(f"Đang xem: **{my_room_name}**\n\nKhách thuê: **{row['Khách thuê']}**{seri_info}")
        st.caption("🔒 Chế độ chỉ xem (dữ liệu được đồng bộ trực tiếp từ chủ trọ).")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state.role = None
            st.session_state.customer_room = None
            st.rerun()

    trang_thai_text = "✅ ĐÃ THANH TOÁN" if row["Đã thu"] else "⏳ CHƯA THANH TOÁN"
    seri_badge = f" • 🔌 Công tơ: {seri_ct}" if seri_ct else ""
    st.markdown(f"""
    <div class="hero-banner">
        <h1>🏠 Xóm Trọ Minh Quân — {my_room_name} ({row['Khách thuê']})</h1>
        <p style="font-weight: 700; color: #ffffff !important; font-size: 15px; margin-top: 4px;">📍 Thôn Mẫn Xá - Xã Yên Phong - Tỉnh Bắc Ninh</p>
        <p>📋 Hóa đơn kỳ {thang_ghi}{seri_badge} | Trạng thái: <strong>{trang_thai_text}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card room">
            <div class="metric-title">🏢 Tiền thuê phòng</div>
            <div class="metric-value">{row['Tiền phòng']:,.0f} đ</div>
            <div class="metric-sub">Giá cố định hàng tháng</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card electric">
            <div class="metric-title">⚡ Tiền điện ({so_kwh} kWh)</div>
            <div class="metric-value">{tien_dien:,.0f} đ</div>
            <div class="metric-sub">Số cũ: {row['Điện cũ']} ➔ Mới: {row['Điện mới']} ({gia_dien:,.0f}đ)</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        khac_sub = f" • Khác {tien_khac:,.0f}" if tien_khac != 0 else ""
        st.markdown(f"""
        <div class="metric-card service">
            <div class="metric-title">💧 Dịch vụ & Phí khác</div>
            <div class="metric-value">{(tien_dv + tien_khac):,.0f} đ</div>
            <div class="metric-sub">Nước {row['Tiền nước']:,.0f} • Rác {row['Tiền rác']:,.0f} • AN {row['An ninh']:,.0f}{khac_sub}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card total">
            <div class="metric-title">💰 Tổng cần thanh toán</div>
            <div class="metric-value">{tong_cong:,.0f} đ</div>
            <div class="metric-sub">{trang_thai_text}</div>
        </div>
        """, unsafe_allow_html=True)

    if tien_khac != 0 or ghi_chu:
        st.info(f"📝 **Chi tiết khoản thu khác / Ghi chú:** {tien_khac:,.0f} đ — {ghi_chu or 'Không có ghi chú thêm'}")

    # Hiển thị ảnh chụp đồng hồ công tơ điện của phòng
    st.subheader(f"📸 Ảnh chụp đồng hồ công tơ điện kỳ {thang_ghi}")
    if anh_ct and anh_ct.startswith("data:image"):
        col_img, col_note = st.columns([1.2, 1])
        with col_img:
            st.image(anh_ct, caption=f"{my_room_name} | Seri: {seri_ct} | Chỉ số chốt: {row['Điện mới']} kWh", use_container_width=True)
        with col_note:
            st.success(f"""
            **Thông tin đối chiếu chỉ số điện:**
            - **Phòng:** {my_room_name} ({row['Khách thuê']})
            - **Số seri công tơ:** `{seri_ct or 'Chưa cập nhật'}`
            - **Chỉ số đầu kỳ (cũ):** `{row['Điện cũ']}`
            - **Chỉ số cuối kỳ (mới):** `{row['Điện mới']}`
            - **Sản lượng tiêu thụ:** **{so_kwh} kWh** × `{gia_dien:,.0f} đ` = **{tien_dien:,.0f} đ**
            """)
    else:
        st.info("📷 Chủ trọ chưa tải ảnh chụp công tơ điện kỳ này lên hệ thống.")

    st.divider()
    st.subheader("💬 Gửi phản hồi / Báo sự cố tới Chủ trọ")
    st.caption("Nếu phòng có vấn đề về điện, nước, thiết bị hoặc thắc mắc hóa đơn, anh/chị nhập nội dung bên dưới — hệ thống sẽ gửi thông báo ngay tới Email của chủ trọ.")
    with st.form(key=f"feedback_form_{my_room_name}", clear_on_submit=True):
        fb_content = st.text_area(
            "Nội dung phản hồi / yêu cầu hỗ trợ:",
            placeholder="Ví dụ: Vòi nước nhà vệ sinh bị rỉ, bóng đèn hành lang cháy, hoặc thắc mắc chỉ số điện kỳ này...",
            height=110
        )
        submitted_fb = st.form_submit_button("📩 Gửi phản hồi ngay cho Chủ trọ", type="primary", use_container_width=True)
        if submitted_fb:
            if not fb_content.strip():
                st.warning("Vui lòng nhập nội dung phản hồi trước khi bấm gửi!")
            else:
                with st.spinner("Đang gửi phản hồi tới chủ trọ..."):
                    ok_fb, msg_fb = send_feedback_to_admin(my_room_name, row["Khách thuê"], fb_content.strip())
                if ok_fb:
                    st.success(f"✅ {msg_fb}")
                    st.toast("Đã gửi phản hồi tới chủ trọ!", icon="📩")

    # Hiển thị lịch sử phản hồi & câu trả lời của chủ trọ cho riêng phòng này
    all_fb_cus = load_feedback()
    if not all_fb_cus.empty:
        my_fb = all_fb_cus[all_fb_cus["Phòng"] == my_room_name]
        if not my_fb.empty:
            has_admin_reply = (my_fb["Phản hồi của chủ trọ"].astype(str).str.strip() != "").any()
            with st.expander(f"📋 Lịch sử phản hồi & Trả lời từ Chủ trọ ({len(my_fb)})", expanded=has_admin_reply):
                st.dataframe(
                    my_fb[["Thời gian", "Nội dung phản hồi", "Trạng thái", "Phản hồi của chủ trọ"]],
                    use_container_width=True,
                    hide_index=True
                )

    st.divider()
    st.subheader(f"🗂️ Lịch sử đóng tiền & tiêu thụ điện của riêng {my_room_name}")
    hist_df = load_history()
    if not hist_df.empty and "Phòng" in hist_df.columns:
        my_hist = hist_df[hist_df["Phòng"] == my_room_name].copy()
        if not my_hist.empty:
            cols_show = [c for c in ["Kỳ thu", "Ngày chốt", "Seri công tơ", "Điện cũ", "Điện mới", "Số kWh", "Tiền điện", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác", "Ghi chú", "Tiền phòng", "Tổng cộng", "Đã thu"] if c in my_hist.columns]
            st.dataframe(my_hist[cols_show], use_container_width=True, hide_index=True)

            if "Kỳ thu" in my_hist.columns and "Số kWh" in my_hist.columns:
                st.caption(f"📊 Biểu đồ số điện tiêu thụ (kWh) qua các tháng của {my_room_name}:")
                chart_my_kwh = my_hist.iloc[::-1].set_index("Kỳ thu")[["Số kWh"]]
                st.bar_chart(chart_my_kwh, color="#f59e0b")
        else:
            st.info(f"Chưa có lịch sử kỳ trước nào được chốt cho {my_room_name}.")
    else:
        st.info("Chưa có dữ liệu lịch sử các tháng trước.")

# ==========================================
# CÁC HỘP THOẠI DÀNH CHO ADMIN
# ==========================================
def get_changes_summary(orig_df, new_df):
    changes = []
    min_len = min(len(orig_df), len(new_df))
    for i in range(min_len):
        row_diffs = []
        phong_name = new_df.iloc[i]["Phòng"] if pd.notna(new_df.iloc[i]["Phòng"]) else f"Dòng {i+1}"
        for col in orig_df.columns:
            if col == "Ảnh công tơ":
                continue
            v1 = orig_df.iloc[i][col]
            v2 = new_df.iloc[i][col]
            if pd.isna(v1) and pd.isna(v2):
                continue
            if str(v1) != str(v2):
                row_diffs.append(f"**{col}**: `{v1}` ➔ `{v2}`")
        if row_diffs:
            changes.append(f"✏️ **{phong_name}** — " + ", ".join(row_diffs))
    return changes

@st.dialog("⚠️ Xác nhận thay đổi")
def confirm_instant_change_dialog(edited_df, changes_list):
    st.write("Bạn có muốn lưu thay đổi vừa nhập không?")
    for item in changes_list:
        st.info(item)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Đồng ý & Lưu luôn", type="primary", use_container_width=True):
            write_table(edited_df, "rooms", ROOMS_FILE)
            st.session_state.editor_key += 1
            st.toast("Đã lưu thay đổi!", icon="✅")
            st.rerun()
    with c2:
        if st.button("❌ Hủy (Hoàn tác)", use_container_width=True):
            st.session_state.editor_key += 1
            st.toast("Đã hủy thay đổi!", icon="↩️")
            st.rerun()

@st.dialog("⚠️ Xác nhận thêm phòng mới")
def confirm_add_room_dialog(new_room_data):
    st.write("Bạn có chắc chắn muốn **thêm phòng mới** này vào danh sách không?")
    info_text = f"""**Phòng:** {new_room_data['Phòng']} | **Khách thuê:** {new_room_data['Khách thuê'] or 'Chưa có'} | **Email:** `{new_room_data['Email khách'] or 'Chưa nhập'}`

**Seri công tơ:** `{new_room_data['Seri công tơ'] or 'Chưa nhập'}` | **Mật khẩu phòng:** `{new_room_data['Mật khẩu phòng']}` | **Tiền phòng:** {new_room_data['Tiền phòng']:,.0f} đ

**Điện đầu:** {new_room_data['Điện cũ']} | **Dịch vụ:** Nước {new_room_data['Tiền nước']:,.0f}đ • Rác {new_room_data['Tiền rác']:,.0f}đ • An ninh {new_room_data['An ninh']:,.0f}đ • Khác {new_room_data['Tiền khác']:,.0f}đ"""
    st.info(info_text)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Đồng ý thêm", type="primary", use_container_width=True):
            df_curr = load_rooms()
            new_row = pd.DataFrame([new_room_data])
            write_table(pd.concat([df_curr, new_row], ignore_index=True), "rooms", ROOMS_FILE)
            st.session_state.editor_key += 1
            st.toast("Đã thêm phòng mới thành công!", icon="✅")
            st.rerun()
    with c2:
        if st.button("❌ Hủy bỏ", use_container_width=True):
            st.rerun()

@st.dialog("🗑️ Xác nhận xóa phòng / khách thuê")
def confirm_delete_room_dialog(room_idx, room_info):
    st.error(f"Bạn có chắc chắn muốn xóa **{room_info['Phòng']}** (Khách thuê: **{room_info['Khách thuê']}**) không?")
    st.write("Hành động này sẽ xóa phòng khỏi danh sách hiện tại (không ảnh hưởng đến lịch sử các tháng đã chốt trước đó).")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Đồng ý xóa", type="primary", use_container_width=True):
            df_curr = load_rooms()
            df_curr = df_curr.drop(index=room_idx).reset_index(drop=True)
            write_table(df_curr, "rooms", ROOMS_FILE)
            st.session_state.editor_key += 1
            st.toast(f"Đã xóa {room_info['Phòng']}!", icon="🗑️")
            st.rerun()
    with c2:
        if st.button("❌ Giữ lại", use_container_width=True):
            st.rerun()

@st.dialog("📧 Xác nhận gửi Email hóa đơn hàng loạt")
def confirm_batch_email_dialog(calc_df, thang_ghi, gia_dien):
    valid_rooms = calc_df[calc_df["Email khách"].astype(str).str.contains("@", na=False)]
    if valid_rooms.empty:
        st.warning("Chưa có phòng nào được nhập địa chỉ Email hợp lệ (có ký tự @). Hãy điền Email khách vào bảng trước!")
        if st.button("Đóng", use_container_width=True):
            st.rerun()
        return

    st.write(f"Hệ thống sẽ tự động gửi hóa đơn **kỳ {thang_ghi}** (kèm ảnh đồng hồ điện nếu có) tới **{len(valid_rooms)} phòng** sau:")
    for _, r in valid_rooms.iterrows():
        has_img = " 📸 (kèm ảnh đồng hồ)" if str(r.get("Ảnh công tơ", "")).strip() else ""
        st.info(f"🏠 **{r['Phòng']}** ({r['Khách thuê']}) ➔ `{r['Email khách']}` — Tổng: **{int(r['Tổng cộng']):,.0f} đ**{has_img}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 Gửi Email ngay", type="primary", use_container_width=True):
            ok_list, fail_list = [], []
            progress = st.progress(0)
            total = len(valid_rooms)
            for idx_step, (_, r) in enumerate(valid_rooms.iterrows(), start=1):
                subj = f"[Xóm Trọ Minh Quân] Thông báo tiền phòng kỳ {thang_ghi} - {r['Phòng']}"
                body = build_invoice_message(r, thang_ghi, gia_dien)
                success, err = send_invoice_email(r["Email khách"], subj, body, str(r.get("Ảnh công tơ", "")))
                if success:
                    ok_list.append(f"{r['Phòng']} ({r['Email khách']})")
                else:
                    fail_list.append(f"{r['Phòng']}: {err}")
                progress.progress(idx_step / total)

            if ok_list:
                st.success(f"✅ Đã gửi thành công {len(ok_list)} email:\n- " + "\n- ".join(ok_list))
            if fail_list:
                st.error("❌ Các phòng gửi lỗi:\n- " + "\n- ".join(fail_list))
    with c2:
        if st.button("❌ Hủy", use_container_width=True):
            st.rerun()

@st.dialog("🔒 Xác nhận chốt sổ & chuyển sang kỳ kế tiếp")
def confirm_close_month_dialog(df_rooms, calc_df, thang_ghi, gia_dien):
    next_thang = advance_month_str(thang_ghi)
    st.write(f"Bạn có chắc chắn muốn **CHỐT SỔ KỲ {thang_ghi}** và chuyển sang kỳ mới **{next_thang}** không?")
    close_info = f"""Sau khi xác nhận:
1. Toàn bộ số liệu kỳ **{thang_ghi}** sẽ được lưu vào **Lịch sử các tháng trước**.
2. Chỉ số **Điện mới** của kỳ **{thang_ghi}** sẽ **tự động nhảy sang cột Điện cũ** cho kỳ kế tiếp (**{next_thang}**).
3. **Kỳ thu tiền** tự động chuyển từ `{thang_ghi}` ➔ **`{next_thang}`**.
4. **Tiền khác**, **Ghi chú**, **Ảnh công tơ** và trạng thái **Đã thu** được làm mới cho kỳ **{next_thang}**."""
    st.info(close_info)

    valid_emails = calc_df[calc_df["Email khách"].astype(str).str.contains("@", na=False)]
    auto_send_mail = False
    if not valid_emails.empty:
        auto_send_mail = st.checkbox(f"📧 Đồng thời tự động gửi hóa đơn kỳ {thang_ghi} qua Email cho {len(valid_emails)} phòng đã có email", value=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Chốt sổ & Sang tháng mới", type="primary", use_container_width=True):
            if auto_send_mail and not valid_emails.empty:
                for _, r in valid_emails.iterrows():
                    subj = f"[Xóm Trọ Minh Quân] Thông báo tiền phòng kỳ {thang_ghi} - {r['Phòng']}"
                    body = build_invoice_message(r, thang_ghi, gia_dien)
                    send_invoice_email(r["Email khách"], subj, body, str(r.get("Ảnh công tơ", "")))

            record_df = calc_df.copy()
            for drop_col in ["Mật khẩu phòng", "Ảnh công tơ"]:
                if drop_col in record_df.columns:
                    record_df = record_df.drop(columns=[drop_col])
            record_df.insert(0, "Kỳ thu", thang_ghi)
            record_df.insert(1, "Ngày chốt", datetime.now().strftime("%d/%m/%Y %H:%M"))
            record_df["Đơn giá điện"] = gia_dien

            old_hist = load_history()
            if not old_hist.empty:
                save_history(pd.concat([record_df, old_hist], ignore_index=True))
            else:
                save_history(record_df)

            # Tự động chuyển Điện mới thành Điện cũ cho kỳ kế tiếp
            next_df = df_rooms.copy()
            next_df["Điện cũ"] = next_df["Điện mới"]
            next_df["Tiền khác"] = 0
            next_df["Ghi chú"] = ""
            next_df["Đã thu"] = False
            next_df["Ảnh công tơ"] = ""
            write_table(next_df, "rooms", ROOMS_FILE)

            # Tự động nhảy kỳ thu tiền sang tháng kế tiếp
            if next_thang != thang_ghi:
                save_config(gia_dien, next_thang)

            st.session_state.editor_key += 1
            st.toast(f"Đã chốt sổ {thang_ghi} và chuyển sang kỳ {next_thang}!", icon="🎉")
            st.rerun()
    with c2:
        if st.button("❌ Quay lại kiểm tra", use_container_width=True):
            st.rerun()

# ==========================================
# GIAO DIỆN QUẢN TRỊ CHỦ TRỌ (ADMIN)
# ==========================================
def render_admin_view(df, gia_dien_saved, thang_ghi_saved):
    df_fb_admin = load_feedback()
    new_fb_count = int((df_fb_admin["Trạng thái"] == "Mới gửi").sum()) if not df_fb_admin.empty else 0

    if new_fb_count > 0:
        latest_rooms = ", ".join(df_fb_admin[df_fb_admin["Trạng thái"] == "Mới gửi"]["Phòng"].astype(str).unique().tolist())
        st.markdown(f"""
        <div class="floating-bell-alert" title="Có phản hồi mới từ khách thuê">
            <span class="floating-bell-icon">🔔</span>
            <span>Phản hồi mới ({latest_rooms})</span>
            <span class="floating-bell-badge">{new_fb_count}</span>
        </div>
        """, unsafe_allow_html=True)

    storage_mode = "☁️ Google Sheets (Cloud)" if get_gsheet_client() is not None else "💻 File CSV trên máy tính"
    sender_mail, _ = get_email_credentials()
    mail_status = f"📧 Gmail tự động: **{sender_mail}**" if sender_mail else "⚠️ Chưa cấu hình Gmail tự động"

    st.markdown(f"""
    <div class="hero-banner">
        <h1>🏠 Xóm Trọ Minh Quân — Bảng Điều Khiển Chủ Trọ</h1>
        <p style="font-weight: 700; color: #ffffff !important; font-size: 15px; margin-top: 4px;">📍 Thôn Mẫn Xá - Xã Yên Phong - Tỉnh Bắc Ninh</p>
        <p>📅 Kỳ thu hiện tại: <strong>{thang_ghi_saved}</strong> &nbsp;|&nbsp; ⚡ Đơn giá điện: <strong>{gia_dien_saved:,.0f} đ/kWh</strong> &nbsp;|&nbsp; 🏘️ Quy mô: <strong>{len(df)} phòng</strong></p>
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.success(f"🔑 Quyền: **Chủ trọ (Admin)**\n\nLưu trữ: {storage_mode}\n\n{mail_status}")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state.role = None
            st.rerun()

        st.divider()
        st.header("⚙️ Cấu hình chung")
        gia_dien = st.number_input("Đơn giá điện (VNĐ/kWh)", min_value=0, value=gia_dien_saved, step=100)
        thang_ghi = st.text_input("Kỳ thu tiền", value=thang_ghi_saved)
        if gia_dien != gia_dien_saved or thang_ghi != thang_ghi_saved:
            if st.button("💾 Lưu cấu hình kỳ & giá điện", type="primary", use_container_width=True):
                save_config(gia_dien, thang_ghi)
                st.toast("Đã lưu cấu hình chung!", icon="⚙️")
                st.rerun()

        st.divider()
        st.subheader("➕ Thêm phòng mới")
        ten_phong = st.text_input("Tên phòng (VD: Phòng P111)")
        khach_thue = st.text_input("Tên khách thuê")
        email_khach_moi = st.text_input("Email khách thuê (VD: khach@gmail.com)")
        seri_cong_to_moi = st.text_input("Số seri công tơ điện (VD: 16060399)")
        mk_phong_moi = st.text_input("Mật khẩu xem phòng (cho khách)", value="123456")
        gia_phong_moi = st.number_input("Giá thuê phòng (VNĐ)", min_value=0, value=1000000, step=100000)
        so_dien_dau = st.number_input("Chỉ số điện ban đầu", min_value=0, value=0)

        c_s1, c_s2, c_s3 = st.columns(3)
        with c_s1:
            gia_nuoc_moi = st.number_input("Nước", min_value=0, value=0, step=10000)
        with c_s2:
            gia_rac_moi = st.number_input("Rác", min_value=0, value=0, step=5000)
        with c_s3:
            gia_an_ninh_moi = st.number_input("An ninh", min_value=0, value=0, step=5000)

        gia_khac_moi = st.number_input("Tiền khác (VNĐ)", value=0, step=10000)
        ghi_chu_moi = st.text_input("Ghi chú khoản tiền khác")

        if st.button("Thêm phòng", use_container_width=True):
            if not ten_phong.strip():
                st.warning("Vui lòng nhập Tên phòng trước khi bấm Thêm!")
            else:
                confirm_add_room_dialog({
                    "Phòng": ten_phong.strip(),
                    "Khách thuê": khach_thue.strip(),
                    "Email khách": email_khach_moi.strip(),
                    "Mật khẩu phòng": mk_phong_moi.strip() or "123456",
                    "Seri công tơ": seri_cong_to_moi.strip(),
                    "Tiền phòng": gia_phong_moi,
                    "Điện cũ": so_dien_dau,
                    "Điện mới": so_dien_dau,
                    "Tiền nước": gia_nuoc_moi,
                    "Tiền rác": gia_rac_moi,
                    "An ninh": gia_an_ninh_moi,
                    "Tiền khác": gia_khac_moi,
                    "Ghi chú": ghi_chu_moi.strip(),
                    "Đã thu": False,
                    "Ảnh công tơ": "",
                })

        st.divider()
        st.subheader("🗑️ Xóa phòng khỏi danh sách")
        if not df.empty:
            room_options = {f"{row['Phòng']} ({row['Khách thuê']})": idx for idx, row in df.iterrows()}
            selected_del_label = st.selectbox("Chọn phòng cần xóa:", list(room_options.keys()))
            if st.button("Xóa phòng đã chọn", use_container_width=True):
                del_idx = room_options[selected_del_label]
                confirm_delete_room_dialog(del_idx, df.iloc[del_idx])

    fb_tab_label = f"💬 Phản hồi khách ({new_fb_count} mới)" if new_fb_count > 0 else "💬 Phản hồi khách"

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Nhập số điện & Thu tiền",
        "📸 Ảnh đồng hồ từng phòng",
        "📊 Biểu đồ & Gửi Zalo / Email",
        "🗂️ Lịch sử các tháng trước",
        fb_tab_label
    ])

    with tab1:
        st.info("💡 Chỉnh sửa bất kỳ ô nào trên bảng dưới đây — phần mềm sẽ **hỏi xác nhận và tự động lưu ngay lập tức**. Khi bấm **Chốt sổ**, cột **Điện mới** sẽ tự động nhảy sang **Điện cũ** của tháng tiếp theo.")
        display_edit_cols = [c for c in df.columns if c != "Ảnh công tơ"]
        edited_sub_df = st.data_editor(
            df[display_edit_cols],
            key=f"room_editor_{st.session_state.editor_key}",
            num_rows="fixed",
            use_container_width=True,
            column_config={
                "Email khách": st.column_config.TextColumn(help="Địa chỉ Gmail của khách để hệ thống tự động gửi hóa đơn hàng tháng"),
                "Mật khẩu phòng": st.column_config.TextColumn(help="Mật khẩu riêng để khách phòng này đăng nhập xem hóa đơn"),
                "Seri công tơ": st.column_config.TextColumn(help="Số seri in trên mặt công tơ điện"),
                "Tiền phòng": st.column_config.NumberColumn(format="%d đ"),
                "Điện cũ": st.column_config.NumberColumn(min_value=0, step=1),
                "Điện mới": st.column_config.NumberColumn(min_value=0, step=1),
                "Tiền nước": st.column_config.NumberColumn(format="%d đ", min_value=0, step=10000),
                "Tiền rác": st.column_config.NumberColumn(format="%d đ", min_value=0, step=5000),
                "An ninh": st.column_config.NumberColumn(format="%d đ", min_value=0, step=5000),
                "Tiền khác": st.column_config.NumberColumn(format="%d đ", step=10000),
                "Ghi chú": st.column_config.TextColumn(width="medium"),
            }
        )

        edited_full_df = edited_sub_df.copy()
        edited_full_df["Ảnh công tơ"] = df["Ảnh công tơ"].values

        pending_changes = get_changes_summary(df, edited_full_df)
        if pending_changes:
            confirm_instant_change_dialog(edited_full_df, pending_changes)

        calc_df = df.copy()
        calc_df["Số kWh"] = calc_df["Điện mới"] - calc_df["Điện cũ"]
        calc_df["Tiền điện"] = calc_df["Số kWh"].apply(lambda x: x * gia_dien if x >= 0 else 0)
        calc_df["Dịch vụ (Nước+Rác+AN)"] = calc_df["Tiền nước"] + calc_df["Tiền rác"] + calc_df["An ninh"]
        calc_df["Tổng cộng"] = calc_df["Tiền phòng"] + calc_df["Tiền điện"] + calc_df["Dịch vụ (Nước+Rác+AN)"] + calc_df["Tiền khác"]

        if (calc_df["Số kWh"] < 0).any():
            st.error("⚠️ Cảnh báo: Có phòng đang có Số điện mới nhỏ hơn Số điện cũ! Vui lòng kiểm tra lại.")

        tong_dien = calc_df["Tiền điện"].sum()
        tong_kwh = calc_df["Số kWh"].clip(lower=0).sum()
        tong_dich_vu_va_khac = calc_df["Dịch vụ (Nước+Rác+AN)"].sum() + calc_df["Tiền khác"].sum()
        tong_khac = calc_df["Tiền khác"].sum()
        tong_phong = calc_df["Tiền phòng"].sum()
        tong_thu = calc_df["Tổng cộng"].sum()
        so_phong_da_thu = calc_df["Đã thu"].sum()
        tong_so_phong = len(calc_df)

        st.markdown("### 📈 Tổng quan kỳ thu " + thang_ghi)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="metric-card electric">
                <div class="metric-title">⚡ Tổng tiền điện</div>
                <div class="metric-value">{tong_dien:,.0f} đ</div>
                <div class="metric-sub">{tong_kwh:,.0f} kWh (Giá {gia_dien:,.0f} đ)</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            sub_dv = f"Dịch vụ + Tiền khác ({tong_khac:,.0f} đ)" if tong_khac != 0 else "Tổng phí dịch vụ các phòng"
            st.markdown(f"""
            <div class="metric-card service">
                <div class="metric-title">💧 Dịch vụ & Tiền khác</div>
                <div class="metric-value">{tong_dich_vu_va_khac:,.0f} đ</div>
                <div class="metric-sub">{sub_dv}</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card room">
                <div class="metric-title">🏢 Tổng tiền phòng</div>
                <div class="metric-value">{tong_phong:,.0f} đ</div>
                <div class="metric-sub">{tong_so_phong} phòng đang quản lý</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="metric-card total">
                <div class="metric-title">💰 Tổng doanh thu</div>
                <div class="metric-value">{tong_thu:,.0f} đ</div>
                <div class="metric-sub">Đã thu: {so_phong_da_thu}/{tong_so_phong} phòng</div>
            </div>
            """, unsafe_allow_html=True)

        st.subheader("📑 Bảng kê chi tiết cần thu")
        def highlight_status(row):
            if row["Đã thu"]:
                return ["background-color: #dcfce7; color: #166534"] * len(row)
            elif row["Số kWh"] < 0:
                return ["background-color: #fee2e2; color: #991b1b"] * len(row)
            return [""] * len(row)

        display_cols = ["Phòng", "Khách thuê", "Seri công tơ", "Điện cũ", "Điện mới", "Số kWh", "Tiền điện", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác", "Ghi chú", "Tiền phòng", "Tổng cộng", "Đã thu"]
        styled_df = calc_df[display_cols].style.apply(highlight_status, axis=1).format({
            "Điện cũ": "{:,.0f}",
            "Điện mới": "{:,.0f}",
            "Số kWh": "{:,.0f}",
            "Tiền điện": "{:,.0f} đ",
            "Tiền nước": "{:,.0f} đ",
            "Tiền rác": "{:,.0f} đ",
            "An ninh": "{:,.0f} đ",
            "Tiền khác": "{:,.0f} đ",
            "Tiền phòng": "{:,.0f} đ",
            "Tổng cộng": "{:,.0f} đ"
        })
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("📧 Gửi hóa đơn Email cho tất cả phòng", use_container_width=True):
                if (calc_df["Số kWh"] < 0).any():
                    st.error("Không thể gửi hóa đơn vì đang có phòng bị âm số điện!")
                else:
                    confirm_batch_email_dialog(calc_df, thang_ghi, gia_dien)
        with col_btn2:
            if st.button(f"✅ Chốt sổ kỳ {thang_ghi} & Chuyển sang {advance_month_str(thang_ghi)}", type="primary", use_container_width=True):
                if (calc_df["Số kWh"] < 0).any():
                    st.error("Không thể chốt sổ vì đang có phòng bị âm số điện!")
                else:
                    confirm_close_month_dialog(df, calc_df, thang_ghi, gia_dien)

    # ==========================================
    # TAB 2: TẢI & XEM ẢNH ĐỒNG HỒ ĐIỆN TỪNG PHÒNG
    # ==========================================
    with tab2:
        st.subheader(f"📸 Bảng ảnh chụp đồng hồ công tơ điện — Kỳ {thang_ghi}")
        st.info("Tải ảnh chụp mặt đồng hồ điện của từng phòng lên đây. Khách thuê khi đăng nhập bằng mật khẩu phòng của mình sẽ nhìn thấy trực tiếp bức ảnh này để đối chiếu minh bạch.")

        if df.empty:
            st.warning("Chưa có phòng nào trong danh sách.")
        else:
            # Hiển thị dạng lưới 2 cột cho trực quan
            for idx_start in range(0, len(df), 2):
                cols_grid = st.columns(2)
                for offset in range(2):
                    idx_r = idx_start + offset
                    if idx_r >= len(df):
                        break
                    row_r = df.iloc[idx_r]
                    phong_r = row_r["Phòng"]
                    khach_r = row_r["Khách thuê"]
                    seri_r = str(row_r["Seri công tơ"]).strip()
                    anh_r = str(row_r.get("Ảnh công tơ", "")).strip()

                    with cols_grid[offset]:
                        st.markdown(f"""
                        <div class="meter-card">
                            <span class="meter-badge">🏠 {phong_r} — {khach_r}</span><br/>
                            <span style="font-size:13px; color:#334155;">🔌 Seri: <strong>{seri_r or 'Chưa có'}</strong> &nbsp;|&nbsp; ⚡ Cũ: <strong>{row_r['Điện cũ']}</strong> ➔ Mới: <strong>{row_r['Điện mới']}</strong></span>
                        </div>
                        """, unsafe_allow_html=True)

                        if anh_r and anh_r.startswith("data:image"):
                            st.image(anh_r, caption=f"Ảnh đồng hồ {phong_r} (Chỉ số: {row_r['Điện mới']})", use_container_width=True)
                            if st.button(f"🗑️ Xóa ảnh của {phong_r}", key=f"del_img_{idx_r}"):
                                df_upd = df.copy()
                                df_upd.at[idx_r, "Ảnh công tơ"] = ""
                                write_table(df_upd, "rooms", ROOMS_FILE)
                                st.toast(f"Đã xóa ảnh đồng hồ {phong_r}!", icon="🗑️")
                                st.rerun()
                        else:
                            st.caption("📷 Chưa có ảnh đồng hồ cho kỳ này.")

                        up_file = st.file_uploader(
                            f"Tải ảnh đồng hồ {phong_r}",
                            type=["jpg", "jpeg", "png", "webp"],
                            key=f"up_meter_{idx_r}",
                            label_visibility="collapsed"
                        )
                        if up_file is not None:
                            if st.button(f"💾 Lưu ảnh đồng hồ cho {phong_r}", key=f"save_img_{idx_r}", type="primary", use_container_width=True):
                                b64_img = compress_image_to_base64(up_file)
                                if b64_img:
                                    df_upd = df.copy()
                                    df_upd.at[idx_r, "Ảnh công tơ"] = b64_img
                                    write_table(df_upd, "rooms", ROOMS_FILE)
                                    st.toast(f"Đã lưu ảnh đồng hồ {phong_r}!", icon="📸")
                                    st.rerun()

    with tab3:
        col_chart, col_zalo = st.columns([1.2, 1])
        with col_chart:
            st.subheader("📊 Biểu đồ chi phí & doanh thu theo phòng")
            if not calc_df.empty:
                chart_df = calc_df.copy()
                chart_df["Dịch vụ & Khác"] = chart_df["Dịch vụ (Nước+Rác+AN)"] + chart_df["Tiền khác"]
                chart_data = chart_df.set_index("Phòng")[["Tiền phòng", "Tiền điện", "Dịch vụ & Khác"]]
                st.bar_chart(chart_data, color=["#6366f1", "#f59e0b", "#06b6d4"])
                st.caption("Biểu đồ số điện tiêu thụ (kWh) từng phòng:")
                kwh_chart = calc_df.set_index("Phòng")[["Số kWh"]]
                st.bar_chart(kwh_chart, color="#10b981")

        with col_zalo:
            st.subheader("💬 Gửi hóa đơn qua Zalo hoặc Email")
            if not calc_df.empty:
                ds_phong = calc_df["Phòng"].tolist()
                phong_chon = st.selectbox("Chọn phòng cần gửi hóa đơn:", ds_phong)
                row_p = calc_df[calc_df["Phòng"] == phong_chon].iloc[0]
                msg = build_invoice_message(row_p, thang_ghi, gia_dien)

                email_hien_tai = str(row_p.get("Email khách", "")).strip()
                if email_hien_tai:
                    if st.button(f"📧 Gửi ngay qua Email tới {email_hien_tai}", type="primary", use_container_width=True):
                        subj = f"[Xóm Trọ Minh Quân] Thông báo tiền phòng kỳ {thang_ghi} - {row_p['Phòng']}"
                        ok, err = send_invoice_email(email_hien_tai, subj, msg, str(row_p.get("Ảnh công tơ", "")))
                        if ok:
                            st.success(f"✅ Đã gửi hóa đơn cho {row_p['Phòng']} thành công!")
                        else:
                            st.error(f"❌ Lỗi gửi email: {err}")
                else:
                    st.caption("ℹ️ Phòng này chưa nhập Email khách (bạn có thể điền ở bảng Tab 1 để gửi tự động).")

                if str(row_p.get("Ảnh công tơ", "")).strip():
                    st.image(str(row_p["Ảnh công tơ"]), caption=f"Ảnh đồng hồ đính kèm của {phong_chon}", width=260)

                st.info("Hoặc bấm biểu tượng Copy ở góc phải khung dưới để dán gửi Zalo:")
                st.code(msg, language="text")

    with tab4:
        hist_df = load_history()
        if not hist_df.empty:
            st.subheader("📈 Biểu đồ doanh thu qua các kỳ đã chốt")
            cols_to_plot = [c for c in ["Tiền phòng", "Tiền điện", "Dịch vụ (Nước+Rác+AN)", "Tiền khác"] if c in hist_df.columns]
            if cols_to_plot and "Kỳ thu" in hist_df.columns:
                rev_by_month = hist_df.groupby("Kỳ thu", sort=False)[cols_to_plot].sum().iloc[::-1]
                st.bar_chart(rev_by_month)

            st.divider()
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                ky_list = ["Tất cả"] + list(hist_df["Kỳ thu"].unique()) if "Kỳ thu" in hist_df.columns else ["Tất cả"]
                chon_ky = st.selectbox("Lọc theo kỳ thu tiền:", ky_list)
            with col_f2:
                phong_list = ["Tất cả"] + list(hist_df["Phòng"].unique()) if "Phòng" in hist_df.columns else ["Tất cả"]
                chon_phong = st.selectbox("Lọc theo phòng:", phong_list)

            view_df = hist_df.copy()
            if chon_ky != "Tất cả":
                view_df = view_df[view_df["Kỳ thu"] == chon_ky]
            if chon_phong != "Tất cả":
                view_df = view_df[view_df["Phòng"] == chon_phong]

            st.dataframe(view_df, use_container_width=True, hide_index=True)

            csv_data = view_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 Tải bảng lịch sử về mở bằng Excel (.csv)",
                data=csv_data,
                file_name=f"lich_su_xom_tro_minh_quan_{chon_ky.replace('/', '-')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Chưa có dữ liệu lịch sử nào được chốt sổ.")

    with tab5:
        st.subheader("💬 Danh sách phản hồi & Trả lời khách thuê")
        df_fb_view = load_feedback()
        if df_fb_view.empty:
            st.info("Chưa có phản hồi nào từ các phòng.")
        else:
            if new_fb_count > 0:
                st.warning(f"🔔 Bạn có **{new_fb_count} phản hồi mới** chưa xử lý!")

            st.caption("💡 Bạn có thể sửa trực tiếp **Trạng thái** hoặc gõ nội dung vào cột **Phản hồi của chủ trọ** ngay trong bảng dưới đây (khách sẽ thấy ngay khi đăng nhập):")
            edited_fb = st.data_editor(
                df_fb_view,
                key="fb_editor",
                num_rows="fixed",
                use_container_width=True,
                column_config={
                    "Thời gian": st.column_config.TextColumn(disabled=True),
                    "Phòng": st.column_config.TextColumn(disabled=True),
                    "Khách thuê": st.column_config.TextColumn(disabled=True),
                    "Nội dung phản hồi": st.column_config.TextColumn(width="medium", disabled=True),
                    "Trạng thái": st.column_config.SelectboxColumn(
                        options=["Mới gửi", "Đang xử lý", "Đã xử lý xong"],
                        required=True
                    ),
                    "Phản hồi của chủ trọ": st.column_config.TextColumn(
                        width="large",
                        help="Nhập câu trả lời của bạn để khách thuê xem được trên web"
                    )
                }
            )
            if not edited_fb.equals(df_fb_view):
                save_feedback(edited_fb)
                st.toast("Đã lưu phản hồi của chủ trọ!", icon="✅")
                st.rerun()

            st.divider()
            st.subheader("📩 Trả lời nhanh & Gửi Email thông báo tình hình cho khách")
            fb_options = {
                f"[{r['Thời gian']}] {r['Phòng']} ({r['Khách thuê']}) — {str(r['Nội dung phản hồi'])[:45]}...": idx
                for idx, r in df_fb_view.iterrows()
            }
            selected_fb_label = st.selectbox("Chọn phản hồi cần trả lời & gửi email:", list(fb_options.keys()))
            sel_idx = fb_options[selected_fb_label]
            sel_fb_row = df_fb_view.iloc[sel_idx]

            # Lấy email của phòng tương ứng từ bảng df
            matched_room_info = df[df["Phòng"] == sel_fb_row["Phòng"]]
            cust_email_found = ""
            if not matched_room_info.empty:
                cust_email_found = str(matched_room_info.iloc[0].get("Email khách", "")).strip()

            st.info(f"**Nội dung khách gửi ({sel_fb_row['Phòng']}):** {sel_fb_row['Nội dung phản hồi']}")
            if cust_email_found:
                st.caption(f"📧 Email khách thuê đã lưu: **`{cust_email_found}`**")
            else:
                st.warning(f"⚠️ **{sel_fb_row['Phòng']}** chưa có địa chỉ Email trong bảng Tab 1 — bạn vẫn có thể lưu phản hồi lên web cho khách xem, hoặc nhập tạm email bên dưới để gửi.")

            with st.form(key=f"admin_reply_form_{sel_idx}"):
                col_st, col_em = st.columns([1, 1.5])
                with col_st:
                    status_opts = ["Mới gửi", "Đang xử lý", "Đã xử lý xong"]
                    curr_st_idx = status_opts.index(sel_fb_row["Trạng thái"]) if sel_fb_row["Trạng thái"] in status_opts else 1
                    new_status_val = st.selectbox("Cập nhật trạng thái:", status_opts, index=curr_st_idx)
                with col_em:
                    target_email_val = st.text_input("Email nhận thông báo:", value=cust_email_found, placeholder="Nhập email khách nếu chưa có...")

                reply_text_val = st.text_area(
                    "Nội dung phản hồi gửi khách thuê:",
                    value=str(sel_fb_row.get("Phản hồi của chủ trọ", "")),
                    placeholder="Ví dụ: Anh đã gọi thợ qua sửa bóng đèn cầu thang vào 17h chiều nay rồi nhé!",
                    height=100
                )
                send_mail_chk = st.checkbox("📧 Đồng thời gửi Email thông báo tình hình cho khách", value=bool(cust_email_found))

                if st.form_submit_button("💾 Lưu phản hồi & Gửi thông báo", type="primary", use_container_width=True):
                    df_fb_upd = load_feedback()
                    df_fb_upd.at[sel_idx, "Trạng thái"] = new_status_val
                    df_fb_upd.at[sel_idx, "Phản hồi của chủ trọ"] = reply_text_val.strip()
                    save_feedback(df_fb_upd)

                    if send_mail_chk:
                        ok_m, msg_m = send_admin_reply_email(
                            target_email_val,
                            sel_fb_row["Phòng"],
                            sel_fb_row["Khách thuê"],
                            sel_fb_row["Nội dung phản hồi"],
                            new_status_val,
                            reply_text_val.strip()
                        )
                        if ok_m:
                            st.success(f"✅ Đã lưu phản hồi lên web và {msg_m}")
                        else:
                            st.warning(f"✅ Đã lưu phản hồi lên web cho khách xem, nhưng chưa gửi được email: {msg_m}")
                    else:
                        st.success("✅ Đã lưu nội dung phản hồi lên web — khách đăng nhập sẽ thấy ngay!")
                    st.rerun()

df_rooms_all = load_rooms()
gia_dien_cfg, thang_ghi_cfg = load_config()

if st.session_state.role is None:
    render_login_screen(df_rooms_all)
elif st.session_state.role == "customer":
    render_customer_view(df_rooms_all, gia_dien_cfg, thang_ghi_cfg)
elif st.session_state.role == "admin":
    render_admin_view(df_rooms_all, gia_dien_cfg, thang_ghi_cfg)