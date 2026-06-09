import streamlit as st
import pandas as pd
import requests
import time
import os

from dotenv import load_dotenv
from catboost import CatBoostRegressor

# -------------------------------
# LOAD .ENV VARIABLES
# -------------------------------
load_dotenv()

THINGSPEAK_CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")
THINGSPEAK_READ_KEY = os.getenv("THINGSPEAK_READ_KEY")

VC_API_KEY = os.getenv("VC_API_KEY")
LAT_LONG = os.getenv("LAT_LONG")

# -------------------------------
# DEBUG CHECK
# -------------------------------


# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="🌾 Smart Farm Hub",
    layout="wide"
)

# -------------------------------
# CUSTOM UI
# -------------------------------
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
# FETCH THINGSPEAK DATA
# -------------------------------
def fetch_physical():

    url = (
        f"https://api.thingspeak.com/channels/"
        f"{THINGSPEAK_CHANNEL_ID}/feeds.json"
        f"?api_key={THINGSPEAK_READ_KEY}&results=1"
    )

    try:

        response = requests.get(url)

        data = response.json()

        if 'feeds' in data and len(data['feeds']) > 0:

            last = data['feeds'][0]

            return {

                "temp": float(last.get('field1') or 0),

                "hum": float(last.get('field2') or 0),

                "soil": float(last.get('field3') or 0),

                "rain": float(last.get('field4') or 0),

                "ts": last.get('created_at')

            }

    except Exception as e:

        st.error(f"ThingSpeak Error: {e}")

    return None

# -------------------------------
# FETCH WEATHER API DATA
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

        response = requests.get(url)

        data = response.json()

        current = data.get('currentConditions', {})

        return {

            "temp": current.get('temp'),

            "humidity": current.get('humidity'),

            "precip": current.get('precip'),

            "dew": current.get('dew'),

            "solarradiation": current.get('solarradiation'),

            "solarenergy": current.get('solarenergy'),

            "windspeed50": current.get('windspeed')

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

    model.load_model("multi_output_agronomist.bin")

    return model

model = load_model()

# -------------------------------
# FETCH DATA
# -------------------------------
physical_data = fetch_physical()

weather_data = fetch_weather()

ai_soil = None

# -------------------------------
# MAIN DASHBOARD
# -------------------------------
if physical_data and weather_data:

    col1, col2, col3 = st.columns(3)

    # -------------------------------
    # PHYSICAL SENSOR DATA
    # -------------------------------
    with col1:

        st.subheader("📡 Physical Station")

        st.metric(
            "🌡 Temperature",
            f"{physical_data['temp']:.1f} °C"
        )

        st.metric(
            "💦 Humidity",
            f"{physical_data['hum']:.1f}%"
        )

        st.metric(
            "💧 Soil Moisture",
            f"{physical_data['soil']:.1f}%"
        )

        st.progress(int(physical_data['soil']))

        st.metric(
            "🌧 Rain Sensor",
            f"{physical_data['rain']}"
        )

        st.caption(f"Last Sync: {physical_data['ts']}")

    # -------------------------------
    # WEATHER API DATA
    # -------------------------------
    with col2:

        st.subheader("☁️ Weather API")

        weather_temp = weather_data['temp'] or 0

        weather_humidity = weather_data['humidity'] or 0

        weather_rain = weather_data['precip'] or 0

        st.metric(
            "Temperature",
            f"{weather_temp:.1f} °C",
            delta=f"{weather_temp - physical_data['temp']:.1f}"
        )

        st.metric(
            "Humidity",
            f"{weather_humidity}%"
        )

        st.metric(
            "Rainfall",
            f"{weather_rain} mm"
        )

    # -------------------------------
    # AI PREDICTION
    # -------------------------------
    with col3:

        st.subheader("🤖 AI Prediction")

        try:

            input_df = pd.DataFrame([{

                "temp": physical_data['temp'],

                "humidity": physical_data['hum'],

                "precip": weather_data['precip'] or 0,

                "dew": weather_data['dew'] or 0,

                "solarradiation": weather_data['solarradiation'] or 0,

                "solarenergy": weather_data['solarenergy'] or 0,

                "windspeed50": weather_data['windspeed50'] or 0,

                "soilmoisture10": physical_data['soil']

            }])

            prediction = model.predict(input_df)

            if len(prediction.shape) > 1:

                ai_soil = float(prediction[0][0])

            else:

                ai_soil = float(prediction[0])

            st.metric(
                "🌱 Predicted Soil Moisture",
                f"{ai_soil:.2f}%"
            )

            st.markdown("### 🔍 Why Prediction?")

            if physical_data['soil'] < 30:
                st.write("👉 Soil moisture is low")

            if (weather_data['temp'] or 0) > 30:
                st.write("👉 High environmental temperature")

            if (weather_data['humidity'] or 0) < 50:
                st.write("👉 Low atmospheric humidity")

            if (weather_data['precip'] or 0) > 0:
                st.write("👉 Rainfall detected")

        except Exception as e:

            st.error(f"Model Error: {e}")

            ai_soil = None

    # -------------------------------
    # IRRIGATION DECISION
    # -------------------------------
    st.divider()

    st.subheader("💧 Smart Irrigation Decision")

    rain_detected = physical_data['rain'] < 4095

    if rain_detected:

        st.success("🌧 Rainfall Detected → Irrigation OFF")

    elif ai_soil is not None:

        if physical_data['soil'] < 30 or ai_soil < 30:

            st.error("🚨 Irrigation ON → Soil Dry")

        else:

            st.success("✅ Soil Moisture Normal → Irrigation OFF")

    else:

        st.warning("⚠ Waiting for AI prediction...")

    # -------------------------------
    # CHART
    # -------------------------------
    st.markdown("### 📊 Soil Moisture Comparison")

    chart_data = pd.DataFrame({

        "Type": ["Physical Sensor", "AI Prediction"],

        "Moisture": [

            physical_data['soil'],

            ai_soil if ai_soil else 0

        ]

    })

    st.bar_chart(chart_data.set_index("Type"))

    # -------------------------------
    # WATER SAVING
    # -------------------------------
    st.markdown("### 🌍 Sustainability Impact")

    if ai_soil is not None:

        water_saved = 40 if physical_data['soil'] >= 30 else 0

        st.metric(
            "💧 Estimated Water Saved",
            f"{water_saved}%"
        )

else:

    st.warning("🔄 Waiting for sensor data...")

# -------------------------------
# FOOTER
# -------------------------------
st.markdown("---")

st.markdown("### 🌱 AI-Powered Smart Irrigation System")

# -------------------------------
# AUTO REFRESH
# -------------------------------
time.sleep(20)

st.rerun()