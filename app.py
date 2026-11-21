import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="Xóm Trọ Minh Quân", page_icon="🏠", layout="wide")

ROOMS_FILE = "rooms.csv"
HISTORY_FILE = "history.csv"

# Khởi tạo biến trạng thái để reset bảng khi Hủy thay đổi
if "editor_key" not in st.session_state:
    st.session_state.editor_key = 0

# CSS tùy chỉnh để giao diện hiện đại, có thẻ màu gradient và đổ bóng
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

# 1. Khởi tạo & tự động nâng cấp cột dữ liệu
def load_rooms():
    default_cols = {
        "Phòng": "Phòng mới",
        "Khách thuê": "",
        "Tiền phòng": 2500000,
        "Điện cũ": 0,
        "Điện mới": 0,
        "Tiền nước": 100000,
        "Tiền rác": 30000,
        "An ninh": 20000,
        "Đã thu": False
    }
    if os.path.exists(ROOMS_FILE):
        df = pd.read_csv(ROOMS_FILE)
        changed = False
        for col, default_val in default_cols.items():
            if col not in df.columns:
                df[col] = default_val
                changed = True
        ordered_cols = ["Phòng", "Khách thuê", "Tiền phòng", "Điện cũ", "Điện mới", "Tiền nước", "Tiền rác", "An ninh", "Đã thu"]
        df = df[ordered_cols]
        if changed:
            df.to_csv(ROOMS_FILE, index=False)
        return df

    df = pd.DataFrame([
        {"Phòng": "Phòng 101", "Khách thuê": "Nguyễn Văn A", "Tiền phòng": 2500000, "Điện cũ": 1200, "Điện mới": 1285, "Tiền nước": 100000, "Tiền rác": 30000, "An ninh": 20000, "Đã thu": False},
        {"Phòng": "Phòng 102", "Khách thuê": "Trần Thị B", "Tiền phòng": 2800000, "Điện cũ": 850, "Điện mới": 940, "Tiền nước": 100000, "Tiền rác": 30000, "An ninh": 20000, "Đã thu": False},
    ])
    df.to_csv(ROOMS_FILE, index=False)
    return df

# Hàm phát hiện chính xác ô vừa thay đổi
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

# Hộp thoại xác nhận TỨC THÌ ngay khi sửa 1 ô
@st.dialog("⚠️ Xác nhận thay đổi")
def confirm_instant_change_dialog(edited_df, changes_list):
    st.write("Bạn có muốn lưu thay đổi vừa nhập không?")
    for item in changes_list:
        st.info(item)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Đồng ý & Lưu luôn", type="primary", use_container_width=True):
            edited_df.to_csv(ROOMS_FILE, index=False)
            st.session_state.editor_key += 1
            st.toast("Đã lưu thay đổi!", icon="✅")
            st.rerun()
    with c2:
        if st.button("❌ Hủy (Hoàn tác)", use_container_width=True):
            st.session_state.editor_key += 1
            st.toast("Đã hủy thay đổi!", icon="↩️")
            st.rerun()

# Hộp thoại xác nhận thêm phòng mới
@st.dialog("⚠️ Xác nhận thêm phòng mới")
def confirm_add_room_dialog(new_room_data):
    st.write("Bạn có chắc chắn muốn **thêm phòng mới** này vào danh sách không?")
    info_text = f"""**Phòng:** {new_room_data['Phòng']} | **Khách thuê:** {new_room_data['Khách thuê'] or 'Chưa có'}

**Tiền phòng:** {new_room_data['Tiền phòng']:,.0f} đ | **Điện đầu:** {new_room_data['Điện cũ']}

**Dịch vụ:** Nước {new_room_data['Tiền nước']:,.0f}đ • Rác {new_room_data['Tiền rác']:,.0f}đ • An ninh {new_room_data['An ninh']:,.0f}đ"""
    st.info(info_text)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Đồng ý thêm", type="primary", use_container_width=True):
            df_curr = load_rooms()
            new_row = pd.DataFrame([new_room_data])
            pd.concat([df_curr, new_row], ignore_index=True).to_csv(ROOMS_FILE, index=False)
            st.session_state.editor_key += 1
            st.toast("Đã thêm phòng mới thành công!", icon="✅")
            st.rerun()
    with c2:
        if st.button("❌ Hủy bỏ", use_container_width=True):
            st.rerun()

# Hộp thoại xác nhận xóa phòng
@st.dialog("🗑️ Xác nhận xóa phòng / khách thuê")
def confirm_delete_room_dialog(room_idx, room_info):
    st.error(f"Bạn có chắc chắn muốn xóa **{room_info['Phòng']}** (Khách thuê: **{room_info['Khách thuê']}**) không?")
    st.write("Hành động này sẽ xóa phòng khỏi danh sách hiện tại (không ảnh hưởng đến lịch sử các tháng đã chốt trước đó).")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Đồng ý xóa", type="primary", use_container_width=True):
            df_curr = load_rooms()
            df_curr = df_curr.drop(index=room_idx).reset_index(drop=True)
            df_curr.to_csv(ROOMS_FILE, index=False)
            st.session_state.editor_key += 1
            st.toast(f"Đã xóa {room_info['Phòng']}!", icon="🗑️")
            st.rerun()
    with c2:
        if st.button("❌ Giữ lại", use_container_width=True):
            st.rerun()

# Hộp thoại xác nhận chốt sổ
@st.dialog("🔒 Xác nhận chốt sổ & chuyển kỳ mới")
def confirm_close_month_dialog(edited_df, calc_df, thang_ghi, gia_dien):
    st.write(f"Bạn có chắc chắn muốn **CHỐT SỔ KỲ {thang_ghi}** không?")
    close_info = f"""Sau khi xác nhận:
1. Toàn bộ số liệu kỳ **{thang_ghi}** sẽ được lưu vào **Lịch sử các tháng trước**.
2. Chỉ số **Điện mới** sẽ tự động chuyển thành **Điện cũ** cho tháng tiếp theo.
3. Trạng thái **Đã thu** sẽ được đặt lại về chưa thu."""
    st.info(close_info)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Chốt sổ ngay", type="primary", use_container_width=True):
            record_df = calc_df.copy()
            record_df.insert(0, "Kỳ thu", thang_ghi)
            record_df.insert(1, "Ngày chốt", datetime.now().strftime("%d/%m/%Y %H:%M"))
            record_df["Đơn giá điện"] = gia_dien
            
            if os.path.exists(HISTORY_FILE):
                old_hist = pd.read_csv(HISTORY_FILE)
                pd.concat([record_df, old_hist], ignore_index=True).to_csv(HISTORY_FILE, index=False)
            else:
                record_df.to_csv(HISTORY_FILE, index=False)

            next_df = edited_df.copy()
            next_df["Điện cũ"] = next_df["Điện mới"]
            next_df["Đã thu"] = False
            next_df.to_csv(ROOMS_FILE, index=False)
            st.session_state.editor_key += 1
            
            st.toast(f"Đã chốt sổ kỳ {thang_ghi} thành công!", icon="🎉")
            st.rerun()
    with c2:
        if st.button("❌ Quay lại kiểm tra", use_container_width=True):
            st.rerun()

st.title("🏠 Xóm Trọ Minh Quân - Quản Lý & Tính Tiền Phòng")

df = load_rooms()

# Thanh cấu hình bên trái
with st.sidebar:
    st.header("⚙️ Cấu hình chung")
    gia_dien = st.number_input("Đơn giá điện (VNĐ/kWh)", min_value=0, value=3500, step=100)
    thang_ghi = st.text_input("Kỳ thu tiền", value=datetime.now().strftime("%m/%Y"))
    
    st.divider()
    st.subheader("➕ Thêm phòng mới")
    ten_phong = st.text_input("Tên phòng (VD: Phòng 103)")
    khach_thue = st.text_input("Tên khách thuê")
    gia_phong_moi = st.number_input("Giá thuê phòng (VNĐ)", min_value=0, value=2500000, step=100000)
    so_dien_dau = st.number_input("Chỉ số điện ban đầu", min_value=0, value=0)
    
    c_s1, c_s2, c_s3 = st.columns(3)
    with c_s1:
        gia_nuoc_moi = st.number_input("Nước", min_value=0, value=100000, step=10000)
    with c_s2:
        gia_rac_moi = st.number_input("Rác", min_value=0, value=30000, step=5000)
    with c_s3:
        gia_an_ninh_moi = st.number_input("An ninh", min_value=0, value=20000, step=5000)

    if st.button("Thêm phòng", use_container_width=True):
        if not ten_phong.strip():
            st.warning("Vui lòng nhập Tên phòng trước khi bấm Thêm!")
        else:
            confirm_add_room_dialog({
                "Phòng": ten_phong.strip(),
                "Khách thuê": khach_thue.strip(),
                "Tiền phòng": gia_phong_moi,
                "Điện cũ": so_dien_dau,
                "Điện mới": so_dien_dau,
                "Tiền nước": gia_nuoc_moi,
                "Tiền rác": gia_rac_moi,
                "An ninh": gia_an_ninh_moi,
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

# Chia 3 Tab trực quan
tab1, tab2, tab3 = st.tabs(["📋 Nhập số điện & Thu tiền", "📊 Biểu đồ & Gửi Zalo", "🗂️ Lịch sử các tháng trước"])

with tab1:
    st.info("💡 Chỉnh sửa bất kỳ ô nào trên bảng dưới đây — phần mềm sẽ **hỏi xác nhận và tự động lưu ngay lập tức** sau từng thay đổi.")
    
    # Dùng key động để có thể hoàn tác sạch sẽ nếu người dùng bấm Hủy
    edited_df = st.data_editor(
        df,
        key=f"room_editor_{st.session_state.editor_key}",
        num_rows="fixed",
        use_container_width=True,
        column_config={
            "Tiền phòng": st.column_config.NumberColumn(format="%d đ"),
            "Điện cũ": st.column_config.NumberColumn(min_value=0, step=1),
            "Điện mới": st.column_config.NumberColumn(min_value=0, step=1),
            "Tiền nước": st.column_config.NumberColumn(format="%d đ", min_value=0, step=10000),
            "Tiền rác": st.column_config.NumberColumn(format="%d đ", min_value=0, step=5000),
            "An ninh": st.column_config.NumberColumn(format="%d đ", min_value=0, step=5000),
        }
    )

    # Tự động bật hộp thoại hỏi & lưu ngay khi phát hiện thay đổi
    pending_changes = get_changes_summary(df, edited_df)
    if pending_changes:
        confirm_instant_change_dialog(edited_df, pending_changes)

    # Tính toán tự động dựa trên dữ liệu đã lưu
    calc_df = df.copy()
    calc_df["Số kWh"] = calc_df["Điện mới"] - calc_df["Điện cũ"]
    calc_df["Tiền điện"] = calc_df["Số kWh"].apply(lambda x: x * gia_dien if x >= 0 else 0)
    calc_df["Dịch vụ (Nước+Rác+AN)"] = calc_df["Tiền nước"] + calc_df["Tiền rác"] + calc_df["An ninh"]
    calc_df["Tổng cộng"] = calc_df["Tiền phòng"] + calc_df["Tiền điện"] + calc_df["Dịch vụ (Nước+Rác+AN)"]

    if (calc_df["Số kWh"] < 0).any():
        st.error("⚠️ Cảnh báo: Có phòng đang có Số điện mới nhỏ hơn Số điện cũ! Vui lòng kiểm tra lại.")

    # Thẻ KPI màu sắc sinh động (4 cột)
    tong_dien = calc_df["Tiền điện"].sum()
    tong_kwh = calc_df["Số kWh"].clip(lower=0).sum()
    tong_dich_vu = calc_df["Dịch vụ (Nước+Rác+AN)"].sum()
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
        st.markdown(f"""
        <div class="metric-card service">
            <div class="metric-title">💧 Nước, Rác & An ninh</div>
            <div class="metric-value">{tong_dich_vu:,.0f} đ</div>
            <div class="metric-sub">Tổng phí dịch vụ các phòng</div>
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

    # Hiển thị bảng kết quả tổng hợp có tô màu trạng thái
    st.subheader("📑 Bảng kê chi tiết cần thu")
    
    def highlight_status(row):
        if row["Đã thu"]:
            return ["background-color: #dcfce7; color: #166534"] * len(row)
        elif row["Số kWh"] < 0:
            return ["background-color: #fee2e2; color: #991b1b"] * len(row)
        return [""] * len(row)

    display_cols = ["Phòng", "Khách thuê", "Số kWh", "Tiền điện", "Tiền nước", "Tiền rác", "An ninh", "Tiền phòng", "Tổng cộng", "Đã thu"]
    styled_df = calc_df[display_cols].style.apply(highlight_status, axis=1).format({
        "Số kWh": "{:,.0f}",
        "Tiền điện": "{:,.0f} đ",
        "Tiền nước": "{:,.0f} đ",
        "Tiền rác": "{:,.0f} đ",
        "An ninh": "{:,.0f} đ",
        "Tiền phòng": "{:,.0f} đ",
        "Tổng cộng": "{:,.0f} đ"
    })
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    st.divider()
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
            chart_data = calc_df.set_index("Phòng")[["Tiền phòng", "Tiền điện", "Dịch vụ (Nước+Rác+AN)"]]
            st.bar_chart(chart_data, color=["#3b82f6", "#f59e0b", "#06b6d4"])
            
            st.caption("Biểu đồ số điện tiêu thụ (kWh) từng phòng:")
            kwh_chart = calc_df.set_index("Phòng")[["Số kWh"]]
            st.bar_chart(kwh_chart, color="#10b981")

    with col_zalo:
        st.subheader("💬 Tạo tin nhắn báo tiền gửi Zalo")
        if not calc_df.empty:
            ds_phong = calc_df["Phòng"].tolist()
            phong_chon = st.selectbox("Chọn phòng cần gửi hóa đơn:", ds_phong)
            row_p = calc_df[calc_df["Phòng"] == phong_chon].iloc[0]
            
            msg = f"""📢 THÔNG BÁO TIỀN PHÒNG XÓM TRỌ MINH QUÂN - KỲ {thang_ghi}
🏠 Phòng: {row_p['Phòng']} ({row_p['Khách thuê']})
------------------------
• Tiền thuê phòng: {row_p['Tiền phòng']:,.0f} đ
• Chỉ số điện: {row_p['Điện cũ']:,.0f} ➔ {row_p['Điện mới']:,.0f} ({row_p['Số kWh']:,.0f} kWh)
• Tiền điện ({gia_dien:,.0f}đ/kWh): {row_p['Tiền điện']:,.0f} đ
• Tiền nước: {row_p['Tiền nước']:,.0f} đ
• Tiền rác: {row_p['Tiền rác']:,.0f} đ
• Phí an ninh: {row_p['An ninh']:,.0f} đ
------------------------
💰 TỔNG CỘNG CẦN THANH TOÁN: {row_p['Tổng cộng']:,.0f} đ
Anh/chị vui lòng thanh toán sớm giúp Xóm Trọ Minh Quân nhé. Xin cảm ơn!"""
            
            st.info("Bấm vào biểu tượng Copy ở góc trên bên phải khung dưới đây để dán gửi Zalo:")
            st.code(msg, language="text")

with tab3:
    if os.path.exists(HISTORY_FILE):
        hist_df = pd.read_csv(HISTORY_FILE)
        
        st.subheader("📈 Biểu đồ doanh thu qua các kỳ đã chốt")
        cols_to_plot = [c for c in ["Tiền phòng", "Tiền điện", "Dịch vụ (Nước+Rác+AN)"] if c in hist_df.columns]
        rev_by_month = hist_df.groupby("Kỳ thu", sort=False)[cols_to_plot].sum()
        st.bar_chart(rev_by_month)
        
        st.divider()
        ky_list = ["Tất cả"] + list(hist_df["Kỳ thu"].unique())
        chon_ky = st.selectbox("Lọc chi tiết theo kỳ thu tiền:", ky_list)
        
        view_df = hist_df if chon_ky == "Tất cả" else hist_df[hist_df["Kỳ thu"] == chon_ky]
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