import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib as jb

ds = pd.read_csv('model/Crop_recommendation.csv')
print(ds['label'].unique())

ds.drop(columns=['ph'], inplace=True)
ds.drop(columns=['temperature'], inplace=True)

X = ds[['N', 'P', 'K', 'humidity', 'rainfall']]
y = ds['label']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Random Forest
rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X_train, y_train)
y_pred = rf.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
# print("Random Forest Model Accuracy:", round(accuracy * 100, 2), "%")
# print("\nClassification Report:\n", classification_report(y_test, y_pred))

jb.dump(rf, 'model/final_model.pkl')
print("Model saved as model/final_model.pkl")