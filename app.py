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

def compress_image_to_base64(uploaded_file, max_width=640, quality=60):
    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if w > max_width:
            new_h = int(h * (max_width / w))
            img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
        for q_try in [quality, 48, 36, 28]:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=q_try, optimize=True)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            if len(b64_str) <= 44000:
                return f"data:image/jpeg;base64,{b64_str}"
        img = img.resize((420, int(img.size[1] * (420 / img.size[0]))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=35, optimize=True)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64_str[:44000]}"
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
            ws.update(data_to_write)
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
        --loft-bg-img: url("data:image/jpeg;base64,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");
    }

    /* Nền ảnh phòng trọ gác lửng hiện đại phủ toàn trang (sau khi đăng nhập) */
    .stApp {
        background-image:
            linear-gradient(135deg, rgba(248, 250, 252, 0.84) 0%, rgba(240, 249, 255, 0.82) 50%, rgba(236, 253, 245, 0.84) 100%),
            var(--loft-bg-img);
        background-size: cover;
        background-position: center;
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
    if df_cfg is None:
        return 3500, "11/2026"
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

    # Nếu kết nối Google Sheets tạm bận (df is None), tuyệt đối KHÔNG ghi đè dữ liệu!
    if df is None:
        st.error("⚠️ Tạm thời chưa tải được dữ liệu từ Google Sheets (vượt giới hạn truy vấn/giây). Vui lòng đợi 5 giây rồi bấm F5 để tải lại — dữ liệu của bạn vẫn an toàn.")
        st.stop()

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
        if existing_hist is not None and existing_hist.empty and not df_hist_seeded.empty:
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
    # Tự động khôi phục ảnh đồng hồ từ sheet dự phòng "meter_photos" nếu cột Ảnh công tơ bị trống
    if (df["Ảnh công tơ"].str.strip() == "").all():
        df_p_bak = read_table("meter_photos", "meter_photos.csv")
        if df_p_bak is not None and not df_p_bak.empty and "Phòng" in df_p_bak.columns and "Ảnh công tơ" in df_p_bak.columns:
            photo_map = dict(zip(df_p_bak["Phòng"].astype(str), df_p_bak["Ảnh công tơ"].astype(str)))
            restored_series = df["Phòng"].map(photo_map).fillna("")
            if (restored_series.str.strip() != "").any():
                df["Ảnh công tơ"] = restored_series
                changed = True
    for num_col in ["Tiền phòng", "Điện cũ", "Điện mới", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác"]:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0).astype(int)
    df["Đã thu"] = df["Đã thu"].apply(lambda x: str(x).strip().lower() in ["true", "1", "yes"])
    if changed:
        write_table(df, "rooms", ROOMS_FILE)
    return df

def load_history():
    df_h = read_table("history", HISTORY_FILE)
    if df_h is None:
        return pd.DataFrame()
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
        /* Nền ảnh phòng trọ gác lửng thực tế nổi bật ở màn hình đăng nhập */
        .stApp {
            background-image:
                linear-gradient(135deg, rgba(15, 23, 42, 0.42) 0%, rgba(30, 58, 138, 0.32) 50%, rgba(6, 78, 59, 0.36) 100%),
                var(--loft-bg-img);
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }

        /* Khung đăng nhập kính mờ (Glassmorphism) nổi bật trên nền phòng trọ */
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
                                backup_meter_photo(phong_r, "")
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
                                    backup_meter_photo(phong_r, b64_img)
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