# Machine Monitor

Equipment monitoring with **ESP32 → MQTT → Home Assistant**. The device observes four physical signals; the integration keeps independent input history, resolves semantic machine states and presents a reusable monitoring dashboard.

**Integration:** 1.2.2 · **Firmware:** supplied Arduino sketch (Discovery version 1.1) · **Interface:** Русский / English

## Возможности

- Real Flow: независимые физические входы на общей шкале времени, одновременные сигналы, фильтры, порядок строк, масштаб и навигация.
- Текущее состояние машины, длительность, доступность и последняя связь.
- Отдельная semantic history с настраиваемыми приоритетами, статистика и события.
- OFFLINE как неизвестная активность: интервалы включения разрываются при потере достоверных данных.
- Отчёты по периодам A/B, сравнение и смены, включая смены через полночь.
- Постоянная история и настраиваемый срок хранения: 7–365 дней, по умолчанию 30.
- Обзор нескольких машин, отдельная Lovelace-карточка, графический редактор.
- Автоматическая регистрация frontend и панели в боковом меню; копировать JS в `/www` не нужно.
- Обновления по событиям, резервный опрос раз в 5 секунд, локальный таймер длительности.

## Быстрый старт

1. Настройте MQTT в Home Assistant и прошейте ESP32: [прошивка и подключение](docs/FIRMWARE_RU.md).
2. Скопируйте **только** `custom_components/machine_monitor` в `/config/custom_components/machine_monitor` и перезапустите HA.
3. **Настройки → Устройства и службы → Добавить интеграцию → Machine Monitor**. Укажите четыре исходных MQTT `binary_sensor`.
4. Через **Настроить** задайте имена входов, состояния, приоритеты и цвета.
5. **Боковое меню → Machine Monitor → машина**. Откроется Real Flow.
6. **⚙ Настройки → Язык интерфейса**: Русский, English или язык Home Assistant.

Подробности: [установка](docs/INSTALL_RU.md) · [руководство пользователя](docs/MANUAL_RU.md) · [архитектура](docs/ARCHITECTURE.md) · [проверки и разработка](docs/DEVELOPMENT.md) · [ограничения и сеть](docs/SECURITY_AND_LIMITATIONS.md).

## English quick start

Install `custom_components/machine_monitor` into your HA configuration directory, restart HA, then add **Machine Monitor** under **Settings → Devices & services → Add integration**. Map the four source binary sensors and configure their names, semantic categories, priorities and colors. Open **Machine Monitor** in the sidebar and select a machine. The integration serves and registers its bundled JavaScript automatically.

Flash `firmware/MachineMonitor/MachineMonitor.ino` using Arduino IDE with Espressif ESP32 board support and the **PubSubClient** library. Inputs are GPIO32, GPIO33, GPIO25, GPIO26 with `INPUT_PULLUP`; LOW means active. Configure Wi-Fi and MQTT credentials using the device's local setup page. The supplied firmware uses `homeassistant.local:1883`; edit its broker constant before flashing if your broker differs. See [firmware guide](docs/FIRMWARE_RU.md) for setup, wiring boundaries and recovery behavior.

The system **monitors only**. It never starts, stops or controls equipment and is not a safety interlock. Physical histories are independent of the semantic priority winner. Offline time is unknown activity, not idle time.

## Repository layout

```text
custom_components/machine_monitor/  # install this directory in Home Assistant
  frontend/                        # full UI + machine card + editor
  translations/                    # HA configuration flow translations
  tests/                           # backend and frontend regression tests
firmware/MachineMonitor/            # Arduino sketch supplied by the author
  MachineMonitor.ino
docs/                              # installation, firmware and user guide
AGENTS.md                          # engineering specification
```

## Validation and status

The integration has local regression tests using Home Assistant boundary stubs and a minimal frontend DOM. They do not replace testing on a running Home Assistant installation. The original firmware is included without behavioral changes; compilation and board upload have not been verified in the publication environment. Exact tested HA/Arduino core versions have not been recorded yet; a compatibility matrix is a follow-up item.

No firmware binaries, Home Assistant configuration, persistent machine data or credentials configured on a device are included. The sketch contains a public default setup-AP password: change `AP_PASSWORD` before deploying a new device and read the security notes.

## License

No distribution license has been selected yet. Public visibility alone is not a grant of permission to reuse or redistribute the code. A license can be added by the project owner.
