# Инструкция по установке на RV1126B

Целевая платформа: **Luckfox Aura** (RV1126B, 1 GB LPDDR4, 16 GB eMMC).
Операционная система: **Ubuntu 22.04 LTS** (Rockchip BSP).

---

## Содержание

1. [Прошивка образа ОС](#1-прошивка-образа-ос)
2. [Первичная настройка системы](#2-первичная-настройка-системы)
3. [Установка RKNN Runtime](#3-установка-rknn-runtime)
4. [Настройка камер (V4L2)](#4-настройка-камер-v4l2)
5. [Установка зависимостей firmware](#5-установка-зависимостей-firmware)
6. [Сборка firmware](#6-сборка-firmware)
7. [Установка моделей](#7-установка-моделей)
8. [Настройка RTSP-сервера](#8-настройка-rtsp-сервера)
9. [Автозапуск через systemd](#9-автозапуск-через-systemd)
10. [Настройка сети и firewall](#10-настройка-сети-и-firewall)
11. [Проверка установки](#11-проверка-установки)
12. [Автотесты firmware](#12-автотесты-firmware)
    - [12.6 Скрипт deploy_and_test.sh](#126-скрипт-deploy_and_testsh)

---

## 1. Прошивка образа ОС

### 1.1 Скачать образ

```bash
# На ПК разработчика (Windows/Linux/macOS)
# Официальная страница: https://wiki.luckfox.com/luckfox-Aura/
# Скачать: Ubuntu 22.04 для Luckfox Aura (файл *.img или *.zip)
```

### 1.2 Прошить eMMC через RKDevTool (Windows)

1. Установить **RKDevTool** и **RK USB Driver** с сайта Rockchip.
2. Перевести плату в режим Maskrom:
   - Зажать кнопку **BOOT** (или замкнуть BOOT0 на GND).
   - Подключить USB-C к ПК — плата появится как `Rockusb Device`.
3. В RKDevTool: выбрать образ → нажать **Run** → дождаться `Download image OK`.

### 1.3 Прошить через rkdeveloptool (Linux/macOS)

```bash
sudo apt install rkdeveloptool   # или собрать из исходников

# Проверить, что плата видна
sudo rkdeveloptool ld
# Ожидаемый вывод: DevNo=1 Vid=0x2207, Pid=0x... ,  Loader

# Прошить
sudo rkdeveloptool db MiniLoaderAll.bin
sudo rkdeveloptool gpt parameter.txt
sudo rkdeveloptool wl 0 luckfox_aura_ubuntu.img
sudo rkdeveloptool rd
```

После перезагрузки плата загрузится с eMMC в Ubuntu 22.04.

---

## 2. Первичная настройка системы

### 2.1 Подключение

```bash
# По UART (115200 baud, USB-UART адаптер на UART2 TX/RX)
# Или по SSH после получения IP по DHCP:
ssh root@<device_ip>   # пароль по умолчанию: luckfox (сменить сразу)
```

### 2.2 Смена пароля и настройка hostname

```bash
passwd root
hostnamectl set-hostname traffic-cam-01
```

### 2.3 Обновление пакетов

```bash
apt update && apt upgrade -y
apt install -y \
    build-essential cmake git curl wget \
    libv4l-dev v4l-utils \
    libssl-dev pkg-config \
    python3 python3-pip \
    nlohmann-json3-dev \
    libmosquitto-dev \
    ffmpeg \
    htop iotop
```

### 2.4 Настройка временной зоны и NTP

```bash
timedatectl set-timezone Europe/Moscow
apt install -y chrony
systemctl enable --now chrony
```

### 2.5 Расширение файловой системы на весь eMMC

```bash
# Только если образ не занял всё пространство автоматически
resize2fs /dev/mmcblk0p8
df -h /   # убедиться, что > 10 GB свободно
```

---

## 3. Установка RKNN Runtime

RKNN Runtime (`librknnrt.so`) — библиотека для запуска `.rknn` моделей на NPU.

### 3.1 Скачать на ПК разработчика

```bash
# На ПК (не на устройстве):
git clone https://github.com/airockchip/rknn-toolkit2.git
# Нужная библиотека:
# rknn-toolkit2/rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so
```

### 3.2 Установить на устройство

```bash
# С ПК разработчика:
scp rknn-toolkit2/rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so \
    root@<device_ip>:/usr/lib/

scp rknn-toolkit2/rknpu2/runtime/Linux/librknn_api/include/rknn_api.h \
    root@<device_ip>:/usr/local/include/

# На устройстве:
ldconfig
```

### 3.3 Проверить NPU

```bash
# На устройстве:
cat /sys/kernel/debug/rknpu/load 2>/dev/null || \
cat /proc/rknpu/load 2>/dev/null
# Ожидаемый вывод: Core0: 0%, Core1: 0%, Core2: 0%

# Проверить версию runtime
strings /usr/lib/librknnrt.so | grep "librknnrt version"
# Ожидаемый вывод: librknnrt version: 2.x.x
```

---

## 4. Настройка камер (V4L2)

### 4.1 Проверить обнаружение камер

```bash
v4l2-ctl --list-devices
# Ожидаемый вывод:
#   rkisp_mainpath (platform:rkisp):
#       /dev/video0   ← фронтальная (IMX335)
#       /dev/video1   ← кабинная (OV4689)
```

### 4.2 Проверить поддерживаемые форматы

```bash
v4l2-ctl -d /dev/video0 --list-formats-ext | grep -A3 "BGR"
# Убедиться, что BGR24 @ 1920x1080 @ 25fps доступен
```

### 4.3 Загрузка драйверов сенсоров (если не загружены автоматически)

```bash
# Проверить текущие модули
lsmod | grep -E "imx335|ov4689|rkisp"

# Если не загружены — добавить в автозагрузку:
cat >> /etc/modules-load.d/cameras.conf << 'EOF'
imx335
ov4689
rkisp_v7
EOF

# Перезагрузиться и проверить снова
reboot
```

### 4.4 Тест захвата кадра

```bash
# Тест фронтальной камеры — захват одного JPEG
v4l2-ctl -d /dev/video0 \
    --set-fmt-video=width=1920,height=1080,pixelformat=BGR3 \
    --stream-mmap --stream-count=1 --stream-to=/tmp/test_front.jpg

# Тест кабинной камеры
v4l2-ctl -d /dev/video1 \
    --set-fmt-video=width=1280,height=720,pixelformat=BGR3 \
    --stream-mmap --stream-count=1 --stream-to=/tmp/test_cabin.jpg

# Скопировать на ПК и проверить
scp root@<device_ip>:/tmp/test_front.jpg .
```

### 4.5 Настройка ISP (яркость, экспозиция)

```bash
# Просмотр доступных элементов управления
v4l2-ctl -d /dev/video0 --list-ctrls-menus

# Пример: включить автоэкспозицию
v4l2-ctl -d /dev/video0 --set-ctrl=exposure_auto=3

# Для IR-режима (ночь) — переключить IR-фильтр через GPIO
echo 1 > /sys/class/gpio/gpio<N>/value   # N — номер GPIO IR-фильтра
```

---

## 5. Установка зависимостей firmware

```bash
# CMake ≥ 3.20
apt install -y cmake
cmake --version   # убедиться, что ≥ 3.20

# nlohmann/json (header-only)
apt install -y nlohmann-json3-dev

# mosquitto (MQTT клиент)
apt install -y libmosquitto-dev

# libcurl (HTTP POST событий)
apt install -y libcurl4-openssl-dev

# GoogleTest (для тестов, опционально)
apt install -y libgtest-dev
```

---

## 6. Сборка firmware

### 6.1 Клонировать репозиторий

```bash
cd /opt
git clone https://github.com/sayr777/rv1126b.git traffic_ai
cd traffic_ai
```

### 6.2 Сборка

```bash
mkdir firmware/build && cd firmware/build

cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DRKNN_SDK_ROOT=/usr   # librknnrt.so уже в /usr/lib

make -j4
# Результат: firmware/build/traffic_ai
```

### 6.3 Установка бинарного файла

```bash
cp firmware/build/traffic_ai /opt/traffic_ai/bin/
chmod +x /opt/traffic_ai/bin/traffic_ai

# Создать рабочую структуру директорий
mkdir -p /opt/traffic_ai/{models,logs,snapshots,config}

# Скопировать конфигурацию
cp firmware/config/config.json  /opt/traffic_ai/config/
cp firmware/config/zones.json   /opt/traffic_ai/config/
```

### 6.4 Отредактировать config.json под реальные параметры

```bash
nano /opt/traffic_ai/config/config.json
```

```json
{
  "front_cam_dev":  "/dev/video0",
  "front_cam_w":    1920,
  "front_cam_h":    1080,
  "front_cam_fps":  25,

  "cabin_cam_dev":  "/dev/video1",
  "cabin_cam_w":    1280,
  "cabin_cam_h":    720,
  "cabin_cam_fps":  25,

  "models": {
    "vehicle_det":  "/opt/traffic_ai/models/vehicle_yolov8n.rknn",
    "plate_det":    "/opt/traffic_ai/models/plate_yolov8n.rknn",
    "plate_ocr":    "/opt/traffic_ai/models/lprnet_crnn.rknn",
    "seatbelt_cls": "/opt/traffic_ai/models/seatbelt_mbv2.rknn",
    "phone_det":    "/opt/traffic_ai/models/phone_yolov8n.rknn"
  },

  "dwell_threshold_sec": 3.0,
  "zones_file":     "/opt/traffic_ai/config/zones.json",

  "http_endpoint":  "http://10.0.0.1:8080/event",
  "mqtt_broker":    "tcp://10.0.0.1:1883",
  "mqtt_topic":     "traffic/cam01",
  "log_dir":        "/opt/traffic_ai/logs",
  "snapshot_dir":   "/opt/traffic_ai/snapshots"
}
```

### 6.5 Запуск тестов (опционально)

```bash
cd firmware/build
ctest --output-on-failure
```

Полное описание сборки и запуска тестов — в разделе [12. Автотесты firmware](#12-автотесты-firmware).

---

## 7. Установка моделей

Модели конвертируются на ПК разработчика (требуется GPU), затем копируются на устройство.

### 7.1 На ПК разработчика — конвертация

```bash
pip install rknn-toolkit2 ultralytics

# YOLOv8n → ONNX
yolo export model=yolov8n.pt format=onnx imgsz=640

# ONNX → RKNN INT8
python models/convert/convert_onnx_to_rknn.py \
    --model  yolov8n.onnx \
    --output models/vehicle_yolov8n.rknn \
    --calib  training/datasets/calibration/ \
    --target rk1126b

# Аналогично для остальных моделей (см. models/README.md)
```

### 7.2 Копирование моделей на устройство

```bash
scp models/*.rknn root@<device_ip>:/opt/traffic_ai/models/

# Проверить
ssh root@<device_ip> "ls -lh /opt/traffic_ai/models/"
```

### 7.3 Проверка моделей на устройстве

```bash
# Быстрый тест загрузки всех моделей:
ssh root@<device_ip> "/opt/traffic_ai/bin/traffic_ai --check-models"
# Ожидаемый вывод:
#   [OK] vehicle_yolov8n.rknn  — loaded, input: 640x640
#   [OK] plate_yolov8n.rknn   — loaded, input: 320x192
#   [OK] lprnet_crnn.rknn     — loaded, input: 94x24
#   [OK] seatbelt_mbv2.rknn   — loaded, input: 224x224
#   [OK] phone_yolov8n.rknn   — loaded, input: 640x640
```

---

## 8. Настройка RTSP-сервера

Используется **mediamtx** (go2rtc) — лёгкий RTSP/HLS сервер.

### 8.1 Установка

```bash
# Скачать последний релиз для arm64
cd /tmp
wget https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_linux_arm64v8.tar.gz
tar xzf mediamtx_linux_arm64v8.tar.gz
mv mediamtx /usr/local/bin/
```

### 8.2 Конфигурация

```bash
cat > /etc/mediamtx.yml << 'EOF'
logLevel: warn
rtspAddress: :8554

paths:
  front:
    source: publisher    # прошивка пушит через RTSP publish
  cabin:
    source: publisher
EOF
```

### 8.3 Systemd-сервис для mediamtx

```bash
cat > /etc/systemd/system/mediamtx.service << 'EOF'
[Unit]
Description=MediaMTX RTSP server
After=network.target

[Service]
ExecStart=/usr/local/bin/mediamtx /etc/mediamtx.yml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now mediamtx
```

Потоки будут доступны:
- `rtsp://<device_ip>:8554/front`
- `rtsp://<device_ip>:8554/cabin`

---

## 9. Автозапуск через systemd

```bash
cat > /etc/systemd/system/traffic_ai.service << 'EOF'
[Unit]
Description=Traffic AI — RV1126B detection pipeline
After=network.target mediamtx.service
Wants=mediamtx.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/traffic_ai
ExecStart=/opt/traffic_ai/bin/traffic_ai /opt/traffic_ai/config/config.json
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Ограничения ресурсов
MemoryMax=800M
CPUWeight=90

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now traffic_ai
```

### Управление сервисом

```bash
systemctl status   traffic_ai     # состояние
systemctl restart  traffic_ai     # перезапуск
systemctl stop     traffic_ai     # остановка
journalctl -u traffic_ai -f       # живой лог
journalctl -u traffic_ai -n 100   # последние 100 строк
```

---

## 10. Настройка сети и firewall

### 10.1 Статический IP (рекомендуется)

```bash
# Найти имя сетевого интерфейса
ip link show
# Например: eth0

# Настроить статический IP через netplan
cat > /etc/netplan/01-static.yaml << 'EOF'
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 10.0.0.5/24
      routes:
        - to: default
          via: 10.0.0.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
EOF

netplan apply
```

### 10.2 Firewall (ufw)

```bash
apt install -y ufw

ufw default deny incoming
ufw default allow outgoing

ufw allow ssh            # порт 22
ufw allow 8554/tcp       # RTSP
ufw allow from 10.0.0.0/24 to any port 8080   # HTTP debug (только ЛВС)

ufw enable
ufw status verbose
```

### 10.3 Watchdog (аппаратный сторожевой таймер)

```bash
# Включить watchdog — устройство перезагрузится при зависании
apt install -y watchdog

cat > /etc/watchdog.conf << 'EOF'
watchdog-device = /dev/watchdog
watchdog-timeout = 60
interval = 10
EOF

systemctl enable --now watchdog
```

---

## 11. Проверка установки

### 11.1 Полная проверка по чеклисту

```bash
# 1. Сервисы работают
systemctl is-active traffic_ai    # active
systemctl is-active mediamtx      # active
systemctl is-active watchdog      # active

# 2. Камеры видны
v4l2-ctl --list-devices | grep video

# 3. NPU доступен
cat /sys/kernel/debug/rknpu/load 2>/dev/null | head -1

# 4. Все модели загружены (смотреть в лог)
journalctl -u traffic_ai -n 50 | grep -E "OK|ERROR|WARN"

# 5. RTSP потоки доступны
ffprobe -v quiet -show_streams rtsp://localhost:8554/front 2>&1 | grep codec_name

# 6. HTTP endpoint отвечает
curl -s -o /dev/null -w "%{http_code}" http://10.0.0.1:8080/health
# Ожидаемый ответ: 200

# 7. MQTT публикация (тест)
mosquitto_pub -h 10.0.0.1 -t "traffic/cam01/heartbeat" \
    -m '{"fps":25,"cpu_temp":55,"npu_load":70,"uptime_s":600}'

# 8. Температура CPU в норме
cat /sys/class/thermal/thermal_zone*/temp | awk '{print $1/1000 " °C"}'
# Должно быть < 75 °C под нагрузкой
```

### 11.2 Ожидаемый вывод journalctl при нормальной работе

```
traffic_ai[1234]: [INFO] RKNN runtime 2.x.x loaded
traffic_ai[1234]: [INFO] Model vehicle_yolov8n.rknn — OK (640x640 INT8)
traffic_ai[1234]: [INFO] Model plate_yolov8n.rknn   — OK (320x192 INT8)
traffic_ai[1234]: [INFO] Model lprnet_crnn.rknn     — OK (94x24 INT8)
traffic_ai[1234]: [INFO] Model seatbelt_mbv2.rknn   — OK (224x224 INT8)
traffic_ai[1234]: [INFO] Model phone_yolov8n.rknn   — OK (640x640 INT8)
traffic_ai[1234]: [INFO] Camera /dev/video0 — 1920x1080 @ 25fps
traffic_ai[1234]: [INFO] Camera /dev/video1 — 1280x720  @ 25fps
traffic_ai[1234]: [INFO] Zones loaded: 1 (waffle_main)
traffic_ai[1234]: [INFO] Pipeline started — main_loop + cabin_loop
traffic_ai[1234]: [INFO] FPS: 24.8  NPU load: 68%  CPU temp: 61°C
```

---

## 12. Автотесты firmware

Тестовый набор написан на **GoogleTest** и не требует физических камер или NPU — все тесты запускаются на хосте (x86-64 или arm64). GoogleTest загружается автоматически через CMake `FetchContent`.

### 12.1 Сборка тестов

```bash
cd /opt/traffic_ai          # корень репозитория
mkdir -p firmware/build_tests && cd firmware/build_tests

cmake .. \
    -DCMAKE_BUILD_TYPE=Debug \
    -DBUILD_TESTS=ON        # включить тестовые цели

make -j4
```

Ожидаемый вывод сборки:

```
-- Fetching GoogleTest v1.14.0 ...
-- Configuring done
-- Build files have been written to: .../firmware/build_tests
[  8%] Building CXX object ...
...
[100%] Linking CXX executable test_zone
[100%] Linking CXX executable test_bytetrack
[100%] Linking CXX executable test_violation
[100%] Linking CXX executable test_event_publisher
[100%] Built target test_lpr
```

### 12.2 Запуск всех тестов через ctest

```bash
cd firmware/build_tests
ctest --output-on-failure -V
```

Ожидаемый вывод при успешном прохождении (все 30 тестов):

```
UpdateCTestConfiguration from :/opt/traffic_ai/firmware/build_tests/CTestTestfile.cmake
1/5 Testing: test_zone
    Start 1: test_zone
1: [==========] Running 11 tests from 4 test suites.
1: [----------] 5 tests from ZoneContainsCenter
1: [ RUN      ] ZoneContainsCenter.CenterInsideZone
1: [       OK ] ZoneContainsCenter.CenterInsideZone (0 ms)
1: [ RUN      ] ZoneContainsCenter.CenterOutsideZone_Left
1: [       OK ] ZoneContainsCenter.CenterOutsideZone_Left (0 ms)
1: [ RUN      ] ZoneContainsCenter.CenterOutsideZone_Above
1: [       OK ] ZoneContainsCenter.CenterOutsideZone_Above (0 ms)
1: [ RUN      ] ZoneContainsCenter.CenterOnBoundary
1: [       OK ] ZoneContainsCenter.CenterOnBoundary (0 ms)
1: [ RUN      ] ZoneContainsCenter.LargeBboxCenterOutside
1: [       OK ] ZoneContainsCenter.LargeBboxCenterOutside (0 ms)
1: [----------] 3 tests from ZoneOverlap
1: [ RUN      ] ZoneOverlap.FullyInside
1: [       OK ] ZoneOverlap.FullyInside (0 ms)
1: [ RUN      ] ZoneOverlap.NoOverlap
1: [       OK ] ZoneOverlap.NoOverlap (0 ms)
1: [ RUN      ] ZoneOverlap.PartialOverlap
1: [       OK ] ZoneOverlap.PartialOverlap (0 ms)
1: [----------] 1 test from ZoneName
1: [ RUN      ] ZoneName.ReturnsCorrectName
1: [       OK ] ZoneName.ReturnsCorrectName (0 ms)
1: [----------] 2 tests from LoadZones
1: [ RUN      ] LoadZones.ParsesValidJson
1: [       OK ] LoadZones.ParsesValidJson (0 ms)
1: [ RUN      ] LoadZones.EmptyFile
1: [       OK ] LoadZones.EmptyFile (0 ms)
1: [==========] 11 tests from 4 test suites ran. (2 ms total)
1: [  PASSED  ] 11 tests.
1/5 Test #1: test_zone ........................   Passed    0.02 sec

2/5 Testing: test_bytetrack
    Start 2: test_bytetrack
2: [==========] Running 7 tests from 1 test suite.
2: [----------] 7 tests from ByteTrack
2: [ RUN      ] ByteTrack.NewTrackAfterMinHits
2: [       OK ] ByteTrack.NewTrackAfterMinHits (0 ms)
2: [ RUN      ] ByteTrack.SingleDetectionSingleTrack
2: [       OK ] ByteTrack.SingleDetectionSingleTrack (0 ms)
2: [ RUN      ] ByteTrack.TwoDetectionsTwoTracks
2: [       OK ] ByteTrack.TwoDetectionsTwoTracks (0 ms)
2: [ RUN      ] ByteTrack.TrackIdPersistsAcrossFrames
2: [       OK ] ByteTrack.TrackIdPersistsAcrossFrames (0 ms)
2: [ RUN      ] ByteTrack.TrackRemovedAfterMaxLost
2: [       OK ] ByteTrack.TrackRemovedAfterMaxLost (0 ms)
2: [ RUN      ] ByteTrack.EmptyDetectionsEmptyTracks
2: [       OK ] ByteTrack.EmptyDetectionsEmptyTracks (0 ms)
2: [ RUN      ] ByteTrack.LowConfNotConfirmedImmediately
2: [       OK ] ByteTrack.LowConfNotConfirmedImmediately (0 ms)
2: [==========] 7 tests from 1 test suite ran. (0 ms total)
2: [  PASSED  ] 7 tests.
2/5 Test #2: test_bytetrack ...................   Passed    0.01 sec

3/5 Testing: test_violation
    Start 3: test_violation
3: [==========] Running 6 tests from 1 test suite.
3: [----------] 6 tests from ViolationDetector
3: [ RUN      ] ViolationDetector.FiresAfterDwellThreshold
3: [       OK ] ViolationDetector.FiresAfterDwellThreshold (151 ms)
3: [ RUN      ] ViolationDetector.NoFireBeforeThreshold
3: [       OK ] ViolationDetector.NoFireBeforeThreshold (0 ms)
3: [ RUN      ] ViolationDetector.NoDoubleFire
3: [       OK ] ViolationDetector.NoDoubleFire (80 ms)
3: [ RUN      ] ViolationDetector.NoFireWhenOutsideZone
3: [       OK ] ViolationDetector.NoFireWhenOutsideZone (80 ms)
3: [ RUN      ] ViolationDetector.PlateAttachedToEvent
3: [       OK ] ViolationDetector.PlateAttachedToEvent (80 ms)
3: [ RUN      ] ViolationDetector.UnconfirmedTrackIgnored
3: [       OK ] ViolationDetector.UnconfirmedTrackIgnored (80 ms)
3: [==========] 6 tests from 1 test suite ran. (471 ms total)
3: [  PASSED  ] 6 tests.
3/5 Test #3: test_violation ...................   Passed    0.47 sec

4/5 Testing: test_event_publisher
    Start 4: test_event_publisher
4: [==========] Running 5 tests from 1 test suite.
4: [----------] 5 tests from EventPublisher
4: [ RUN      ] EventPublisher.WritesLogFile
4: [       OK ] EventPublisher.WritesLogFile (1 ms)
4: [ RUN      ] EventPublisher.LogFileIsValidJson
4: [       OK ] EventPublisher.LogFileIsValidJson (0 ms)
4: [ RUN      ] EventPublisher.EventTypeInJson
4: [       OK ] EventPublisher.EventTypeInJson (0 ms)
4: [ RUN      ] EventPublisher.PlateStoredInJson
4: [       OK ] EventPublisher.PlateStoredInJson (0 ms)
4: [ RUN      ] EventPublisher.MultipleEventsMultipleLogs
4: [       OK ] EventPublisher.MultipleEventsMultipleLogs (0 ms)
4: [==========] 5 tests from 1 test suite ran. (1 ms total)
4: [  PASSED  ] 5 tests.
4/5 Test #4: test_event_publisher .............   Passed    0.01 sec

5/5 Testing: test_lpr
    Start 5: test_lpr
5: [==========] Running 2 tests from 1 test suite.
5: [----------] 2 tests from LprUtils
5: [ RUN      ] LprUtils.NmsRemovesDuplicates
5: [       OK ] LprUtils.NmsRemovesDuplicates (0 ms)
5: [ RUN      ] LprUtils.CropResizeOutputSize
5: [       OK ] LprUtils.CropResizeOutputSize (0 ms)
5: [==========] 2 tests from 1 test suite ran. (0 ms total)
5: [  PASSED  ] 2 tests.
5/5 Test #5: test_lpr .........................   Passed    0.01 sec

100% tests passed, 0 tests failed out of 5
Total Test time (real) =   0.51 sec
```

### 12.3 Запуск отдельного теста

```bash
cd firmware/build_tests

# Все тесты одного бинарника с подробным выводом
./test_zone          --gtest_color=yes
./test_bytetrack     --gtest_color=yes
./test_violation     --gtest_color=yes
./test_event_publisher --gtest_color=yes
./test_lpr           --gtest_color=yes

# Запустить только один конкретный тест
./test_violation --gtest_filter=ViolationDetector.PlateAttachedToEvent

# Запустить все тесты, совпадающие с паттерном
./test_bytetrack --gtest_filter="ByteTrack.*"
```

### 12.4 Интеграционные тесты LPR (требуют .rknn моделей)

Интеграционные тесты LPR pipeline автоматически пропускаются (`SKIPPED`) если переменная `MODELS_DIR` не задана. Для запуска с реальными моделями:

```bash
MODELS_DIR=/opt/traffic_ai/models ./test_lpr --gtest_color=yes
```

Ожидаемый вывод с моделями:

```
[==========] Running 4 tests from 2 test suites.
[----------] 2 tests from LprUtils
[ RUN      ] LprUtils.NmsRemovesDuplicates
[       OK ] LprUtils.NmsRemovesDuplicates (0 ms)
[ RUN      ] LprUtils.CropResizeOutputSize
[       OK ] LprUtils.CropResizeOutputSize (0 ms)
[----------] 2 tests from LprIntegration
[ RUN      ] LprIntegration.LoadModelsWithoutCrash
[       OK ] LprIntegration.LoadModelsWithoutCrash (312 ms)
[ RUN      ] LprIntegration.ProcessBlankFrameNocrash
[       OK ] LprIntegration.ProcessBlankFrameNocrash (18 ms)
[==========] 4 tests from 2 test suites ran. (330 ms total)
[  PASSED  ] 4 tests.
```

### 12.6 Скрипт deploy_and_test.sh

`tools/deploy_and_test.sh` — однокомандный способ собрать и запустить тесты прямо **на SOC** с хост-машины разработчика (Linux / macOS / WSL).

Скрипт автоматически:
1. Проверяет SSH-доступ к SOC.
2. Устанавливает `cmake`, `g++`, `rsync`, `git` на SOC если их нет.
3. Синхронизирует исходники через `rsync` (передаётся только diff).
4. Собирает тестовые бинарники на SOC (`cmake + make -j$(nproc)`).
5. Запускает `ctest -V` и выводит цветной итог.

#### Требования на хосте

- `bash`, `rsync`, `ssh` (в WSL на Windows: `wsl`-терминал)
- SSH-доступ к SOC без пароля (рекомендуется SSH-ключ):
  ```bash
  ssh-keygen -t ed25519       # создать ключ (если нет)
  ssh-copy-id root@10.0.0.5  # скопировать на SOC
  ```

#### Базовый запуск

```bash
# из корня репозитория
./tools/deploy_and_test.sh <SOC_IP>

# пример
./tools/deploy_and_test.sh 10.0.0.5
```

#### Дополнительные варианты

```bash
# Указать пользователя и порт SSH
./tools/deploy_and_test.sh 10.0.0.5 root 22

# Полная пересборка (удалить build-кэш на SOC)
CLEAN_BUILD=1 ./tools/deploy_and_test.sh 10.0.0.5

# Пропустить синхронизацию — только сборка и запуск
NO_RSYNC=1 ./tools/deploy_and_test.sh 10.0.0.5

# Интеграционные тесты LPR (требуют .rknn моделей на SOC)
MODELS_DIR=/opt/traffic_ai/models ./tools/deploy_and_test.sh 10.0.0.5
```

#### Ожидаемый вывод

```
▶ Проверка SSH-соединения с root@10.0.0.5:22
✓ Соединение установлено
   Архитектура: aarch64   ОС: Ubuntu 22.04.3 LTS

▶ Проверка зависимостей на SOC
✓ g++ — g++ (Ubuntu 13.x) 13.x.x
✓ cmake — cmake version 3.28.3
✓ rsync — rsync  version 3.x.x
✓ git — git version 2.x.x

▶ Синхронизация исходников → root@10.0.0.5:/opt/rv1126b_src
✓ Исходники синхронизированы

▶ Сборка тестов на SOC (cmake + make)
[cmake] Конфигурируем ...
-- Fetching GoogleTest v1.14.0 ...
-- Configuring done
[make] Собираем ...
[100%] Built target test_violation
✓ Сборка завершена

▶ Запуск unit-тестов на SOC
 1/29 Test  #1: ZoneContainsCenter.CenterInsideZone ..........   Passed    0.00 sec
 2/29 Test  #2: ZoneContainsCenter.CenterOutsideZone_Left ....   Passed    0.00 sec
...
29/29 Test #29: EventPublisher.MultipleEventsMultipleLogs ....   Passed    0.01 sec

100% tests passed, 0 tests failed out of 29
Total Test time (real) =   0.70 sec

▶ Итог

  ✓  29/29 тестов прошли
```

> **Первый запуск** занимает дольше: CMake скачивает GoogleTest (~30 MB) и компилирует его.  
> Повторные запуски используют кэш — значительно быстрее.

#### Типичные проблемы

| Симптом                                | Решение                                                          |
|----------------------------------------|------------------------------------------------------------------|
| `Permission denied (publickey)`        | Скопируйте SSH-ключ: `ssh-copy-id root@<SOC_IP>`               |
| `rsync: command not found` на хосте   | `sudo apt install rsync` или запускайте из WSL                  |
| `cmake: No such file or directory`     | Скрипт установит cmake автоматически; нужен интернет на SOC     |
| Ошибка скачивания GoogleTest           | SOC не имеет доступа в интернет; заранее установите `libgtest-dev` на SOC и добавьте `-DBUILD_TESTS_USE_SYSTEM_GTEST=ON` |
| Тест падает только на SOC             | Запустите бинарник с `--gtest_color=yes` напрямую: `ssh root@<SOC_IP> "cd /opt/rv1126b_src/firmware/build_tests && ./test_violation"` |

---

### 12.5 Структура тестов

| Файл                       | Тест-суит              | Кол-во | Что проверяется                                          |
|----------------------------|------------------------|--------|----------------------------------------------------------|
| `test_zone.cpp`            | ZoneContainsCenter     | 5      | Попадание центра bbox в полигон зоны                     |
|                            | ZoneOverlap            | 3      | Доля перекрытия bbox с зоной                             |
|                            | ZoneName               | 1      | Имя зоны из конфига                                      |
|                            | LoadZones              | 2      | Разбор `zones.json`, пустой файл                         |
| `test_bytetrack.cpp`       | ByteTrack              | 7      | Подтверждение трека, два объекта, persistence ID, потеря |
| `test_violation.cpp`       | ViolationDetector      | 6      | Dwell-time, повторный fire, прикрепление номера, фильтры |
| `test_event_publisher.cpp` | EventPublisher         | 5      | Создание лог-файла, валидный JSON, поля type/plate       |
| `test_lpr.cpp`             | LprUtils               | 2      | Unit (без NPU)                                           |
|                            | LprIntegration         | 2      | Интеграция с .rknn (пропускается без MODELS_DIR)         |

---

## Устранение типичных проблем

| Симптом                                   | Причина                          | Решение                                   |
|-------------------------------------------|----------------------------------|-------------------------------------------|
| `librknnrt.so: cannot open shared object` | Библиотека не найдена            | `ldconfig` после копирования .so          |
| `/dev/video0` отсутствует                 | Драйвер сенсора не загружен      | Проверить `dmesg`, добавить модуль в `/etc/modules-load.d/` |
| NPU load всегда 0%                        | Модель не запущена / ошибка ctx  | Проверить лог: `journalctl -u traffic_ai` |
| RTSP поток не открывается                 | mediamtx не запущен              | `systemctl status mediamtx`               |
| Температура CPU > 80 °C                   | Нет термопасты или вентиляции    | Нанести термопасту, проверить корпус      |
| HTTP события не доходят до сервера        | Firewall или неверный IP         | `curl` с устройства вручную, проверить `config.json` |
