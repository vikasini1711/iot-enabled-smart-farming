#include <WiFi.h>
#include "ThingSpeak.h"
#include "DHT.h"

// 1. Network and ThingSpeak Credentials
const char* ssid = "OnePlus Nord CE5 w5ya";
const char* password = "yohipara";
unsigned long myChannelNumber = 3326078; 
const char* myWriteAPIKey = "6YZ5XDDS6P7TXPTD";

// 2. Hardware Pin Definitions (Non-I2C) [Ref 278]
#define DHTPIN 4          // DHT22 Signal (Confirmed working in logs)
#define DHTTYPE DHT22
#define SOIL_PIN 34       // Capacitive Soil Moisture (f6)
#define RAIN_PIN 35       // Rain Sensor (f3)

// 3. Statistical Tracking Variables [Ref 1]
float tMax = -100.0;
float tMin = 100.0;

DHT dht(DHTPIN, DHTTYPE);
WiFiClient client;

void setup() {
  Serial.begin(115200);
  delay(2000); 
  dht.begin();
  
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected.");
  ThingSpeak.begin(client);
}

void loop() {
  // A. Physical Sensor Readings (Ground-Truth) [Ref 287]
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  int rawSoil = analogRead(SOIL_PIN);
  int rawRain = analogRead(RAIN_PIN);

  if (isnan(temp) || isnan(hum)) {
    Serial.println("DHT22 Error: Check Pin 4 and Power Rail.");
    delay(5000);
    return; 
  }

  // B. Derived Software Logic [Ref 1, 286]
  // Calibration for soil at 15cm depth [Ref 305]
  float soilPercent = constrain(map(rawSoil, 3200, 1500, 0, 100), 0, 100);

  // Derived: Heat Index (feelslike)
  float feelsLike = dht.computeHeatIndex(temp, hum, false); 
  
  // Derived: Simple Dew Point estimate (dew)
  float dewPoint = temp - ((100 - hum) / 5.0); 

  // Statistics: Tracking Daily Max/Min
  if (temp > tMax) tMax = temp;
  if (temp < tMin) tMin = temp;

  // C. Push Data to 8 ThingSpeak Fields [Ref 303-305]
  ThingSpeak.setField(1, temp);         // f1: Temperature
  ThingSpeak.setField(2, hum);          // f2: Humidity
  ThingSpeak.setField(3, soilPercent);  // f6: Soil Moisture (15cm)
  ThingSpeak.setField(4, (float)rawRain); // f3: Rain ADC
  ThingSpeak.setField(5, feelsLike);    // feelslike
  ThingSpeak.setField(6, dewPoint);     // dew
  ThingSpeak.setField(7, tMax);         // tempmax
  ThingSpeak.setField(8, tMin);         // tempmin

  int x = ThingSpeak.writeFields(myChannelNumber, myWriteAPIKey);

  if(x == 200) {
    Serial.print("T | Temp: "); Serial.print(temp);
    Serial.print("H | Humid: "); Serial.print(hum);
    Serial.print("C | Soil: "); Serial.print(soilPercent);
    Serial.print("R | Rain: "); Serial.print(rawRain);
    Serial.println("% | 8-Field Sync Successful.");
  } else {
    Serial.println("Cloud Error: " + String(x));
  }

  delay(20000); // 20-second update cycle
}
