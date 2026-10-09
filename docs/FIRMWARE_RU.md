# Устройство мониторинга ESP32

Исходный файл: [`firmware/MachineMonitor/MachineMonitor.ino`](../firmware/MachineMonitor/MachineMonitor.ino). Скетч получен от автора и добавлен без изменения поведения, GPIO или MQTT protocol. Версия в MQTT Discovery — `1.1`; она независима от версии HA-интеграции `1.2.2`.

## Оборудование и сигналы

Текущий стенд: классический ESP32 DevKit / ESP32-WROOM-32, четырёхканальная плата PC817 и преобразователь питания XL4015E.

| Физический вход | GPIO ESP32 | Настройка |
|---|---:|---|
| Input 1 | 32 | INPUT_PULLUP |
| Input 2 | 33 | INPUT_PULLUP |
| Input 3 | 25 | INPUT_PULLUP |
| Input 4 | 26 | INPUT_PULLUP |

На стороне ESP32 выход соответствующего оптоканала должен опускать GPIO к логическому LOW при активном сигнале. LOW → ON; HIGH → OFF. Подавать напряжение машинного сигнала прямо на GPIO нельзя; GPIO рассчитаны на логику 3,3 В. Выходной транзистор оптоканала работает с логической землёй ESP32. Изоляция и подключения входной стороны зависят от конкретной PC817-платы.

В репозитории нет универсальной электросхемы для произвольного оборудования. Проверьте допустимое входное напряжение и резисторы именно вашей платы PC817. Настройте преобразователь на требуемое вашей ESP32-плате питание до подключения; допустимые точки подачи питания зависят от платы. Для цепей сетевого напряжения требуется отдельное проектирование квалифицированным специалистом.

## Сборка Arduino IDE

1. Установите Arduino IDE и поддержку **esp32 by Espressif Systems** через Boards Manager. Официальная инструкция: [Arduino ESP32 Installing](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html).
2. При необходимости добавьте в настройки Boards Manager URL:

   ```text
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```

3. В Library Manager установите **PubSubClient** (Nick O'Leary). [Исходники библиотеки](https://github.com/knolleary/pubsubclient). WiFi, WebServer, Preferences и ESPmDNS входят в Arduino ESP32 core.
4. Откройте `firmware/MachineMonitor/MachineMonitor.ino`. Имя файла и каталога скетча совпадают.
5. Выберите плату, соответствующую своему ESP32; для обычной DevKit используйте подходящий вариант **ESP32 Dev Module**, и выберите USB/COM port.
6. Проверьте константы `MQTT_BROKER_NAME`, `MQTT_PORT`, `AP_PASSWORD` перед сборкой. Broker по умолчанию `homeassistant.local:1883`, setup-AP пароль фиксирован в исходнике. Замените пароль собственным до эксплуатации; не коммитьте production credentials.
7. Выполните **Verify**, затем **Upload**. Откройте Serial Monitor на **115200 baud**. Если плата требует ручного входа в bootloader, используйте её кнопку BOOT при загрузке.

Точная версия ESP32 core и PubSubClient, на которой автор прошивал устройство, не предоставлена. В среде подготовки этого репозитория компиляция и загрузка на ESP32 не выполнялись. Ошибку сборки следует сообщать с названием платы и версиями core/library.

## Первый запуск

Без сохранённой Wi-Fi сети ESP32 создаёт AP `MachineMonitor-<короткий ID>`. Пароль берётся из константы `AP_PASSWORD` вашего скетча.

1. Подключитесь к AP устройства.
2. Откройте адрес из Serial Monitor, обычно **http://192.168.4.1/**.
3. Введите Device name, Wi-Fi SSID/password, MQTT username/password.
4. Нажмите **Save and reboot**. Настройки сохраняются в Preferences/NVS; устройство перезапускается примерно через 2 секунды.
5. После подключения к домашней сети настройочная AP отключается. Страница остаётся доступной по IP ESP32 или `http://<hostname>.local/`, если локальная сеть разрешает имя.
6. Проверьте Serial Monitor: Wi-Fi и MQTT connected, публикация Discovery и состояний. Найдите четыре sensor в интеграции MQTT Home Assistant.

Для имени устройства используйте простое имя латиницей, цифры и дефисы. Скетч фильтрует hostname, но напрямую вставляет Device name в HTML и Discovery JSON без escaping; кавычки и HTML-символы могут нарушить страницу или Discovery.

## Что делает скетч

- Debounce физических входов — 50 мс.
- Состояния читаются даже без сети, но события за время отсутствия MQTT не буферизуются.
- Wi-Fi reconnect: попытки каждые 10 секунд; примерно после 20 секунд отсутствия Wi-Fi включается fallback AP, одновременно продолжается поиск сохранённой сети.
- MQTT reconnect: интервал попыток 5 секунд. При соединении публикуются Discovery, availability `online` и все четыре текущих состояния.
- При HA birth `homeassistant/status = online` повторно публикуются Discovery и текущие состояния.
- Настроечная страница показывает входы и состояние связи; сохранение настроек перезапускает ESP32.
- В этом скетче нет OTA, SD-buffer, исторической догрузки и выходов управления.

## MQTT protocol

`deviceId` формируется из MAC чипа, а не из пользовательского имени. Переименование не меняет этот ID.

| Topic | Payload | Retain |
|---|---|---|
| `machine_monitor/<deviceId>/state/input1` … `input4` | `ON` / `OFF` | Да |
| `machine_monitor/<deviceId>/availability` | `online`; LWT `offline` | Да |
| `machine_monitor/<deviceId>/event` | JSON с `input`, `state`, `millis` | Нет |
| `homeassistant/binary_sensor/<deviceId>/input1/config` … `input4/config` | MQTT Discovery JSON | Да |

Пример event:

```json
{"input":1,"state":"ON","millis":123456}
```

`millis` — время от старта ESP32, не UTC timestamp. HA-интеграция использует source entities и не строит свою историю из этого event topic. Потеря связи означает неизвестную активность: восстановление текущего ON не доказывает непрерывность ON в пропущенном периоде.

Транспорт текущего скетча — обычный MQTT TCP без TLS. Настройочная HTTP-страница не требует авторизации; содержимое password-полей включает сохранённые значения. Развёртывайте устройство в доверенной/изолированной локальной сети; подробности — [ограничения](SECURITY_AND_LIMITATIONS.md).
