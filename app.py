import os, io, base64
from PIL import Image

im = Image.open("input_file_12.png").convert("RGB")
w, h = im.size
im_cropped = im.crop((0, 0, w, h - 48))
im_resized = im_cropped.resize((960, int(im_cropped.size[1] * (960 / im_cropped.size[0]))), Image.Resampling.LANCZOS)
buf = io.BytesIO()
im_resized.save(buf, format="JPEG", quality=55, optimize=True)
bg_b64_compact = base64.b64encode(buf.getvalue()).decode("utf-8")
print("Compact bg_b64 length:", len(bg_b64_compact))

with open("app-v7.py", "r", encoding="utf-8") as f:
    code = f.read()

old_compress = '''def compress_image_to_base64(uploaded_file, max_width=720, quality=65):
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
        return ""'''

new_compress = '''def compress_image_to_base64(uploaded_file, max_width=640, quality=60):
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
        return ""'''

assert old_compress in code, "old_compress not found"
code = code.replace(old_compress, new_compress, 1)

old_gsheet_io = '''def get_gsheet_client():
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
    df.to_csv(csv_file, index=False)'''

new_gsheet_io = '''@st.cache_resource
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
    df.to_csv(csv_file, index=False)'''

assert old_gsheet_io in code, "old_gsheet_io not found"
code = code.replace(old_gsheet_io, new_gsheet_io, 1)

old_load_config = '''def load_config():
    df_cfg = read_table("config", CONFIG_FILE)
    if not df_cfg.empty and "gia_dien" in df_cfg.columns and "thang_ghi" in df_cfg.columns:
        return int(float(df_cfg.iloc[0]["gia_dien"])), str(df_cfg.iloc[0]["thang_ghi"])
    default_gia = 3500
    default_thang = "11/2026"
    save_config(default_gia, default_thang)
    return default_gia, default_thang'''

new_load_config = '''def load_config():
    df_cfg = read_table("config", CONFIG_FILE)
    if df_cfg is None:
        return 3500, "11/2026"
    if not df_cfg.empty and "gia_dien" in df_cfg.columns and "thang_ghi" in df_cfg.columns:
        return int(float(df_cfg.iloc[0]["gia_dien"])), str(df_cfg.iloc[0]["thang_ghi"])
    default_gia = 3500
    default_thang = "11/2026"
    save_config(default_gia, default_thang)
    return default_gia, default_thang'''

assert old_load_config in code, "old_load_config not found"
code = code.replace(old_load_config, new_load_config, 1)

old_load_rooms_head = '''    df = read_table("rooms", ROOMS_FILE)

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
        return df_seeded[ordered_cols]'''

new_load_rooms_head = '''    df = read_table("rooms", ROOMS_FILE)

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
        return df_seeded[ordered_cols]'''

assert old_load_rooms_head in code, "old_load_rooms_head not found"
code = code.replace(old_load_rooms_head, new_load_rooms_head, 1)

old_load_hist = '''def load_history():
    df_h = read_table("history", HISTORY_FILE)
    if not df_h.empty:'''

new_load_hist = '''def load_history():
    df_h = read_table("history", HISTORY_FILE)
    if df_h is None:
        return pd.DataFrame()
    if not df_h.empty:'''

assert old_load_hist in code, "old_load_hist not found"
code = code.replace(old_load_hist, new_load_hist, 1)

old_load_fb = '''def load_feedback():
    df_fb = read_table("feedback", FEEDBACK_FILE)
    expected_cols = ["Thời gian", "Phòng", "Khách thuê", "Nội dung phản hồi", "Trạng thái", "Phản hồi của chủ trọ"]
    if not df_fb.empty:'''

new_load_fb = '''def load_feedback():
    df_fb = read_table("feedback", FEEDBACK_FILE)
    expected_cols = ["Thời gian", "Phòng", "Khách thuê", "Nội dung phản hồi", "Trạng thái", "Phản hồi của chủ trọ"]
    if df_fb is None:
        return pd.DataFrame(columns=expected_cols)
    if not df_fb.empty:'''

assert old_load_fb in code, "old_load_fb not found"
code = code.replace(old_load_fb, new_load_fb, 1)

photo_backup_helpers = '''
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
'''

code = code.replace('FEEDBACK_FILE = "feedback.csv"', 'FEEDBACK_FILE = "feedback.csv"\n' + photo_backup_helpers, 1)

old_photo_col_clean = '''    df["Ghi chú"] = df["Ghi chú"].fillna("").astype(str)
    df["Ảnh công tơ"] = df["Ảnh công tơ"].fillna("").astype(str)'''

new_photo_col_clean = '''    df["Ghi chú"] = df["Ghi chú"].fillna("").astype(str)
    df["Ảnh công tơ"] = df["Ảnh công tơ"].fillna("").astype(str)
    # Tự động khôi phục ảnh đồng hồ từ sheet dự phòng "meter_photos" nếu cột Ảnh công tơ bị trống
    if (df["Ảnh công tơ"].str.strip() == "").all():
        df_p_bak = read_table("meter_photos", "meter_photos.csv")
        if df_p_bak is not None and not df_p_bak.empty and "Phòng" in df_p_bak.columns and "Ảnh công tơ" in df_p_bak.columns:
            photo_map = dict(zip(df_p_bak["Phòng"].astype(str), df_p_bak["Ảnh công tơ"].astype(str)))
            restored_series = df["Phòng"].map(photo_map).fillna("")
            if (restored_series.str.strip() != "").any():
                df["Ảnh công tơ"] = restored_series
                changed = True'''

assert old_photo_col_clean in code, "old_photo_col_clean not found"
code = code.replace(old_photo_col_clean, new_photo_col_clean, 1)

old_save_img_btn = '''                        if up_file is not None:
                            if st.button(f"💾 Lưu ảnh đồng hồ cho {phong_r}", key=f"save_img_{idx_r}", type="primary", use_container_width=True):
                                b64_img = compress_image_to_base64(up_file)
                                if b64_img:
                                    df_upd = df.copy()
                                    df_upd.at[idx_r, "Ảnh công tơ"] = b64_img
                                    write_table(df_upd, "rooms", ROOMS_FILE)
                                    st.toast(f"Đã lưu ảnh đồng hồ {phong_r}!", icon="📸")
                                    st.rerun()'''

new_save_img_btn = '''                        if up_file is not None:
                            if st.button(f"💾 Lưu ảnh đồng hồ cho {phong_r}", key=f"save_img_{idx_r}", type="primary", use_container_width=True):
                                b64_img = compress_image_to_base64(up_file)
                                if b64_img:
                                    df_upd = df.copy()
                                    df_upd.at[idx_r, "Ảnh công tơ"] = b64_img
                                    write_table(df_upd, "rooms", ROOMS_FILE)
                                    backup_meter_photo(phong_r, b64_img)
                                    st.toast(f"Đã lưu ảnh đồng hồ {phong_r}!", icon="📸")
                                    st.rerun()'''

assert old_save_img_btn in code, "old_save_img_btn not found"
code = code.replace(old_save_img_btn, new_save_img_btn, 1)

old_del_img_btn = '''                            if st.button(f"🗑️ Xóa ảnh của {phong_r}", key=f"del_img_{idx_r}"):
                                df_upd = df.copy()
                                df_upd.at[idx_r, "Ảnh công tơ"] = ""
                                write_table(df_upd, "rooms", ROOMS_FILE)
                                st.toast(f"Đã xóa ảnh đồng hồ {phong_r}!", icon="🗑️")
                                st.rerun()'''

new_del_img_btn = '''                            if st.button(f"🗑️ Xóa ảnh của {phong_r}", key=f"del_img_{idx_r}"):
                                df_upd = df.copy()
                                df_upd.at[idx_r, "Ảnh công tơ"] = ""
                                write_table(df_upd, "rooms", ROOMS_FILE)
                                backup_meter_photo(phong_r, "")
                                st.toast(f"Đã xóa ảnh đồng hồ {phong_r}!", icon="🗑️")
                                st.rerun()'''

assert old_del_img_btn in code, "old_del_img_btn not found"
code = code.replace(old_del_img_btn, new_del_img_btn, 1)

old_global_css = """    /* Nền gradient pastel sinh động, tươi sáng */
    .stApp {
        background: linear-gradient(135deg, #e0f2fe 0%, #f0fdf4 45%, #fef3c7 100%);
        background-attachment: fixed;
    }"""

new_global_css = f"""    :root {{
        --loft-bg-img: url("data:image/jpeg;base64,{bg_b64_compact}");
    }}

    /* Nền ảnh phòng trọ gác lửng hiện đại phủ toàn trang (sau khi đăng nhập) */
    .stApp {{
        background-image:
            linear-gradient(135deg, rgba(248, 250, 252, 0.84) 0%, rgba(240, 249, 255, 0.82) 50%, rgba(236, 253, 245, 0.84) 100%),
            var(--loft-bg-img);
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}"""

assert old_global_css in code, "old_global_css not found"
code = code.replace(old_global_css, new_global_css, 1)

start_marker = "    st.markdown(\"\"\"\n    <style>\n        /* Hình nền kiến trúc dãy nhà trọ"
end_marker = "    </style>\n    \"\"\", unsafe_allow_html=True)"
s_idx = code.index(start_marker)
e_idx = code.index(end_marker, s_idx) + len(end_marker)

new_login_style = """    st.markdown(\"\"\"
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
    \"\"\", unsafe_allow_html=True)"""

code = code[:s_idx] + new_login_style + code[e_idx:]

with open("app-v9.py", "w", encoding="utf-8") as f:
    f.write(code)

compile(code, "app-v9.py", "exec")
print("Saved app-v9.py successfully! Total size:", len(code))