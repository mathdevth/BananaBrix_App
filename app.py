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
    # กำหนดช่วงสี BGR ของกล้วย (อาจต้องปรับจูนตามสภาพแสงและชนิดกล้วย)
    lower_banana_color_bgr = np.array([0, 80, 80])
    upper_banana_color_bgr = np.array([120, 255, 255])

    # สร้าง Mask เพื่อเลือกเฉพาะส่วนที่เป็นกล้วย
    mask = cv2.inRange(img, lower_banana_color_bgr, upper_banana_color_bgr)

    # ตรวจสอบว่ามีพิกเซลที่ตรงกับสีที่กำหนดหรือไม่
    if np.count_nonzero(mask) == 0:
        st.warning("ไม่พบพิกเซลสีที่เกี่ยวข้องกับกล้วย โปรดตรวจสอบแสงและภาพ")
        return None, None, None

    # คำนวณค่าเฉลี่ย BGR ของพิกเซลใน Mask
    mean_bgr = cv2.mean(img, mask=mask)[:3]
    avg_red = mean_bgr[2] # BGR -> RGB (R คือ index 2)
    avg_green = mean_bgr[1] # G คือ index 1
    avg_blue = mean_bgr[0] # B คือ index 0

    return avg_red, avg_green, avg_blue

# --- ฟังก์ชันประเมินระดับความสุกและให้คำแนะนำจากค่า Brix ---
# ปรับช่วงค่า Brix และคำอธิบายตามความเหมาะสมกับข้อมูลของคุณครู
def predict_ripeness(brix_value):
    if brix_value <= 8.0:
        return "กล้วยน้ำว้าดิบ", "⭐️ กล้วยยังดิบอยู่ มีแป้งสูง ควรบ่มต่อในที่แห้ง มีอากาศถ่ายเท อาจใช้เวลา 5-7 วันเพื่อให้สุกตามต้องการ"
    elif 8.0 < brix_value <= 14.0:
        return "กล้วยน้ำว้าที่เริ่มสุก", "😊 กล้วยเริ่มสุกแล้ว เนื้อเริ่มนิ่ม รสชาติไม่หวานจัด สามารถรับประทานได้สำหรับผู้ที่ชอบกล้วยไม่หวานมาก หรือบ่มต่อ 2-3 วันให้สุกนิ่มขึ้น"
    elif 14.0 < brix_value <= 20.0:
        return "กล้วยน้ำว้าสุกพอดี", "😋 กล้วยสุกกำลังดี หวานอร่อย เหมาะสำหรับการรับประทานสด หรือนำไปประกอบอาหารที่ไม่ต้องการความหวานมาก"
    elif 20.0 < brix_value <= 25.0:
        return "กล้วยน้ำว้าสุกงอม", "😉 กล้วยสุกงอม มีความหวานมาก เนื้อนิ่มมาก อาจมีจุดดำบนเปลือก สามารถนำไปแปรรูปเป็นกล้วยเชื่อม กล้วยฉาบ กล้วยตาก หรือทำขนมหวานได้"
    else: # brix_value > 25.0
        return "กล้วยน้ำว้าที่สุกจัดมาก", "👍 กล้วยสุกจัดมาก เนื้อนิ่มเละ หวานจัด เหมาะสำหรับนำไปแปรรูปทันที เช่น ทำกล้วยบวดชี เค้กกล้วยหอม สมูทตี้ หรือแยม"

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
    image_np_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR) # แปลงเป็น BGR สำหรับ OpenCV

    st.image(image_pil, caption='รูปภาพกล้วยน้ำว้าของคุณ', use_column_width=True)

    st.header("2. ผลการประเมิน")
    if st.button('ประเมินสถานะกล้วย'):
        with st.spinner('กำลังวิเคราะห์...'):
            r_avg, g_avg, b_avg = get_avg_color_rgb(image_np_bgr)

            if r_avg is not None:
                # เตรียมข้อมูลสำหรับทำนาย (ต้องเป็นรูปแบบ 2D array)
                input_features = np.array([[r_avg, g_avg, b_avg]])
                predicted_brix = model.predict(input_features)[0]

                # ใช้ฟังก์ชันใหม่ในการประเมินระดับความสุกและคำแนะนำ
                ripeness_status, advice = predict_ripeness(predicted_brix)

                st.success("ประเมินเสร็จสิ้น!")
                st.metric(label="ระดับความหวาน (Brix)", value=f"{predicted_brix:.2f} °Bx")
                st.subheader(f"สถานะกล้วยน้ำว้า: {ripeness_status}")
                st.info(advice) # แสดงคำแนะนำ
                st.caption(f"ค่าสีเฉลี่ย (RGB) ที่ได้: R={r_avg:.0f}, G={g_avg:.0f}, B={b_avg:.0f}")

            else:
                st.warning("ไม่สามารถวิเคราะห์สีจากรูปภาพได้ กรุณาลองใหม่ หรือปรับรูปภาพให้ชัดเจนขึ้น")

st.markdown("---")
st.caption("พัฒนาโดย ครูผู้ช่วยสอนคณิตศาสตร์ โรงเรียนวังโพรงพิทยาคม")
