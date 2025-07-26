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
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # Step 1: กำหนดช่วงสีของกล้วยในรูปแบบ BGR (อาจต้องปรับจูน)
    lower_banana_color_bgr = np.array([0, 80, 80])
    upper_banana_color_bgr = np.array([120, 255, 255])

    # Step 2: สร้าง Mask
    color_mask = cv2.inRange(img_bgr, lower_banana_color_bgr, upper_banana_color_bgr)

    # Step 3: หา Contours
    contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Step 4: หา Contours ที่ใหญ่ที่สุด
    max_area = 0
    largest_contour = None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > max_area:
            max_area = area
            largest_contour = contour

    # Step 5: กำหนดเกณฑ์ขั้นต่ำของพื้นที่พิกเซลที่ยอมรับว่าเป็นกล้วย
    min_banana_pixel_area = 5000 # ค่าเริ่มต้น ลองปรับเพิ่ม/ลด หากพบว่าตรวจจับผิดพลาด

    # Step 6: ตรวจสอบว่าพบกล้วยที่ใหญ่พอหรือไม่
    if largest_contour is None or max_area < min_banana_pixel_area:
        return None, None, None # ไม่พบกล้วย

    # Step 7: สร้าง Mask ใหม่ที่มีเฉพาะวัตถุที่ใหญ่ที่สุด
    final_mask = np.zeros(img_bgr.shape[:2], dtype="uint8")
    cv2.drawContours(final_mask, [largest_contour], -1, 255, -1)

    # Step 8: คำนวณค่าเฉลี่ย BGR
    mean_bgr = cv2.mean(img_bgr, mask=final_mask)[:3]

    avg_red = mean_bgr[2]
    avg_green = mean_bgr[1]
    avg_blue = mean_bgr[0]

    return avg_red, avg_green, avg_blue

# --- ฟังก์ชันประเมินระดับความสุกและให้คำแนะนำจากค่า Brix ---
def predict_ripeness(brix_value):
    ripeness_level_num = 0
    status_desc = ""
    advice_text = ""

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

# --- ฟังก์ชันคำนวณปริมาณน้ำตาลที่ควรได้รับต่อวัน ---
def calculate_daily_sugar_allowance(age, weight, height, gender, is_patient, needs_weight_loss):
    # Mifflin-St Jeor Equation for BMR (Basal Metabolic Rate)
    if gender == "ชาย":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else: # หญิง
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    # Activity factor for TDEE (Total Daily Energy Expenditure) - Simplified
    # Can expand this with more activity levels if needed
    activity_factor = 1.2 # Sedentary (little to no exercise)
    tdee = bmr * activity_factor

    # Convert TDEE to recommended sugar intake (approx.)
    # WHO recommends free sugars not exceeding 10% of total energy intake, ideally < 5%.
    # 1 gram of sugar is approx. 4 kilocalories.
    
    # Let's use 5% of TDEE as a target for sugar for health-conscious/weight loss.
    # And 10% as a general maximum.
    
    # For weight loss or patients, aim for a lower percentage.
    if needs_weight_loss or is_patient:
        target_sugar_calories_percent = 0.05 # 5% of TDEE
    else:
        target_sugar_calories_percent = 0.10 # 10% of TDEE

    daily_sugar_calories = tdee * target_sugar_calories_percent
    daily_sugar_grams = daily_sugar_calories / 4 # 1g sugar = 4 kcal

    return daily_sugar_grams

# --- โค้ด Streamlit App หลัก ---
# กำหนดพาธไปยังโมเดลใน GitHub Repository
model_path = 'banana_brix_model.pkl' 

# โหลดโมเดลที่ฝึกไว้
try:
    model = joblib.load(model_path)
except FileNotFoundError:
    st.error(f"Error: ไม่พบไฟล์โมเดล '{model_path}' กรุณาตรวจสอบว่าไฟล์อยู่ใน GitHub Repository และพาธถูกต้อง")
    st.stop() 

# --- การปรับแต่ง CSS ทั่วไป (สำหรับความสวยงาม) ---
st.markdown("""
<style>
    .reportview-container {
        background: #F0F2F6; /* สีพื้นหลังตาม theme.backgroundColor */
    }
    .main .block-container {
        padding-top: 2rem; /* ลด padding ด้านบน */
        padding-bottom: 2rem; /* ลด padding ด้านล่าง */
        padding-left: 1rem;
        padding-right: 1rem;
    }
    .stButton>button {
        background-color: #FF4B4B; /* สีปุ่มตาม theme.primaryColor */
        color: white;
        border-radius: 5px;
        border: 0px;
        padding: 0.5rem 1rem;
        font-size: 1rem;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        background-color: #FF6363; /* สีปุ่มเมื่อเมาส์ชี้ */
        color: white;
    }
    h1 {
        text-align: center;
        color: #26272E; /* สีตัวอักษรตาม theme.textColor */
        margin-bottom: 0.5rem;
    }
    h2 {
        color: #FF4B4B; /* สีหัวข้อตาม primaryColor */
        text-align: center;
        margin-bottom: 0.5rem;
    }
    h3 {
        color: #26272E; /* สีหัวข้อรองตาม textColor */
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
    .stMetric {
        background-color: #FFFFFF; /* สีพื้นหลัง metric */
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05); /* เพิ่มเงา */
    }
    .stAlert {
        border-radius: 10px;
    }
    .stFileUploader, .stCameraInput {
        border: 1px dashed #FF4B4B; /* เส้นขอบสำหรับอัปโหลด */
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        background-color: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)


# --- ส่วนหัวข้อแอป ---
st.image("https://images.emojiterra.com/google/noto-emoji/unicode-15/color/512px/1f34c.png", width=70) # รูปกล้วยอีโมจิ
st.title("แอปประเมินระดับความหวานและสถานะกล้วยน้ำว้า")
st.markdown("---")


# --- ส่วนหลักของแอป (จัดวางเรียงลงมา) ---
st.header("1. ข้อมูลส่วนตัว (สำหรับคำแนะนำสุขภาพ)")
col_personal_data_1, col_personal_data_2 = st.columns(2)
with col_personal_data_1:
    age = st.number_input("อายุ (ปี)", min_value=1, max_value=120, value=25)
    weight = st.number_input("น้ำหนัก (กิโลกรัม)", min_value=1.0, max_value=200.0, value=60.0, step=0.1)
with col_personal_data_2:
    height = st.number_input("ส่วนสูง (เซนติเมตร)", min_value=10.0, max_value=250.0, value=170.0, step=0.1)
    gender = st.selectbox("เพศ", ["ชาย", "หญิง"])

is_patient = st.checkbox("เป็นผู้ป่วย (เช่น เบาหวาน)", help="ข้อมูลนี้ใช้เพื่อปรับคำแนะนำปริมาณน้ำตาลให้เหมาะสมยิ่งขึ้น")
needs_weight_loss = st.checkbox("ต้องการลดน้ำหนัก / รักษาสุขภาพ", help="ข้อมูลนี้ใช้เพื่อปรับคำแนะนำปริมาณน้ำตาลให้เหมาะสมยิ่งขึ้น")

st.markdown("---")

st.header("2. ถ่ายภาพหรืออัปโหลดรูปกล้วยน้ำว้า")
uploaded_file = st.file_uploader("เลือกรูปภาพกล้วยน้ำว้า", type=["jpg", "jpeg", "png"])
camera_input = st.camera_input("หรือ ถ่ายรูปกล้วยน้ำว้าจากกล้อง")

image_source = None
if uploaded_file is not None:
    image_source = uploaded_file
elif camera_input is not None:
    image_source = camera_input

if image_source is not None:
    image_bytes = image_source.read()
    image_pil = Image.open(io.BytesIO(image_bytes))
    image_np = np.array(image_pil)
    
    st.image(image_pil, caption='รูปภาพกล้วยน้ำว้าของคุณ', use_container_width=True)

    st.header("3. ผลการประเมินและคำแนะนำสุขภาพ") # ปรับเป็นหัวข้อที่ 3
    if st.button('ประเมินสถานะกล้วยและรับคำแนะนำ', use_container_width=True): # ปรับข้อความปุ่ม
        with st.spinner('กำลังวิเคราะห์...'):
            ripeness_result = get_avg_color_rgb(image_np) 

            if ripeness_result[0] is None:
                st.warning("ไม่พบกล้วยในภาพ หรือภาพไม่ชัดเจน กรุณาลองถ่ายภาพใหม่ให้เห็นกล้วยชัดเจน")
            else:
                r_avg, g_avg, b_avg = ripeness_result

                input_features = np.array([[r_avg, g_avg, b_avg]])
                predicted_brix = model.predict(input_features)[0]

                ripeness_level_num, ripeness_status, advice, percentage_ripeness = predict_ripeness(predicted_brix)

                # --- ส่วนแสดงผลลัพธ์จากกล้วย ---
                st.success("ผลการประเมินกล้วยเสร็จสิ้น!")
                st.metric(label="ระดับความหวาน (Brix)", value=f"{predicted_brix:.2f} °Bx")
                st.metric(label="ปริมาณน้ำตาล (กรัม/100กรัม)", value=f"{predicted_brix:.2f} g") # Brix ประมาณเท่ากับกรัมน้ำตาล/100กรัม
                st.metric(label="ร้อยละความสุก", value=f"{percentage_ripeness:.1f}%")
                st.subheader(f"สถานะกล้วยน้ำว้า: {ripeness_status}")
                st.subheader(f"ระดับความสุก: {ripeness_level_num} (จาก 7 ระดับ)")
                st.info(advice) 
                st.caption(f"ค่าสีเฉลี่ย (RGB) ที่ได้: R={r_avg:.0f}, G={g_avg:.0f}, B={b_avg:.0f}")

                st.markdown("---")
                
                # --- ส่วนคำแนะนำสุขภาพส่วนบุคคล ---
                st.subheader("คำแนะนำปริมาณน้ำตาลสำหรับคุณ")
                daily_sugar_grams_allowance = calculate_daily_sugar_allowance(age, weight, height, gender, is_patient, needs_weight_loss)
                
                st.info(f"ตามข้อมูลที่คุณให้ ปริมาณน้ำตาลที่แนะนำต่อวันของคุณคือประมาณ **{daily_sugar_grams_allowance:.1f} กรัม**")
                st.write(f"ดังนั้น กล้วยน้ำว้า 100 กรัมนี้ (ประมาณ 1 ผลเล็กถึงกลาง) มีปริมาณน้ำตาลประมาณ **{predicted_brix:.1f} กรัม** ซึ่งคิดเป็น **{((predicted_brix / daily_sugar_grams_allowance) * 100):.1f}%** ของปริมาณที่แนะนำต่อวันของคุณ")
                
                st.warning("**ข้อจำกัด:** ข้อมูลนี้เป็นการประมาณการเบื้องต้น ไม่ใช่คำแนะนำทางการแพทย์ ควรปรึกษาแพทย์หรือนักโภชนาการสำหรับคำแนะนำเฉพาะบุคคล.")

else:
    st.info("กรุณาป้อนข้อมูลส่วนตัวด้านบน, อัปโหลดรูปกล้วย หรือถ่ายภาพกล้วยเพื่อเริ่มการประเมินและรับคำแนะนำสุขภาพ")

st.markdown("---")
st.markdown("พัฒนาโดย นางสาวนรินทร์ธร พิมสา, นางสาวนิชาภา ศรีละวัลย์ และนางสาวรัตนาวดี สว่างศรี<br>อาจารย์ที่ปรึกษา: นายอชิตพล บุณรัตน์, นางสาวปทุมวดี วงษ์สุธรรม และนางสาวสมใจ จันทรงกรด<br>โรงเรียนวังโพรงพิทยาคม สำนักงานเขตพื้นที่การศึกษามัธยมศึกษาพิษณุโลก อุตรดิตถ์", unsafe_allow_html=True)
