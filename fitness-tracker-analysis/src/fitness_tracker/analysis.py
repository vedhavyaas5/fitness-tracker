from typing import Optional


def bmi(weight_kg: float, height_cm: float) -> Optional[float]:
    try:
        h_m = height_cm / 100.0
        return round(weight_kg / (h_m * h_m), 2)
    except Exception:
        return None


def bmr_mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, sex: str) -> Optional[float]:
    sex = (sex or "").lower()
    if sex not in ("male", "female"):
        return None
    s = 5 if sex == "male" else -161
    return round(10 * weight_kg + 6.25 * height_cm - 5 * age + s, 2)
