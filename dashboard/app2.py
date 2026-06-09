import streamlit as st
import pandas as pd
import requests
import time
import os

from dotenv import load_dotenv
from catboost import CatBoostRegressor

# -------------------------------
# LOAD ENV VARIABLES
# -------------------------------
load_dotenv()

THINGSPEAK_CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")
THINGSPEAK_READ_KEY = os.getenv("THINGSPEAK_READ_KEY")

VC_API_KEY = os.getenv("VC_API_KEY")
LAT_LONG = os.getenv("LAT_LONG")

# -------------------------------
# SAFE FUNCTION
# -------------------------------
def safe(val):
    try:
        return float(val)
    except:
        return 0.0

# -------------------------------
# UI DESIGN
# -------------------------------
st.set_page_config(page_title="🌾 Smart Farm Hub", layout="wide")

st.markdown("""
<style>
.main {
    background: linear-gradient(135deg, #e3f2fd, #ffffff);
}

.stMetric {
    background: white;
    padding: 18px;
    border-radius: 15px;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.1);
    text-align: center;
}

h1, h2, h3 {
    color: #2e7d32;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------
# TITLE
# -------------------------------
st.title("🌾 AquaSense")
st.caption("ESP32 + AI + Weather API")

# -------------------------------
# FETCH ESP32 DATA
# -------------------------------
def fetch_physical():

    url = (
        f"https://api.thingspeak.com/channels/"
        f"{THINGSPEAK_CHANNEL_ID}/feeds.json"
        f"?api_key={THINGSPEAK_READ_KEY}&results=1"
    )

    try:

        r = requests.get(url).json()

        if 'feeds' in r and len(r['feeds']) > 0:

            last = r['feeds'][0]

            return {

                "temp": safe(last.get('field1')),

                "hum": safe(last.get('field2')),

                "soil": safe(last.get('field3')),

                "rain": safe(last.get('field4')),

                "ts": last.get('created_at')

            }

    except Exception as e:

        st.error(f"ThingSpeak Error: {e}")

    return None

# -------------------------------
# FETCH WEATHER API
# -------------------------------
def fetch_weather():

    url = (
        f"https://weather.visualcrossing.com/"
        f"VisualCrossingWebServices/rest/services/"
        f"timeline/{LAT_LONG}/today"
        f"?unitGroup=metric"
        f"&key={VC_API_KEY}"
        f"&contentType=json"
    )

    try:

        r = requests.get(url).json()

        curr = r.get('currentConditions', {})

        return {

            "temp": safe(curr.get('temp')),

            "humidity": safe(curr.get('humidity')),

            "precip": safe(curr.get('precip')),

            "dew": safe(curr.get('dew')),

            "solarradiation": safe(curr.get('solarradiation')),

            "solarenergy": safe(curr.get('solarenergy')),

            "windspeed": safe(curr.get('windspeed'))

        }

    except Exception as e:

        st.error(f"Weather API Error: {e}")

        return None

# -------------------------------
# LOAD MODEL
# -------------------------------
@st.cache_resource
def load_model():

    model = CatBoostRegressor()

    model.load_model("multi_output_agronomist(1).bin")

    return model

model = load_model()

# -------------------------------
# MAIN
# -------------------------------
phys = fetch_physical()

weather = fetch_weather()

ai_soil = None

if phys and weather:

    col1, col2, col3 = st.columns(3)

    # -------------------------------
    # ESP32 DATA
    # -------------------------------
    with col1:

        st.subheader("📡 Physical Station")

        st.metric(
            "🌡 Temp",
            f"{phys['temp']:.1f} °C"
        )

        st.metric(
            "💦 Humidity",
            f"{phys['hum']:.1f}%"
        )

        st.metric(
            "💧 Soil",
            f"{phys['soil']:.1f}%"
        )

        st.progress(int(phys['soil']))

        st.metric(
            "🌧 Rain (ADC)",
            f"{phys['rain']}"
        )

        st.caption(f"Last Sync: {phys['ts']}")

    # -------------------------------
    # WEATHER DATA
    # -------------------------------
    with col2:

        st.subheader("☁️ Field Data")

        temp = weather['temp']

        hum = weather['humidity']

        rain = weather['precip']

        st.metric(
            "Temp",
            f"{temp:.1f} °C",
            delta=f"{temp - phys['temp']:.1f}"
        )

        st.metric(
            "Humidity",
            f"{hum}%"
        )

        st.metric(
            "Rainfall",
            f"{rain} mm"
        )

    # -------------------------------
    # AI MODEL
    # -------------------------------
    with col3:

        st.subheader("🤖 AI Prediction")

        try:

            input_df = pd.DataFrame([{

                "field1": phys['temp'],

                "field2": phys['hum'],

                "field3": weather['precip'],

                "field4": weather['dew'],

                "field5": weather['solarradiation'],

                "field6": weather['solarenergy'],

                "field7": weather['windspeed'],

                "field8": phys['soil']

            }])

            prediction = model.predict(input_df)

            if len(prediction.shape) > 1:

                ai_soil = float(prediction[0][0])

            else:

                ai_soil = float(prediction[0])

            st.metric(
                "🌱 Predicted Soil",
                f"{ai_soil:.2f}%"
            )

            # -------------------------------
            # XAI
            # -------------------------------
            st.markdown("### 🔍 Why?")

            if phys['soil'] < 30:
                st.write("👉 Soil dry")

            if weather['temp'] > 30:
                st.write("👉 High temperature")

            if weather['humidity'] < 50:
                st.write("👉 Low humidity")

            if weather['precip'] > 0:
                st.write("👉 Rainfall present")

        except Exception as e:

            st.error(f"Model Error: {e}")

            ai_soil = None

    # -------------------------------
    # IRRIGATION LOGIC
    # -------------------------------
    st.divider()

    st.subheader("💧 Irrigation Decision")

    rain_detected = phys['rain'] < 4095

    if rain_detected:

        st.success("🌧 Soil Moisture Detected → Irrigation OFF")

    elif ai_soil is not None:

        if phys['soil'] < 30 or ai_soil < 30:

            st.error("🚨 Irrigation ON (Soil Dry)")

        else:

            st.success("✅ Soil Healthy → No Irrigation")

    else:

        st.warning("⚠ Waiting for prediction...")

    # -------------------------------
    # CHART
    # -------------------------------
    st.markdown("### 📊 Soil Comparison")

    chart_data = pd.DataFrame({

        "Type": ["Physical", "AI"],

        "Moisture": [

            phys['soil'],

            ai_soil if ai_soil else 0

        ]

    })

    st.bar_chart(chart_data.set_index("Type"))

    # -------------------------------
    # WATER SAVING
    # -------------------------------
    st.markdown("### 🌍 Sustainability")

    if ai_soil is not None:

        water_saved = 40 if phys['soil'] >= 30 else 0

        st.metric(
            "💧 Water Saved",
            f"{water_saved}%"
        )

else:

    st.warning("🔄 Waiting for data...")

# -------------------------------
# FOOTER
# -------------------------------
st.markdown("---")

st.markdown("Smart Irrigation System 🌱")

# -------------------------------
# AUTO REFRESH
# -------------------------------
time.sleep(20)

st.rerun()