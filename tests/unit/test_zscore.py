import numpy as np
import pytest


def calculate_z_score(values: list[float], new_val: float) -> float:
    arr = np.array(values, dtype=np.float64)
    mean = np.mean(arr)
    std = np.std(arr, ddof=1)
    if std < 1e-6:
        return 0.0
    return float((new_val - mean) / std)


def test_nominal_reading_within_three_sigma():
    baseline = [70.0 + float(i % 3) for i in range(50)]
    z = calculate_z_score(baseline, 71.0)
    assert abs(z) < 3.0, "Normal reading should not breach 3-sigma"


def test_thermal_anomaly_exceeds_three_sigma():
    baseline = [70.0 + float(i % 2) for i in range(50)]
    z = calculate_z_score(baseline, 98.0)  # Extreme temperature anomaly
    assert z > 3.0, "Thermal excursion must yield Z-score > 3.0"