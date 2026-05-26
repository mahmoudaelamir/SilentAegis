# SilentAegis 🎯
## 6G ISAC Passive Radar: Physics-Informed Neural Network + UKF + Real Hardware Validation

[![IEEE](https://img.shields.io/badge/IEEE-Access-blue)](https://ieeeaccess.ieee.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red)](https://pytorch.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📋 Overview

**SilentAegis** is a real-time passive radar pipeline for 6G Integrated Sensing and Communication (ISAC) that combines:

| Component | Description |
|---|---|
| **① ISAC** | Bistatic 6G OFDM channel exploitation |
| **② PINN** | Physics-Informed Neural Network localizer |
| **③ UKF** | Unscented Kalman Filter tracker |
| **④ NLOS** | Multi-path exploitation as Virtual Anchors |

---

## 🏆 Results

### Simulation (28 GHz Urban Canyon)
| Method | RMSE | P95 | Inference |
|---|---|---|---|
| UKF-only (baseline) | 80.9 m | 137.6 m | — |
| PINN-only | 5.27 m | 8.45 m | 0.0016 ms |
| **PINN+UKF (ours)** | **4.40 m** | **6.97 m** | **0.0016 ms** |

### Real Hardware Validation (Oryx Dataset, 3.75 GHz)
| Model | Features | RMSE | P95 |
|---|---|---|---|
| Model 1 — 5G (LOS) | 14 | 0.115 m | 0.168 m |
| **Model 2 — 6G ISAC (LOS+NLOS)** | **135** | **0.030 m** | **0.045 m** |

**Key findings:**
- 🎯 Physics loss reduces RMSE by **76.7%** on real hardware
- 📡 NLOS features provide **3.8x** improvement over LOS-only
- ⚡ Ablation: **304x** gain from Baseline → Full 6G ISAC
- 🔧 ONNX export: **16.4 KB** | **0.088 ms/sample**

---

## 🗂️ Repository Structure
SilentAegis/
├── models/
│   ├── SilentAegis_5G_Final.onnx   # 5G model (14 features)
│   └── SilentAegis_6G_Final.onnx   # 6G ISAC model (135 features)
├── notebooks/
│   └── SilentAegis_Training.ipynb  # Full training pipeline
├── paper/
│   └── IEEE_SilentAegis_Final.docx # IEEE paper
├── figures/
│   ├── SilentAegis_GraphicalAbstract.png
│   └── SilentAegis_Ablation.png
└── README.md
---

## 🚀 Quick Start

```python
import onnxruntime as ort
import numpy as np

# Load 6G ISAC model
sess = ort.InferenceSession('models/SilentAegis_6G_Final.onnx')

# Input: 135 features (LOS + NLOS from 7 TX-RX links)
features = np.random.randn(1, 135).astype(np.float32)

# Inference
position_xy = sess.run(None, {'features': features})[0]
print(f"Position: X={position_xy[0,0]:.3f}m, Y={position_xy[0,1]:.3f}m")
```

---

## 📡 Dataset

Real hardware validation uses the **Oryx ISAC Dataset** (TU Ilmenau, 2025):
- **FC:** 3.75 GHz | **BW:** 48 MHz | **Δr:** 3.13 m
- **Hardware:** USRP X310 SDR
- **Target:** VTOL UAV | **Samples:** 625 synchronized
- **DOI:** [10.71758/refodat.60](https://doi.org/10.71758/refodat.60)

---

## 🔬 Pipeline
6G ISAC Signal
↓
Hybrid Ray-Tracing Engine (1100x faster than Sionna RT)
↓
Sparse Sionna RT Calibration (N=10, -89% delay error)
↓
PINN Localizer (Physics Loss + NLOS features)
↓
UKF Tracker (simulation) / Direct PINN (real HW)
↓
UAV Position Output
---

## 📊 Ablation Study

| Config | Features | RMSE | Gain |
|---|---|---|---|
| ① Baseline (R_sum only) | 4 | 1.722 m | 1.0x |
| ② + ISAC (SNR+Doppler) | 12 | 0.032 m | 53x |
| ③ + NLOS (4RX) | 76 | 0.006 m | **304x** |
| ④ Full 6G (7 links) | 135 | 0.006 m | 293x |

---

## 📝 Citation

```bibtex
@article{elamir2025silentaegis,
  title={SilentAegis: Hybrid Ray-Tracing Passive Radar for 6G ISAC:
         Physics-Informed Neural Network with Sparse Sionna Calibration
         and Unscented Kalman Filter Tracking},
  author={ELAMiR, Mahmoud A.},
  journal={IEEE Access},
  year={2025},
  institution={Faculty of Engineering, Mansoura University}
}
```

---

## 👥 Authors

**Mahmoud A. ELAMiR**
Faculty of Engineering, Mansoura University, Egypt

**Supervisors:**
- Dr. Seham Abd-Elsamee
- Dr. Doaa A. Altantawy

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.
