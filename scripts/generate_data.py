"""Generate a synthetic cardiovascular risk dataset.

Outputs:
  data/raw/patients_raw.csv    - one row per patient, numeric/categorical fields
  data/clean/patients.csv      - adds bands, risk score and per-organ status
  data/clean/dim_organ.csv     - organ selector table (disconnected in Power BI)
  data/clean/dim_status.csv    - status toggle table (disconnected in Power BI)

Usage:  python scripts/generate_data.py [--n 1200] [--seed 42]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def generate(n, seed):
    rng = np.random.default_rng(seed)

    age = np.clip(rng.normal(52, 14, n), 20, 90).round().astype(int)
    gender = rng.choice(["Male", "Female"], n, p=[0.52, 0.48])
    bmi = np.clip(rng.normal(27.5, 5.2, n), 16, 48).round(1)

    # Smoking: older people are more likely to be Former/Current smokers
    p_smoke = np.clip((age - 20) / 120 + 0.12, 0.1, 0.6)
    u = rng.random(n)
    smoking = np.where(u < p_smoke * 0.55, "Current", np.where(u < p_smoke, "Former", "Never"))
    years = np.where(smoking == "Never", 0, np.minimum(age - 16, rng.gamma(3.0, 6.0, n))).round().astype(int)
    years = np.clip(years, 0, None)
    cigs = np.where(smoking == "Never", 0,
                    np.where(smoking == "Current", rng.integers(3, 31, n), rng.integers(2, 18, n)))

    alcohol = np.clip(rng.gamma(1.6, 4.0, n), 0, 45).round(1)
    activity = rng.choice(["Low", "Moderate", "High"], n, p=[0.38, 0.40, 0.22])
    diet = rng.choice(["Poor", "Average", "Good"], n, p=[0.30, 0.45, 0.25])

    sys_bp = np.clip(rng.normal(112 + 0.38 * (age - 20) + 0.9 * (bmi - 25)
                                + 6 * (smoking == "Current"), 11, n), 90, 210).round().astype(int)
    chol = np.clip(rng.normal(170 + 0.6 * (age - 20) + 1.6 * (bmi - 25) + 8 * (diet == "Poor")
                              - 6 * (diet == "Good"), 28, n), 120, 340).round().astype(int)
    diabetes = rng.random(n) < sigmoid(-4.2 + 0.04 * (age - 20) + 0.07 * (bmi - 25))
    family = rng.random(n) < 0.22

    hypertension = sys_bp >= 140
    pack_years = years * cigs / 20

    base = (-4.4 + 0.045 * age + 0.012 * (chol - 180) + 0.018 * (sys_bp - 120)
            + 0.05 * (bmi - 25) + 0.07 * pack_years + 0.35 * diabetes + 0.5 * family
            + 0.15 * (activity == "Low") - 0.2 * (activity == "High")
            + 0.25 * (diet == "Poor") - 0.2 * (diet == "Good")
            + 0.015 * np.maximum(alcohol - 14, 0) + 0.25 * (gender == "Male"))

    heart_attack = rng.random(n) < sigmoid(base + 0.2)
    stroke = rng.random(n) < sigmoid(base - 0.3 + 0.015 * (sys_bp - 120) + 0.3 * hypertension)
    kidney = rng.random(n) < sigmoid(base - 0.6 + 0.9 * diabetes + 0.4 * hypertension)

    df = pd.DataFrame({
        "PatientID": [f"P{i:04d}" for i in range(1, n + 1)],
        "Age": age, "Gender": gender, "BMI": bmi,
        "Smoking_Status": smoking, "Smoking_Years": years, "Cigarettes_Per_Day": cigs,
        "Alcohol_Units_Week": alcohol, "Physical_Activity": activity, "Diet_Quality": diet,
        "Systolic_BP": sys_bp, "Cholesterol": chol,
        "Diabetes": np.where(diabetes, "Yes", "No"),
        "Family_History": np.where(family, "Yes", "No"),
        "Hypertension": np.where(hypertension, "Yes", "No"),
        "Heart_Attack": heart_attack.astype(int),
        "Stroke": stroke.astype(int),
        "Kidney_Disease": kidney.astype(int),
    })
    return df


def clean(df):
    df = df.copy()
    df["Age_Group"] = pd.cut(df["Age"], [0, 29, 39, 49, 59, 69, 120],
                             labels=["<30", "30-39", "40-49", "50-59", "60-69", "70+"]).astype(str)
    df["BMI_Category"] = pd.cut(df["BMI"], [0, 18.5, 25, 30, 100],
                                labels=["Underweight", "Normal", "Overweight", "Obese"]).astype(str)
    df["Cholesterol_Level"] = pd.cut(df["Cholesterol"], [0, 200, 240, 1000],
                                     labels=["Normal", "Borderline", "High"]).astype(str)
    df["Daily_Intake_Band"] = pd.cut(df["Cigarettes_Per_Day"], [-1, 0, 10, 20, 100],
                                     labels=["None", "1-10", "11-20", "20+"]).astype(str)
    df["Smoking_Years_Band"] = pd.cut(df["Smoking_Years"], [-1, 0, 10, 20, 30, 100],
                                      labels=["None", "1-10", "11-20", "21-30", "30+"]).astype(str)

    # Overall risk score 0-100: weighted conditions + risk factors
    score = (df["Heart_Attack"] * 25 + df["Stroke"] * 25 + df["Kidney_Disease"] * 15
             + (df["Age"] - 20).clip(0) / 70 * 10
             + (df["Cholesterol"] - 150).clip(0) / 150 * 8
             + (df["Systolic_BP"] - 110).clip(0) / 90 * 8
             + (df["Smoking_Status"] == "Current") * 6)
    df["Risk_Score"] = score.clip(0, 100).round(1)
    df["Risk_Band"] = pd.cut(df["Risk_Score"], [-1, 20, 40, 101], labels=["Low", "Medium", "High"]).astype(str)

    # Per-organ status drives the organ selector + Healthy / At Risk toggle
    for col, flag in [("Heart_Status", "Heart_Attack"), ("Brain_Status", "Stroke"), ("Kidney_Status", "Kidney_Disease")]:
        df[col] = np.where(df[flag] == 1, "At Risk", "Healthy")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    raw = generate(a.n, a.seed)
    (ROOT / "data/raw").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/clean").mkdir(parents=True, exist_ok=True)
    raw.to_csv(ROOT / "data/raw/patients_raw.csv", index=False)

    df = clean(raw)
    df.to_csv(ROOT / "data/clean/patients.csv", index=False)
    pd.DataFrame({"Organ": ["Heart", "Brain", "Kidney"], "Sort": [1, 2, 3]}).to_csv(ROOT / "data/clean/dim_organ.csv", index=False)
    pd.DataFrame({"Status": ["Healthy", "At Risk"], "Sort": [1, 2]}).to_csv(ROOT / "data/clean/dim_status.csv", index=False)

    print(f"{len(df)} patients written to data/clean/patients.csv")
    print(df[["Heart_Attack", "Stroke", "Kidney_Disease"]].mean().round(3).to_string())
    print(df["Risk_Band"].value_counts().to_string())


if __name__ == "__main__":
    main()
