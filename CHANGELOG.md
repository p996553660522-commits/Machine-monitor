# История изменений Machine Monitor

## Integration 1.4.2 — 2026-10-20

- Remove native browser title tooltips that duplicated the styled Real Flow tooltip after a hover delay, in detailed/compact input bars, OFFLINE bands and row labels. Preserve translated interval metadata and accessible labels.
- Keep mouse/touch/keyboard interaction, add keyboard-focus display and handle nested label targets. No monitoring, history, statistics, MQTT or firmware changes; schema 4.
- Local validation: 105 integration Python tests, 47 frontend tests, 9 release tests, JavaScript syntax.


## Integration 1.4.1 — 2026-10-20

- Serialize shared coordinator initialization when HA sets up several config entries concurrently. Previously independent coordinators could overwrite each other, leaving a configured machine absent from the overview/API.
- Add concurrent setup/API and two-machine event-driven overview regressions. No physical/semantic history, MQTT, firmware or Real Flow rendering changes; history schema remains 4.
- Local validation: 105 Python integration tests, 45 frontend tests, JavaScript syntax. Live restart acceptance is still required. A separate transient Lovelace configuration error was observed but not reproduced after refresh; its cause is not established by this fix.


Номера интеграции и ESP32 firmware независимы. Готовые пакеты: [GitHub Releases](https://github.com/p996553660522-commits/Machine-monitor/releases). Точные коммиты, схемы истории и compatibility notes: [каталог версий](docs/VERSIONS_RU.md).

## Интеграция 1.4.0

- Произвольные названия режимов, условия И/ИЛИ и приоритеты.
- Продуктивное, непродуктивное и исключённое время независимо от категории.
- Учёт сохраняется в семантических интервалах; изменение не пересчитывает прошлое.
- Группировка разрывов <10 секунд только в Real Flow, точная история доступна.
- Исправлены RGB selector настроек и порядок событий с разными UTC offsets.
- Схема истории 4: чтение старых данных 1–3 с сохранением прежнего учёта.
- 104 Python и 44 frontend tests. Firmware 1.2.1 не менялась.

## Интеграция 1.3.0

- Привязка от одного до четырёх физических источников.
- acquisition_enabled: отключённая линия не создаёт ложный OFFLINE.
- ON закрывается при отключении линии и возвращается только после достоверного ON.
- Старая физическая история и статистика сохраняются.
- 97 Python и 37 frontend tests, схема истории 3.
- Известна несовместимость ColorSelector с современным HA; исправлена в 1.4.0.

## Интеграция 1.2.2

- Первоначальная публикация интеграции, исходников ESP32 и руководств.
- Независимые physical/semantic histories, Real Flow, OFFLINE, сохранение истории.
- Профили, статистика, отчёты/смены, sidebar и Lovelace card.
- Русский/English интерфейс, event-driven updates и fallback.
- 88 Python и 36 frontend tests, схема истории 3.
- Известна несовместимость ColorSelector с современным HA; исправлена в 1.4.0.

## Firmware 1.2.2

- Поле MQTT broker address в конфигураторе: IPv4 или DNS-имя, сохранение в NVS.
- Прежний homeassistant.local остаётся default для устройств без нового ключа.
- IPv4 подключается напрямую без mDNS; подходит для broker 192.168.0.22 через VPN.
- Неверный адрес отклоняется до сохранения; порт остаётся 1883.
- Проверка DNS больше не принимает ненулевой код ошибки за успех.
- Прежние GPIO, inputs, Wi-Fi recovery, MQTT topics/Discovery и настройки сохраняются.

## Firmware 1.2.1

- Wi-Fi/AP инициализируется до HTTP server: исправлен assert первого запуска.
- GPIO, MQTT protocol и сохранённые настройки остаются прежними.

## Firmware 1.2 (тег firmware-v1.2.0, архив с известной ошибкой)

- Переключатели сигнальных линий с сохранением в NVS.
- Per-line availability и acquisition_enabled для HA.
- Известная ошибка первого запуска без настроек Wi-Fi; используйте 1.2.1.

## Firmware 1.1 (тег firmware-v1.1.0)

- Исходный опубликованный четырёхканальный ESP32 sketch с MQTT Discovery.
- Версии до первого опубликованного снимка не реконструируются задним числом.

## Правила дальнейших выпусков

Каждая новая версия получает неизменный тег, описание, отдельные integration/firmware/source ZIP, SHA256SUMS и инструкцию установки/отката. Сначала проходят тесты точного коммита и проверка пакетов, затем публикация. Процесс описан в [RELEASING.md](docs/RELEASING.md).
