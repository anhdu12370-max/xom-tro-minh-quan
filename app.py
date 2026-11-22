import streamlit as st
import pandas as pd
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

st.set_page_config(page_title="Xóm Trọ Minh Quân", page_icon="🏠", layout="wide")

ROOMS_FILE = "rooms.csv"
HISTORY_FILE = "history.csv"
CONFIG_FILE = "config.csv"

DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "minhquan2026"
DEFAULT_APP_URL = "https://xom-tro-minh-quan-pxg4pzand8apstxfa7aw66.streamlit.app"

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

def send_invoice_email(to_email, subject, body_text):
    sender_email, app_password = get_email_credentials()
    if not sender_email or not app_password:
        return False, "Chưa cấu hình [email] trong Secrets của Streamlit Cloud."
    try:
        msg = MIMEMultipart()
        msg["From"] = f"Xóm Trọ Minh Quân <{sender_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

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

    return f"""📢 THÔNG BÁO TIỀN PHÒNG XÓM TRỌ MINH QUÂN - KỲ {thang_ghi}
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
💰 TỔNG CỘNG CẦN THANH TOÁN: {int(row_p['Tổng cộng']):,.0f} đ

🌐 Tra cứu hóa đơn & lịch sử online tại: {DEFAULT_APP_URL}
🔑 Mật khẩu phòng của bạn: {row_p['Mật khẩu phòng']}

Anh/chị vui lòng thanh toán sớm giúp Xóm Trọ Minh Quân nhé. Xin cảm ơn!"""

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

st.markdown("""
<style>
    .stApp {
        background-color: #f8fafc;
    }
    .metric-card {
        background: linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%);
        border-radius: 14px;
        padding: 18px;
        border-left: 6px solid #3b82f6;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
        margin-bottom: 10px;
    }
    .metric-card.electric {
        border-left-color: #f59e0b;
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    }
    .metric-card.service {
        border-left-color: #06b6d4;
        background: linear-gradient(135deg, #ecfeff 0%, #cffafe 100%);
    }
    .metric-card.room {
        border-left-color: #3b82f6;
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    }
    .metric-card.total {
        border-left-color: #10b981;
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    }
    .metric-title {
        font-size: 13px;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 23px;
        font-weight: 800;
        color: #0f172a;
    }
    .metric-sub {
        font-size: 12px;
        color: #64748b;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

def load_config():
    df_cfg = read_table("config", CONFIG_FILE)
    if not df_cfg.empty and "gia_dien" in df_cfg.columns and "thang_ghi" in df_cfg.columns:
        return int(float(df_cfg.iloc[0]["gia_dien"])), str(df_cfg.iloc[0]["thang_ghi"])
    default_gia = 3500
    default_thang = datetime.now().strftime("%m/%Y")
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
        "Tiền phòng": 2500000,
        "Điện cũ": 0,
        "Điện mới": 0,
        "Tiền nước": 100000,
        "Tiền rác": 30000,
        "An ninh": 20000,
        "Tiền khác": 0,
        "Ghi chú": "",
        "Đã thu": False
    }
    ordered_cols = [
        "Phòng", "Khách thuê", "Email khách", "Mật khẩu phòng", "Seri công tơ", "Tiền phòng",
        "Điện cũ", "Điện mới", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác", "Ghi chú", "Đã thu"
    ]
    df = read_table("rooms", ROOMS_FILE)
    if not df.empty:
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
        for num_col in ["Tiền phòng", "Điện cũ", "Điện mới", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác"]:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0).astype(int)
        df["Đã thu"] = df["Đã thu"].apply(lambda x: str(x).strip().lower() in ["true", "1", "yes"])
        if changed:
            write_table(df, "rooms", ROOMS_FILE)
        return df

    df = pd.DataFrame([
        {"Phòng": "Phòng 101", "Khách thuê": "Nguyễn Văn A", "Email khách": "", "Mật khẩu phòng": "101123", "Seri công tơ": "CT-101", "Tiền phòng": 2500000, "Điện cũ": 1200, "Điện mới": 1285, "Tiền nước": 100000, "Tiền rác": 30000, "An ninh": 20000, "Tiền khác": 0, "Ghi chú": "", "Đã thu": False},
        {"Phòng": "Phòng 102", "Khách thuê": "Trần Thị B", "Email khách": "", "Mật khẩu phòng": "102123", "Seri công tơ": "CT-102", "Tiền phòng": 2800000, "Điện cũ": 850, "Điện mới": 940, "Tiền nước": 100000, "Tiền rác": 30000, "An ninh": 20000, "Tiền khác": 0, "Ghi chú": "", "Đã thu": False},
    ])
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
# MÀN HÌNH ĐĂNG NHẬP
# ==========================================
def render_login_screen(df_rooms):
    col_left, col_mid, col_right = st.columns([1, 1.4, 1])
    with col_mid:
        st.markdown("<h1 style='text-align: center;'>🏠 Xóm Trọ Minh Quân</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b;'>Hệ thống tra cứu hóa đơn & quản lý phòng trọ trực tuyến</p>", unsafe_allow_html=True)

        login_tab_cus, login_tab_adm = st.tabs(["👤 Khách thuê (Xem hóa đơn)", "🔑 Chủ trọ (Admin)"])

        with login_tab_cus:
            st.info("Chọn phòng của bạn và nhập **Mật khẩu phòng** do chủ trọ cung cấp để xem tiền phòng & lịch sử.")
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
            st.info("Khu vực dành riêng cho **Chủ trọ** quản lý, nhập số điện và chốt sổ.")
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
    tong_cong = int(row["Tiền phòng"]) + tien_dien + tien_dv + tien_khac

    with st.sidebar:
        st.header("👤 Tài khoản Khách thuê")
        seri_info = f"\n\n🔌 Seri công tơ: **{seri_ct}**" if seri_ct else ""
        st.success(f"Đang xem: **{my_room_name}**\n\nKhách thuê: **{row['Khách thuê']}**{seri_info}")
        st.caption("🔒 Chế độ chỉ xem (không có quyền chỉnh sửa dữ liệu).")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state.role = None
            st.session_state.customer_room = None
            st.rerun()

    st.title(f"🏠 Xóm Trọ Minh Quân — {my_room_name}")
    trang_thai_text = "✅ ĐÃ THANH TOÁN" if row["Đã thu"] else "⏳ CHƯA THANH TOÁN"
    seri_badge = f" | 🔌 Công tơ: `{seri_ct}`" if seri_ct else ""
    st.markdown(f"### 📋 Hóa đơn kỳ {thang_ghi}{seri_badge} | Trạng thái: **{trang_thai_text}**")

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
                chart_my_kwh = my_hist.set_index("Kỳ thu")[["Số kWh"]]
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

    st.write(f"Hệ thống sẽ tự động gửi hóa đơn **kỳ {thang_ghi}** tới **{len(valid_rooms)} phòng** sau:")
    for _, r in valid_rooms.iterrows():
        st.info(f"🏠 **{r['Phòng']}** ({r['Khách thuê']}) ➔ `{r['Email khách']}` — Tổng: **{int(r['Tổng cộng']):,.0f} đ**")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 Gửi Email ngay", type="primary", use_container_width=True):
            ok_list, fail_list = [], []
            progress = st.progress(0)
            total = len(valid_rooms)
            for idx_step, (_, r) in enumerate(valid_rooms.iterrows(), start=1):
                subj = f"[Xóm Trọ Minh Quân] Thông báo tiền phòng kỳ {thang_ghi} - {r['Phòng']}"
                body = build_invoice_message(r, thang_ghi, gia_dien)
                success, err = send_invoice_email(r["Email khách"], subj, body)
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

@st.dialog("🔒 Xác nhận chốt sổ & chuyển kỳ mới")
def confirm_close_month_dialog(df_rooms, calc_df, thang_ghi, gia_dien):
    st.write(f"Bạn có chắc chắn muốn **CHỐT SỔ KỲ {thang_ghi}** không?")
    close_info = f"""Sau khi xác nhận:
1. Toàn bộ số liệu kỳ **{thang_ghi}** (bao gồm số seri công tơ, tiền khác & ghi chú) sẽ được lưu vào **Lịch sử các tháng trước**.
2. Chỉ số **Điện mới** sẽ tự động chuyển thành **Điện cũ** cho tháng tiếp theo.
3. **Tiền khác**, **Ghi chú** và trạng thái **Đã thu** sẽ được đặt lại về 0 / trống cho kỳ mới."""
    st.info(close_info)

    valid_emails = calc_df[calc_df["Email khách"].astype(str).str.contains("@", na=False)]
    auto_send_mail = False
    if not valid_emails.empty:
        auto_send_mail = st.checkbox(f"📧 Đồng thời tự động gửi hóa đơn kỳ {thang_ghi} qua Email cho {len(valid_emails)} phòng đã có email", value=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Chốt sổ ngay", type="primary", use_container_width=True):
            if auto_send_mail and not valid_emails.empty:
                for _, r in valid_emails.iterrows():
                    subj = f"[Xóm Trọ Minh Quân] Thông báo tiền phòng kỳ {thang_ghi} - {r['Phòng']}"
                    body = build_invoice_message(r, thang_ghi, gia_dien)
                    send_invoice_email(r["Email khách"], subj, body)

            record_df = calc_df.copy()
            if "Mật khẩu phòng" in record_df.columns:
                record_df = record_df.drop(columns=["Mật khẩu phòng"])
            record_df.insert(0, "Kỳ thu", thang_ghi)
            record_df.insert(1, "Ngày chốt", datetime.now().strftime("%d/%m/%Y %H:%M"))
            record_df["Đơn giá điện"] = gia_dien
            
            old_hist = load_history()
            if not old_hist.empty:
                save_history(pd.concat([record_df, old_hist], ignore_index=True))
            else:
                save_history(record_df)

            next_df = df_rooms.copy()
            next_df["Điện cũ"] = next_df["Điện mới"]
            next_df["Tiền khác"] = 0
            next_df["Ghi chú"] = ""
            next_df["Đã thu"] = False
            write_table(next_df, "rooms", ROOMS_FILE)
            st.session_state.editor_key += 1
            
            st.toast(f"Đã chốt sổ kỳ {thang_ghi} thành công!", icon="🎉")
            st.rerun()
    with c2:
        if st.button("❌ Quay lại kiểm tra", use_container_width=True):
            st.rerun()

# ==========================================
# GIAO DIỆN QUẢN TRỊ CHỦ TRỌ (ADMIN)
# ==========================================
def render_admin_view(df, gia_dien_saved, thang_ghi_saved):
    storage_mode = "☁️ Google Sheets (Cloud)" if get_gsheet_client() is not None else "💻 File CSV trên máy tính"
    sender_mail, _ = get_email_credentials()
    mail_status = f"📧 Gmail tự động: **{sender_mail}**" if sender_mail else "⚠️ Chưa cấu hình Gmail tự động"
    st.title("🏠 Xóm Trọ Minh Quân - Quản Trị Chủ Trọ")

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
        ten_phong = st.text_input("Tên phòng (VD: Phòng 103)")
        khach_thue = st.text_input("Tên khách thuê")
        email_khach_moi = st.text_input("Email khách thuê (VD: khach@gmail.com)")
        seri_cong_to_moi = st.text_input("Số seri công tơ điện (VD: 24051988)")
        mk_phong_moi = st.text_input("Mật khẩu xem phòng (cho khách)", value="123456")
        gia_phong_moi = st.number_input("Giá thuê phòng (VNĐ)", min_value=0, value=2500000, step=100000)
        so_dien_dau = st.number_input("Chỉ số điện ban đầu", min_value=0, value=0)

        c_s1, c_s2, c_s3 = st.columns(3)
        with c_s1:
            gia_nuoc_moi = st.number_input("Nước", min_value=0, value=100000, step=10000)
        with c_s2:
            gia_rac_moi = st.number_input("Rác", min_value=0, value=30000, step=5000)
        with c_s3:
            gia_an_ninh_moi = st.number_input("An ninh", min_value=0, value=20000, step=5000)

        gia_khac_moi = st.number_input("Tiền khác (VNĐ - có thể nhập âm để giảm trừ)", value=0, step=10000)
        ghi_chu_moi = st.text_input("Ghi chú khoản tiền khác (VD: Sửa vòi nước, cọc...)")

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
                    "Đã thu": False
                })

        st.divider()
        st.subheader("🗑️ Xóa phòng khỏi danh sách")
        if not df.empty:
            room_options = {f"{row['Phòng']} ({row['Khách thuê']})": idx for idx, row in df.iterrows()}
            selected_del_label = st.selectbox("Chọn phòng cần xóa:", list(room_options.keys()))
            if st.button("Xóa phòng đã chọn", use_container_width=True):
                del_idx = room_options[selected_del_label]
                confirm_delete_room_dialog(del_idx, df.iloc[del_idx])

    tab1, tab2, tab3 = st.tabs(["📋 Nhập số điện & Thu tiền", "📊 Biểu đồ & Gửi Zalo / Email", "🗂️ Lịch sử các tháng trước"])

    with tab1:
        st.info("💡 Chỉnh sửa bất kỳ ô nào trên bảng dưới đây (bao gồm **Email khách**, **Seri công tơ**, **Tiền khác** và **Ghi chú**) — phần mềm sẽ **hỏi xác nhận và tự động lưu ngay lập tức**.")
        edited_df = st.data_editor(
            df,
            key=f"room_editor_{st.session_state.editor_key}",
            num_rows="fixed",
            use_container_width=True,
            column_config={
                "Email khách": st.column_config.TextColumn(help="Địa chỉ Gmail của khách để hệ thống tự động gửi hóa đơn hàng tháng"),
                "Mật khẩu phòng": st.column_config.TextColumn(help="Mật khẩu riêng để khách phòng này đăng nhập xem hóa đơn"),
                "Seri công tơ": st.column_config.TextColumn(help="Số seri in trên mặt công tơ điện để đối chiếu tránh ghi nhầm phòng"),
                "Tiền phòng": st.column_config.NumberColumn(format="%d đ"),
                "Điện cũ": st.column_config.NumberColumn(min_value=0, step=1),
                "Điện mới": st.column_config.NumberColumn(min_value=0, step=1),
                "Tiền nước": st.column_config.NumberColumn(format="%d đ", min_value=0, step=10000),
                "Tiền rác": st.column_config.NumberColumn(format="%d đ", min_value=0, step=5000),
                "An ninh": st.column_config.NumberColumn(format="%d đ", min_value=0, step=5000),
                "Tiền khác": st.column_config.NumberColumn(format="%d đ", step=10000, help="Khoản phát sinh thêm hoặc giảm trừ (nhập số âm nếu giảm tiền)"),
                "Ghi chú": st.column_config.TextColumn(width="medium", help="Ghi rõ lý do khoản tiền khác (VD: Sửa khóa, thay bóng đèn, trừ tiền cọc...)"),
            }
        )

        pending_changes = get_changes_summary(df, edited_df)
        if pending_changes:
            confirm_instant_change_dialog(edited_df, pending_changes)

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

        display_cols = ["Phòng", "Khách thuê", "Seri công tơ", "Số kWh", "Tiền điện", "Tiền nước", "Tiền rác", "An ninh", "Tiền khác", "Ghi chú", "Tiền phòng", "Tổng cộng", "Đã thu"]
        styled_df = calc_df[display_cols].style.apply(highlight_status, axis=1).format({
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
            if st.button("✅ Chốt sổ tháng này & Chuyển kỳ mới", type="primary", use_container_width=True):
                if (calc_df["Số kWh"] < 0).any():
                    st.error("Không thể chốt sổ vì đang có phòng bị âm số điện!")
                else:
                    confirm_close_month_dialog(df, calc_df, thang_ghi, gia_dien)

    with tab2:
        col_chart, col_zalo = st.columns([1.2, 1])
        with col_chart:
            st.subheader("📊 Biểu đồ chi phí & doanh thu theo phòng")
            if not calc_df.empty:
                chart_df = calc_df.copy()
                chart_df["Dịch vụ & Khác"] = chart_df["Dịch vụ (Nước+Rác+AN)"] + chart_df["Tiền khác"]
                chart_data = chart_df.set_index("Phòng")[["Tiền phòng", "Tiền điện", "Dịch vụ & Khác"]]
                st.bar_chart(chart_data, color=["#3b82f6", "#f59e0b", "#06b6d4"])
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
                        ok, err = send_invoice_email(email_hien_tai, subj, msg)
                        if ok:
                            st.success(f"✅ Đã gửi hóa đơn cho {row_p['Phòng']} thành công!")
                        else:
                            st.error(f"❌ Lỗi gửi email: {err}")
                else:
                    st.caption("ℹ️ Phòng này chưa nhập Email khách (bạn có thể điền ở bảng Tab 1 để gửi tự động).")

                st.info("Hoặc bấm biểu tượng Copy ở góc phải khung dưới để dán gửi Zalo:")
                st.code(msg, language="text")

    with tab3:
        hist_df = load_history()
        if not hist_df.empty:
            st.subheader("📈 Biểu đồ doanh thu qua các kỳ đã chốt")
            cols_to_plot = [c for c in ["Tiền phòng", "Tiền điện", "Dịch vụ (Nước+Rác+AN)", "Tiền khác"] if c in hist_df.columns]
            if cols_to_plot and "Kỳ thu" in hist_df.columns:
                rev_by_month = hist_df.groupby("Kỳ thu", sort=False)[cols_to_plot].sum()
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
            st.info("Chưa có dữ liệu lịch sử nào được chốt sổ. Hãy bấm nút 'Chốt sổ tháng này' ở Tab 1 để lưu kỳ đầu tiên.")

df_rooms_all = load_rooms()
gia_dien_cfg, thang_ghi_cfg = load_config()

if st.session_state.role is None:
    render_login_screen(df_rooms_all)
elif st.session_state.role == "customer":
    render_customer_view(df_rooms_all, gia_dien_cfg, thang_ghi_cfg)
elif st.session_state.role == "admin":
    render_admin_view(df_rooms_all, gia_dien_cfg, thang_ghi_cfg)