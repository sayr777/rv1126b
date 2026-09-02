# Даташиты и справочные материалы

## SoC — Rockchip RV1126B

| Документ                           | Ссылка                                                                                  |
|------------------------------------|-----------------------------------------------------------------------------------------|
| RV1126B Brief Datasheet v1.0       | https://www.rock-chips.com/uploads/pdf/2026.2.11/192/RV1126B%20brief%20datasheet%20V1.0%2020241219.pdf |
| RV1126B vs RV1126 сравнение        | https://rockchips.net/rv1126b-vs-rv1126-technical-comparison/                           |
| RKNN-Toolkit2 GitHub               | https://github.com/airockchip/rknn-toolkit2                                             |
| RKNN Model Zoo                     | https://github.com/airockchip/rknn_model_zoo                                            |
| Luckfox Aura Wiki + RKNN примеры   | https://wiki.luckfox.com/luckfox-Aura/RKNN-Toolkit2/                                   |

**Ключевые характеристики:**

| Параметр     | Значение                                        |
|--------------|-------------------------------------------------|
| CPU          | 4× Cortex-A53 @ 1.6 GHz                        |
| NPU          | 3 TOPS INT8 (RKNPU2)                            |
| Точность NPU | INT4 / INT8 / INT16 / FP16 / BF16 / TF32       |
| ISP          | 12MP AI-ISP, HDR, 3A                           |
| Video encode | H.265 4K@45fps, H.264 4K@30fps                 |
| Ethernet     | Gigabit                                         |
| USB          | USB 3.0                                         |
| MIPI CSI-2   | 2 входа (2 камеры одновременно)                 |
| RAM макс.    | 4 GB LPDDR4/LPDDR5                             |

## Камера фронтальная — Sony IMX335

| Документ               | Ссылка                                               |
|------------------------|------------------------------------------------------|
| IMX335 Product Brief   | https://www.sony-semicon.com/products/IS/imx335.html |

| Параметр       | Значение          |
|----------------|-------------------|
| Разрешение     | 2592×1944 (5 МП)  |
| Интерфейс      | MIPI CSI-2, 4 Lane |
| FPS @ 1080p    | 60 fps            |
| Чувствит.      | 0.005 Lux (ч/б)   |
| HDR            | 2-frame HDR       |

## Камера кабинная — OmniVision OV4689

| Параметр       | Значение         |
|----------------|------------------|
| Разрешение     | 2688×1520 (4 МП) |
| Интерфейс      | MIPI CSI-2, 2 Lane |
| FPS @ 1080p    | 45 fps           |
| Чувствит.      | 0.002 Lux (StarLight) |
| Рабочий диап.  | -30°C … +70°C    |

## RKNN инструменты

| Инструмент         | Назначение                                    |
|--------------------|-----------------------------------------------|
| rknn-toolkit2      | Конвертация ONNX/TF/PT → RKNN (запуск на ПК) |
| librknnrt          | Runtime инференса (запуск на RV1126B)         |
| rknn_model_zoo     | Готовые модели: YOLOv8, LPRNet, MobileNetV2  |
| Ultralytics RKNN   | YOLOv8 → RKNN экспорт через Ultralytics CLI  |
