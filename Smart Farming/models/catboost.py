
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.model_selection import train_test_split

# Load dataset
data = pd.read_csv("Farming_final.csv")

# Features and target
X = data.drop("target", axis=1)
y = data["target"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = CatBoostRegressor(verbose=0)
model.fit(X_train, y_train)

# Save model
model.save_model("multi_output_agronomist.bin")

print("Model and code saved successfully")
