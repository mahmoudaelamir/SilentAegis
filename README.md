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
