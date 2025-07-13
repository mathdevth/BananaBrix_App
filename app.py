import streamlit as st
import cv2
import numpy as np
import joblib
from PIL import Image
import io
import os

# --- ฟังก์ชัน get_avg_color_rgb (สำหรับประมวลผลสี) ---
def get_avg_color_rgb(image_array):
    img = image_array
    # image_array ที่รับเข้ามาจาก Streamlit จะเป็น RGB
    # แต่ OpenCV (cv2) โดยทั่วไปทำงานกับ BGR.
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # Step 1: กำหนดช่วงสีของกล้วยในรูปแบบ BGR
    # ค่าเหล่านี้อาจต้องปรับจูนตามสภาพแสงและชนิดกล้วยที่คุณครูใช้
    # (B, G, R)
    lower_banana_color_bgr = np.array([0, 80, 80])    # สีค่อนไปทางน้ำเงิน/เขียวน้อยๆ
    upper_banana_color_bgr = np.array([120, 255, 255]) # สีค่อนไปทางแดง/เหลืองมาก

    # Step 2: สร้าง Mask เพื่อกรองพิกเซลที่อยู่ในช่วงสีที่กำหนด
    color_mask = cv2.inRange(img_bgr, lower_banana_color_bgr, upper_banana_color_bgr)

    # Step 3: หา Contours (โครงร่างของวัตถุที่เชื่อมต่อกัน) ใน Mask
    # RETR_EXTERNAL: ค้นหาเฉพาะโครงร่างภายนอก
    # CHAIN_APPROX_SIMPLE: บีบอัดจุดโครงร่างให้เรียบง่าย
    contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Step 4: หา Contours ที่มีพื้นที่ใหญ่ที่สุด (สันนิษฐานว่าเป็นกล้วย)
    max_area = 0
    largest_contour = None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > max_area:
            max_area = area
            largest_contour = contour

    # Step 5: กำหนดเกณฑ์ขั้นต่ำของพื้นที่พิกเซลที่ยอมรับว่าเป็นกล้วย
    # **สำคัญมาก: ปรับค่านี้ตามขนาดของกล้วยในภาพถ่ายของคุณครู**
    # ถ้าภาพกล้วยมีขนาดเล็กในภาพรวม ค่านี้ก็ควรน้อย
    min_banana_pixel_area = 5000 # ค่าเริ่มต้น ลองปรับเพิ่ม/ลด หากพบว่าตรวจจับผิดพลาด

    # Step 6: ตรวจสอบว่าพบวัตถุที่ใหญ่พอและมีลักษณะเป็นสีของกล้วยหรือไม่
    if largest_contour is None or max_area < min_banana_pixel_area:
        # หากไม่พบวัตถุขนาดใหญ่พอ หรือไม่มีวัตถุที่อยู่ในช่วงสีที่กำหนด
        return None, None, None # คืนค่า None เพื่อแจ้งว่าไม่พบกล้วย/ประมวลผลไม่ได้

    # Step 7: สร้าง Mask ใหม่ที่มีเฉพาะวัตถุที่ใหญ่ที่สุด (กล้วย) เท่านั้น
    final_mask = np.zeros(img_bgr.shape[:2], dtype="uint8") # สร้าง Mask สีดำเปล่าๆ
    cv2.drawContours(final_mask, [largest_contour], -1, 255, -1) # วาดโครงร่างที่ใหญ่ที่สุดให้เป็นสีขาว (255) ลงบน Mask

    # Step 8: คำนวณค่าเฉลี่ย BGR ของพิกเซล โดยใช้ Mask สุดท้ายนี้ (เฉพาะส่วนที่เป็นกล้วย)
    mean_bgr = cv2.mean(img_bgr, mask=final_mask)[:3] # ใช้ final_mask

    avg_red = mean_bgr[2] # BGR -> RGB (R คือ index 2)
    avg_green = mean_bgr[1] # G คือ index 1
    avg_blue = mean_bgr[0] # B คือ index 0

    return avg_red, avg_green, avg_blue

# --- ฟังก์ชันประเมินระดับความสุกและให้คำแนะนำจากค่า Brix ---
# ปรับช่วงค่า Brix และคำอธิบายตามความเหมาะสมกับข้อมูลของคุณครู
def predict_ripeness(brix_value):
    ripeness_level_num = 0 # กำหนดค่าเริ่มต้น
    status_desc = ""
    advice_text = ""

    # คำนวณร้อยละความสุก (Brix 0% = 0, Brix 30% = 100%)
    # ค่า 30.0 เป็นค่า Brix สูงสุดที่คาดการณ์ว่าเป็นสุกจัดเต็มที่
    percentage_ripeness = min(100.0, max(0.0, (brix_value / 30.0) * 100.0))

    if brix_value <= 5.0:
        ripeness_level_num = 1
        status_desc = "กล้วยน้ำว้าดิบ"
        advice_text = "⭐️ กล้วยยังดิบอยู่ มีแป้งสูงมาก ควรบ่มต่อในที่แห้ง มีอากาศถ่ายเท หรือบ่มร่วมกับผลไม้ที่ปล่อยก๊าซเอทิลีน (เช่น แอปเปิล) อาจใช้เวลา 5-7 วันเพื่อให้สุกตามต้องการ"
    elif 5.0 < brix_value <= 8.0:
        ripeness_level_num = 2
        status_desc = "กล้วยน้ำว้าดิบ (เริ่มอมเหลือง)"
        advice_text = "✨ กล้วยยังดิบอยู่แต่เริ่มมีสัญญาณการสุก ควรบ่มต่อประมาณ 3-5 วัน เพื่อให้ได้ความหวานที่เพิ่มขึ้น"
    elif 8.0 < brix_value <= 12.0:
        ripeness_level_num = 3
        status_desc = "กล้วยน้ำว้าที่เริ่มสุก (เหลืองปนเขียว)"
        advice_text = "😊 กล้วยเริ่มสุกแล้ว เนื้อเริ่มนิ่ม รสชาติไม่หวานจัด สามารถรับประทานได้สำหรับผู้ที่ชอบกล้วยไม่หวานมาก หรือบ่มต่อ 2-3 วันให้สุกนิ่มขึ้น"
    elif 12.0 < brix_value <= 18.0:
        ripeness_level_num = 4
        status_desc = "กล้วยน้ำว้าสุกพอดี (เหลืองทั้งผล)"
        advice_text = "😋 กล้วยสุกกำลังดี เนื้อนิ่ม หวานอร่อย เหมาะสำหรับการรับประทานสด หรือนำไปประกอบอาหารที่ไม่ต้องการความหวานมาก"
    elif 18.0 < brix_value <= 22.0:
        ripeness_level_num = 5
        status_desc = "กล้วยน้ำว้าสุก (มีจุดน้ำตาลเล็กน้อย)"
        advice_text = "👌 กล้วยสุกกำลังดีถึงสุกงอมเล็กน้อย เนื้อนิ่ม หวานจัด สามารถรับประทานสด หรือนำไปแปรรูปเป็นกล้วยบวชชี หรือเค้กกล้วยหอมได้เลย"
    elif 22.0 < brix_value <= 25.0:
        ripeness_level_num = 6
        status_desc = "กล้วยน้ำว้าสุกงอม (มีจุดน้ำตาลมาก)"
        advice_text = "😉 กล้วยสุกงอม มีความหวานมาก เนื้อนิ่มมาก อาจมีจุดดำบนเปลือก สามารถนำไปแปรรูปทันที เช่น ทำกล้วยเชื่อม กล้วยฉาบ กล้วยตาก หรือทำขนมหวานได้"
    else: # brix_value > 25.0
        ripeness_level_num = 7
        status_desc = "กล้วยน้ำว้าที่สุกจัดมาก (น้ำตาลเกือบทั้งผล)"
        advice_text = "👍 กล้วยสุกจัดมาก เนื้อนิ่มเละ หวานจัด เหมาะสำหรับนำไปแปรรูปทันที เช่น ทำกล้วยบวดชี เค้กกล้วยหอม สมูทตี้ หรือแยม"
    
    return ripeness_level_num, status_desc, advice_text, percentage_ripeness

# --- โค้ด Streamlit App หลัก ---
# กำหนดพาธไปยังโมเดลใน GitHub Repository
# ***สำคัญ***: ไฟล์ banana_brix_model.pkl ต้องอยู่ในโฟลเดอร์เดียวกันกับ app.py ใน GitHub
model_path = 'banana_brix_model.pkl' 
# หากคุณวางไฟล์ .pkl ในโฟลเดอร์ชื่อ 'models' ใน GitHub ให้ใช้ 'models/banana_brix_model.pkl'

# โหลดโมเดลที่ฝึกไว้
try:
    model = joblib.load(model_path)
except FileNotFoundError:
    st.error(f"Error: ไม่พบไฟล์โมเดล '{model_path}' กรุณาตรวจสอบว่าไฟล์อยู่ใน GitHub Repository และพาธถูกต้อง")
    st.stop() # หยุดการทำงานของ Streamlit ถ้าหาโมเดลไม่เจอ

st.title("🍌 แอปประเมินระดับความหวานและสถานะกล้วยน้ำว้า 🍌")
st.markdown("---")

st.header("1. ถ่ายภาพหรืออัปโหลดรูปกล้วยน้ำว้า")
uploaded_file = st.file_uploader("เลือกรูปภาพกล้วยน้ำว้า", type=["jpg", "jpeg", "png"])
camera_input = st.camera_input("หรือ ถ่ายรูปกล้วยน้ำว้าจากกล้อง") # สำหรับถ่ายสดจากกล้องของอุปกรณ์ผู้ใช้

image_source = None
if uploaded_file is not None:
    image_source = uploaded_file
elif camera_input is not None:
    image_source = camera_input

if image_source is not None:
    # อ่านรูปภาพจาก Streamlit
    image_bytes = image_source.read()
    image_pil = Image.open(io.BytesIO(image_bytes))
    image_np = np.array(image_pil) # แปลง PIL Image เป็น NumPy array (RGB)
    
    # ***สำคัญ: ตรงนี้เปลี่ยนจาก image_np_bgr เป็น image_np ที่เป็น RGB ก่อนส่งเข้า get_avg_color_rgb***
    # แล้วให้ get_avg_color_rgb แปลงเป็น BGR เอง
    ripeness_result = get_avg_color_rgb(image_np) 

    st.image(image_pil, caption='รูปภาพกล้วยน้ำว้าของคุณ', use_column_width=True)

    st.header("2. ผลการประเมิน")
    if st.button('ประเมินสถานะกล้วย'):
        with st.spinner('กำลังวิเคราะห์...'):
            # ตรวจสอบว่า get_avg_color_rgb คืนค่า None (ไม่พบกล้วย) หรือไม่
            if ripeness_result[0] is None: # ถ้า r_avg เป็น None
                st.warning("ไม่พบกล้วยในภาพ หรือภาพไม่ชัดเจน กรุณาลองถ่ายภาพใหม่ให้เห็นกล้วยชัดเจน")
            else:
                r_avg, g_avg, b_avg = ripeness_result # ดึงค่า R, G, B ออกมา

                # เตรียมข้อมูลสำหรับทำนาย (ต้องเป็นรูปแบบ 2D array)
                input_features = np.array([[r_avg, g_avg, b_avg]])
                predicted_brix = model.predict(input_features)[0]

                # ใช้ฟังก์ชันใหม่ในการประเมินระดับความสุกและคำแนะนำ
                ripeness_level_num, ripeness_status, advice, percentage_ripeness = predict_ripeness(predicted_brix)

                st.success("ประเมินเสร็จสิ้น!")
                st.metric(label="ระดับความหวาน (Brix)", value=f"{predicted_brix:.2f} °Bx")
                st.metric(label="ร้อยละความสุก", value=f"{percentage_ripeness:.1f}%") # แสดงผลร้อยละความสุก
                st.subheader(f"สถานะกล้วยน้ำว้า: {ripeness_status}")
                st.subheader(f"ระดับความสุก: {ripeness_level_num} (จาก 7 ระดับ)")
                st.info(advice) # แสดงคำแนะนำ
                st.caption(f"ค่าสีเฉลี่ย (RGB) ที่ได้: R={r_avg:.0f}, G={g_avg:.0f}, B={b_avg:.0f}")

st.markdown("---")
st.caption("พัฒนาโดย นางสาวนรินทร์ธร พิมสา, นางสาวนิชาภา ศรีละวัลย์ และนางสาวรัตนาวดี สว่างศรี\nอาจารย์ที่ปรึกษา: นายอชิตพล บุณรัตน์, นางสาวปทุมวดี วงษ์สุธรรม และนางสาวสมใจ จันทรงกรด\nโรงเรียนวังโพรงพิทยาคม สำนักงานเขตพื้นที่การศึกษามัธยมศึกษาพิษณุโลก อุตรดิตถ์")
