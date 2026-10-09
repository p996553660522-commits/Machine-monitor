/**
 * Machine Monitor dashboard and machine card V6.
 *
 * Real Flow shows the PHYSICAL INPUT history: one shared time axis, one row
 * per input. The semantic machine state stays a separate layer (current
 * status + statistics).
 *
 * Updates are event driven: the backend fires the HA event
 * machine_monitor_state_changed on every physical change and the card
 * refreshes immediately (debounced). A 5 second timer remains as fallback.
 */
(function () {
  "use strict";

  // UI-only preference: never modify machine profiles or stored history.
  var RU = {
  "Today": "Сегодня",
  "Yesterday": "Вчера",
  "This week": "Эта неделя",
  "Last week": "Прошлая неделя",
  "This month": "Этот месяц",
  "Last month": "Прошлый месяц",
  "Custom range": "Свой период",
  "Custom order": "Заданный порядок",
  "Name": "Название",
  "Activity duration": "Время активности",
  "Number of activations": "Количество включений",
  "Last activity": "Последняя активность",
  "Try again": "Повторить",
  "Connecting to your workshop": "Подключение к мастерской",
  "Loading machines and their latest activity…": "Загрузка машин и последних данных…",
  "Your workshop starts here": "Начните с добавления машины",
  "Add Machine Monitor from Settings > Devices & services to connect your first machine.": "Добавьте Machine Monitor: Настройки → Устройства и службы → Добавить интеграцию.",
  "← All machines": "← Все машины",
  "History period": "Период истории",
  "Range start": "Начало периода",
  "Range end": "Конец периода",
  "Choose a past start and a later end": "Выберите начало в прошлом и конец позднее начала",
  "↻ Refresh": "↻ Обновить",
  "Refresh current data": "Обновить данные",
  "WORKSHOP OVERVIEW": "ОБЗОР МАСТЕРСКОЙ",
  "Your machines, at a glance.": "Все машины — на одном экране.",
  " machines · ": " машин · ",
  " online · Today's activity": " на связи · Активность за сегодня",
  "Sort machines": "Сортировка машин",
  "State": "Состояние",
  "Work time": "Время работы",
  "Idle time": "Время простоя",
  "Sort: ": "Сортировка: ",
  "Open ": "Открыть: ",
  "Offline": "Нет связи",
  "Unknown": "Неизвестно",
  "Last seen ": "Последняя связь: ",
  "Work": "Работа",
  "Non-work": "Без работы",
  "Work share": "Доля работы",
  "Machine workspace": "Разделы машины",
  "Monitor": "Мониторинг",
  "Reports": "Отчёты",
  "Diagnostics": "Диагностика",
  "Productive time": "Продуктивное время",
  "Non-productive time": "Непродуктивное время",
  "% of included known time": "% от учтённого известного времени",
  "No included known time": "Нет учтённого известного времени",
  "Idle and other non-work states": "Простой и другие нерабочие состояния",
  "% of selected period": "% выбранного периода",
  "Unknown machine activity": "Активность машины неизвестна",
  "Downtimes": "Простои",
  "Longest ": "Самый долгий: ",
  "Loading machine activity…": "Загрузка активности машины…",
  "MACHINE WORKSPACE": "МОНИТОРИНГ МАШИНЫ",
  "Machine": "Машина",
  "Data unavailable": "Данные недоступны",
  "Monitoring online": "Мониторинг на связи",
  "Machine diagnostics": "Диагностика машины",
  "Storage and source details for investigating missing or unavailable data.": "Хранение истории и состояние источников для проверки пропусков и недоступных данных.",
  "CURRENT STATUS": "ТЕКУЩЕЕ СОСТОЯНИЕ",
  "Offline for: ": "Без связи: ",
  "last seen ": "Последняя связь: ",
  "recovered ": "Связь восстановлена: ",
  "SEMANTIC STATISTICS": "СТАТИСТИКА СОСТОЯНИЙ",
  "Work ": "Работа: ",
  "Percentages: included known time ": "Проценты от учтённого известного времени: ",
  "Idle ": "Простой: ",
  "Offline ": "Без связи: ",
  "Downtimes ": "Простоев: ",
  " (max ": " (максимум ",
  "Detailed": "Подробно",
  "Compact": "Компактно",
  "Real Flow row order": "Порядок строк Real Flow",
  "Zoom -": "Масштаб −",
  "Zoom +": "Масштаб +",
  "Now": "Сейчас",
  "Independent physical signals · ": "Независимые физические сигналы · ",
  "No physical inputs configured.": "Физические входы не настроены.",
  "Input: ": "Вход: ",
  "NOW": "СЕЙЧАС",
  "All inputs": "Все входы",
  "Availability": "Доступность",
  "All inputs are hidden by the filter.": "Все входы скрыты фильтром.",
  "History available from: ": "История доступна с: ",
  "INPUT FILTERS": "ФИЛЬТРЫ ВХОДОВ",
  "All": "Все",
  "None": "Ни одного",
  "Hide ": "Скрыть ",
  "Show ": "Показать ",
  " in Real Flow": " в Real Flow",
  "HISTORY STORAGE": "ХРАНЕНИЕ ИСТОРИИ",
  "Retention:": "Срок хранения:",
  " days": " дн.",
  "Persistent file:": "Файл истории:",
  "Not yet available": "Пока недоступно",
  " bytes": " байт",
  "Oldest record:": "Первая запись:",
  "Newest record:": "Последняя запись:",
  "Physical intervals:": "Физические интервалы:",
  "Semantic intervals:": "Интервалы состояний:",
  "Change retention and shifts in Settings > Devices & services > Machine Monitor > Configure > Machine settings.": "Срок хранения и смены: Настройки → Устройства и службы → Machine Monitor → Настроить → Настройки машины.",
  "Choose a valid period A": "Выберите корректный период A",
  "Choose both dates for period B": "Укажите обе даты периода B",
  "REPORTS — ": "ОТЧЁТЫ — ",
  "Select local dates for period A and optional comparison B. Reports are calculated when requested.": "Выберите местные даты периода A и, при необходимости, периода B для сравнения. Отчёт рассчитывается по запросу.",
  "Period A · From": "Период A · С",
  "Period A · To": "Период A · По",
  "Period B · From (optional)": "Период B · С (необязательно)",
  "Period B · To (optional)": "Период B · По (необязательно)",
  "Calculating...": "Расчёт…",
  "Generate report / compare": "Рассчитать / сравнить",
  "Total period": "Весь период",
  "Known monitored time": "Известное время мониторинга",
  "Unrecorded / unknown": "Нет записей / неизвестно",
  "Idle": "Простой",
  "Idle share": "Доля простоя",
  "Offline share": "Доля времени без связи",
  "Work cycles": "Рабочие циклы",
  "Longest work": "Самая долгая работа",
  "Longest idle": "Самый долгий простой",
  "Longest downtime": "Самая долгая остановка",
  "B versus A": "Сравнение B с A",
  "Metric": "Показатель",
  "Change": "Изменение",
  "N/A (A = 0)": "Нет данных (A = 0)",
  "Period ": "Период ",
  "Semantic states ": "Состояния ",
  "Physical inputs ": "Физические входы ",
  "Input": "Вход",
  "ON time": "Время включения",
  "Activations": "Включения",
  "Work/idle %: known time included in statistics. Offline %: full period. Unrecorded time is unknown. Physical inputs can overlap; their totals need not sum to the period. Cycles count work starts inside the period.": "Доли работы и простоя рассчитаны от известного времени, включённого в статистику; доля времени без связи — от всего периода. Время без записей неизвестно. Физические входы могут работать одновременно, поэтому сумма их длительностей может превышать период. Циклы — начала работы внутри периода.",
  "Shifts — period A — ": "Смены — период A — ",
  "Shift": "Смена",
  "Known": "Известное время",
  "Work %": "Работа, %",
  "Idle %": "Простой, %",
  "Configure shifts in Machine settings: Name | HH:MM | HH:MM, one per line. Overnight shifts are supported.": "Настройте смены в настройках машины: Название | ЧЧ:ММ | ЧЧ:ММ, по одной в строке. Поддерживаются смены через полночь.",
  "SOURCE DIAGNOSTICS": "ДИАГНОСТИКА ИСТОЧНИКОВ",
  "Semantic: ": "Состояние: ",
  "Last state change: ": "Последнее изменение: ",
  "PHYSICAL INPUTS": "ФИЗИЧЕСКИЕ ВХОДЫ",
  "No inputs configured.": "Входы не настроены.",
  "UNKNOWN": "НЕИЗВЕСТНО",
  "ON": "ВКЛ",
  "OFF": "ВЫКЛ",
  " act.": " включ.",
  "SEMANTIC EVENTS": "СОБЫТИЯ СОСТОЯНИЙ",
  "Newest first": "Сначала новые",
  "Oldest first": "Сначала старые",
  "Longest first": "Сначала длительные",
  "Shortest first": "Сначала короткие",
  "No semantic events in this period.": "В этом периоде нет событий состояний.",
  "Select a machine in the card editor.": "Выберите машину в редакторе карточки.",
  "Loading Machine Monitor...": "Загрузка Machine Monitor…",
  "Choose a machine and make this card yours.": "Выберите машину и настройте карточку.",
  "Select a machine": "Выберите машину",
  "Period": "Период",
  "Real Flow mode": "Режим Real Flow",
  "Show current status": "Показывать текущее состояние",
  "Show input totals": "Показывать итоги по входам",
  "Show offline periods": "Показывать периоды без связи",
  "Real Flow time navigator": "Навигатор времени Real Flow",
  "Drag to navigate the selected period": "Перетаскивайте для перемещения по выбранному периоду",
  "Cannot load machines: ": "Не удалось загрузить машины: ",
  "Cannot load states: ": "Не удалось загрузить состояния: ",
  "Cannot load timeline: ": "Не удалось загрузить историю: ",
  "Heating": "Нагрев",
  "Cooling": "Остывание",
  "Preparation": "Подготовка",
  "Waiting": "Ожидание",
  "Technical": "Техническое состояние",
  "Alarm": "Авария",
  "Other": "Другое",
  "Settings": "Настройки",
  "Interface language": "Язык интерфейса",
  "Automatic (Home Assistant)": "Автоматически (Home Assistant)",
  "Language is saved in this browser.": "Язык сохраняется в этом браузере.",
  "\nState: ON\nStart: ": "\nСостояние: ВКЛ\nНачало: ",
  "\nEnd: ": "\nКонец: ",
  "\nDuration: ": "\nДлительность: ",
  "OFFLINE (unavailable)\nStart: ": "НЕТ СВЯЗИ (данные недоступны)\nНачало: ",
  " | Available: ": " | Доступен: ",
  " | Enabled: ": " | Включён: ",
  " | Error: ": " | Ошибка: ",
  " | Physical: ": " | Физический: ",
  " | Real Flow in profile: ": " | Real Flow в профиле: ",
  "yes": "да",
  "no": "нет",
  "missing": "отсутствует",
  "unknown": "неизвестно",
  "hidden": "скрыт",
  "visible": "виден",
  "Unavailable sources:": "Недоступны источники:",
  " (error: own Machine Monitor entity)": " (ошибка: собственная entity Machine Monitor)",
  "Monitoring disabled": "Мониторинг выключен",
  "No enabled sources": "Нет включённых источников",
  "1 h": "1 ч",
  "6 h": "6 ч",
  "12 h": "12 ч",
  "24 h": "24 ч",
  "7 d": "7 дн.",
  "30 d": "30 дн.",
  "60 d": "60 дн.",
  "90 d": "90 дн.",
  "180 d": "180 дн.",
  "365 d": "365 дн.",
  "h ": " ч ",
  "m": " мин",
  "m ": " мин ",
  "s": " с",
  "pp": "п.п.",
  "Machine Monitor — Full UI": "Machine Monitor — Полный интерфейс",
  "One machine: current status, physical Real Flow and input totals. Visual editor included.": "Одна машина: текущее состояние, физический Real Flow и итоги по входам. Есть графический редактор.",
  "Machine overview, physical Real Flow, statistics, input filters and events.": "Обзор машин, физический Real Flow, статистика, фильтры входов и события."
};
  var LANGUAGE_KEY = "machine_monitor.language";
  var languagePreference = "auto", haLanguage = "en";
  var languageViews = new Set();
  try {
    var storedLanguage = window.localStorage.getItem(LANGUAGE_KEY);
    if (["auto", "ru", "en"].includes(storedLanguage)) languagePreference = storedLanguage;
  } catch (_) { /* Private browsers may deny storage. The UI remains usable. */ }
  if (typeof navigator !== "undefined") haLanguage = /^ru(?:-|$)/i.test(navigator.language || "") ? "ru" : "en";
  function language() { return languagePreference === "auto" ? haLanguage : languagePreference; }
  function t(key) { return language() === "ru" && Object.prototype.hasOwnProperty.call(RU,key) ? RU[key] : key; }
  function redrawLanguages() { localizeCardMetadata(); languageViews.forEach(view => { view._dirty = true; view._render(); }); }
  function setHassLanguage(hass) {
    if (!hass.language && !hass.locale?.language) return;
    var next = /^ru(?:-|$)/i.test(hass.language || hass.locale?.language || "en") ? "ru" : "en";
    if (next !== haLanguage) { haLanguage = next; if(languagePreference === "auto") redrawLanguages(); }
  }
  function chooseLanguage(value, owner) {
    if (!["auto", "ru", "en"].includes(value)) return;
    languagePreference = value;
    try { window.localStorage.setItem(LANGUAGE_KEY,value); } catch (_) { /* In-memory fallback. */ }
    if (TIP) TIP.style.display = "none";
    redrawLanguages();
    if (!languageViews.has(owner)) { owner._dirty=true;owner._render(); }
  }
  function translatedError(message) {
    for (var key of ["Cannot load machines: ","Cannot load states: ","Cannot load timeline: ","Choose a valid period A","Choose both dates for period B"]) {
      for (var prefix of [key,RU[key]]) if (message && message.startsWith(prefix)) return t(key)+message.slice(prefix.length);
    }
    return message;
  }
  function languageSettings(owner) {
    var box=el("details",{position:"relative"}), summary=el("summary",null,"⚙ "+t("Settings"));
    box.open=Boolean(owner._languageSettingsOpen);
    summary.onclick=()=>{owner._languageSettingsOpen=!box.open;};
    box.ontoggle=()=>{if(box.isConnected)owner._languageSettingsOpen=box.open;};
    box.appendChild(summary);
    var panel=el("div",{padding:"12px",minWidth:"230px"}),label=el("label",null,t("Interface language")+" ");
    var select=el("select",SEL);select.setAttribute("aria-label","Language / Язык");
    [["auto",t("Automatic (Home Assistant)")],["ru","Русский"],["en","English"]].forEach(item=>{
      var option=el("option",null,item[1]);option.value=item[0];option.selected=item[0]===languagePreference;select.appendChild(option);
    });
    select.onchange=()=>{owner._languageSettingsOpen=box.open;chooseLanguage(select.value,owner);};
    label.appendChild(select);panel.appendChild(label);panel.appendChild(el("div",{fontSize:"11px",marginTop:"8px"},t("Language is saved in this browser.")));
    box.appendChild(panel);return box;
  }
  function localizeCardMetadata() {
    (window.customCards || []).forEach(card=>{
      if(card.type==="machine-monitor-card") {
        card.name=t("Machine Monitor — Full UI");
        card.description=t("Machine overview, physical Real Flow, statistics, input filters and events.");
      } else if(card.type==="machine-monitor-machine-card") {
        card.description=t("One machine: current status, physical Real Flow and input totals. Visual editor included.");
      }
    });
  }
  var STATE_LABELS={work:"Work",idle:"Idle",preparation:"Preparation",waiting:"Waiting",technical:"Technical",cooling:"Cooling",heating:"Heating",alarm:"Alarm",other:"Other",offline:"Offline"};
  function semanticLabel(state,label) {
    var standard=STATE_LABELS[state];
    // Preserve any custom display label; translate only canonical semantic names.
    return standard && (!label || label===standard || label===state) ? t(standard) : (label || state || t("Unknown"));
  }

  var PERIODS = [
    { id: "1h", label: "1 h", hours: 1 },
    { id: "6h", label: "6 h", hours: 6 },
    { id: "12h", label: "12 h", hours: 12 },
    { id: "today", label: "Today", hours: 0 },
    { id: "yesterday", label: "Yesterday", hours: 0 },
    { id: "week", label: "This week", hours: 0 },
    { id: "last_week", label: "Last week", hours: 0 },
    { id: "month", label: "This month", hours: 0 },
    { id: "last_month", label: "Last month", hours: 0 },
    { id: "24h", label: "24 h", hours: 24 },
    { id: "7d", label: "7 d", hours: 168 },
    { id: "30d", label: "30 d", hours: 720 },
    { id: "60d", label: "60 d", hours: 1440 },
    { id: "90d", label: "90 d", hours: 2160 },
    { id: "180d", label: "180 d", hours: 4320 },
    { id: "365d", label: "365 d", hours: 8760 },
    { id: "custom", label: "Custom range", hours: 24 }
  ];

  var ROW_SORTS = [
    ["custom", "Custom order"],
    ["name", "Name"],
    ["duration", "Activity duration"],
    ["activations", "Number of activations"],
    ["last", "Last activity"]
  ];

  var MACHINE_SORTS = {
    name: function (a, b) { return a.name.localeCompare(b.name); },
    state: function (a, b) { return a.state.localeCompare(b.state); },
    work: function (a, b) { return (b.work_seconds || 0) - (a.work_seconds || 0); },
    idle: function (a, b) { return (b.idle_seconds || 0) - (a.idle_seconds || 0); },
    activity: function (a, b) {
      return String(b.state_since || "").localeCompare(String(a.state_since || ""));
    }
  };

  var EVENT_SORT = {
    newest: function (a, b) { return String(b.start).localeCompare(String(a.start)); },
    oldest: function (a, b) { return String(a.start).localeCompare(String(b.start)); },
    longest: function (a, b) { return (b.duration || 0) - (a.duration || 0); },
    shortest: function (a, b) { return (a.duration || 0) - (b.duration || 0); }
  };

  function fmtDuration(seconds) {
    seconds = Math.max(0, Math.floor(seconds || 0));
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (h) return h + t("h ") + String(m).padStart(2, "0") + t("m");
    if (m) return m + t("m ") + String(s).padStart(2, "0") + t("s");
    return s + t("s");
  }

  function fmtClock(iso) {
    if (!iso) return "--:--";
    var d = new Date(iso);
    return String(d.getHours()).padStart(2, "0") + ":" +
      String(d.getMinutes()).padStart(2, "0");
  }

  function fmtDateTime(iso) {
    if (!iso) return "--";
    var d = new Date(iso);
    return d.toLocaleDateString(language()) + " " + d.toLocaleTimeString(language());
  }

  function hms(seconds) {
    seconds = Math.max(0, Math.floor(seconds || 0));
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    return String(h).padStart(2, "0") + ":" +
      String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  function el(tag, styles, text) {
    var node = document.createElement(tag);
    if (styles) Object.assign(node.style, styles);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  var TIP = null;
  function tip() {
    if (!TIP) {
      TIP = el("div", {
        position: "fixed", display: "none", zIndex: "9999",
        pointerEvents: "none", background: "rgba(0,0,0,.88)", color: "#fff",
        padding: "8px 11px", borderRadius: "6px", fontSize: "11px",
        lineHeight: "1.55", maxWidth: "260px"
      });
      document.body.appendChild(TIP);
    }
    return TIP;
  }

  var BTN = {
    padding: "8px 13px", minHeight: "38px", borderRadius: "10px", cursor: "pointer",
    border: "1px solid var(--divider-color)",
    background: "var(--card-background-color)",
    color: "var(--primary-text-color)", fontSize: "12px"
  };
  var SEL = {
    padding: "8px 11px", minHeight: "38px", borderRadius: "10px", fontSize: "13px", maxWidth: "100%",
    border: "1px solid var(--divider-color)",
    background: "var(--card-background-color)",
    color: "var(--primary-text-color)"
  };
  var SECTION = {
    padding: "20px", marginBottom: "16px", borderRadius: "16px", minWidth: "0",
    border: "1px solid var(--divider-color)", background: "var(--card-background-color)"
  };
  var ROW = { display: "flex", alignItems: "center", gap: "6px" };
  var CELL = { minWidth: "0", overflow: t("hidden"), textOverflow: "ellipsis" };
  var TABLE = { display: "flex", flexDirection: "column" };
  var CSS = `
:host{display:block;color:var(--primary-text-color,#18212b);font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif);
--mm-surface:var(--ha-card-background,var(--card-background-color,#fff));--mm-muted:var(--secondary-text-color,#667585);--mm-line:var(--divider-color,#e1e7ed);
--mm-accent:var(--primary-color,#168889);--mm-soft:var(--secondary-background-color,#f4f6f8);--mm-label:clamp(96px,15cqi,160px);container-type:inline-size;font-size:14px;line-height:1.5}
*,*::before,*::after{box-sizing:border-box}[hidden]{display:none!important}button,input,select{font:inherit}button,select,input{transition:border-color .15s,background .15s,box-shadow .15s}
button{touch-action:manipulation}button:hover{border-color:var(--mm-accent)!important;background:var(--mm-soft)!important}button:focus-visible,select:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--mm-accent);outline-offset:3px}
button:disabled{opacity:.5;cursor:wait}select{cursor:pointer}input[type=checkbox]{accent-color:var(--mm-accent);width:19px;height:19px}
.mm-shell{max-width:1440px;margin:0 auto;padding:24px clamp(12px,3cqi,40px) 40px}.mm-topbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:0 0 22px;border-bottom:1px solid var(--mm-line);margin-bottom:24px}
.mm-brand{display:flex;align-items:center;gap:11px;font-weight:750;font-size:17px;letter-spacing:-.4px;margin-right:auto}.mm-logo{display:flex;align-items:center;gap:3px;width:34px;height:34px;border-radius:10px;padding:8px;background:var(--mm-accent);color:white}
.mm-logo i{width:4px;background:currentColor;border-radius:3px;height:11px}.mm-logo i:nth-child(2){height:19px}.mm-logo i:nth-child(3){height:15px}
.mm-subtle{color:var(--mm-muted);font-size:12px}.mm-caption{font-size:11px;font-weight:700;letter-spacing:1.25px;color:var(--mm-muted);text-transform:uppercase}.mm-title{margin:0;font-size:clamp(24px,4cqi,36px);font-weight:730;line-height:1.18;letter-spacing:-1px;overflow-wrap:anywhere}
.mm-pagehead{display:flex;align-items:end;justify-content:space-between;gap:16px;margin:8px 0 22px;flex-wrap:wrap}.mm-fleet-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:16px}
.mm-machine-tile{padding:22px!important;text-align:left;display:flex;flex-direction:column;gap:18px;min-width:0;border-radius:18px!important;background:var(--mm-surface)!important;box-shadow:0 2px 5px #00000004;position:relative;overflow:hidden}
.mm-machine-tile::before{content:'';position:absolute;left:0;top:22px;bottom:22px;width:3px;background:var(--machine-color,var(--mm-accent));border-radius:4px}
.mm-tile-head,.mm-tile-state{display:flex;align-items:center;justify-content:space-between;gap:12px}.mm-tile-head strong{font-size:19px;letter-spacing:-.35px}.mm-tile-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.mm-tile-stats strong{display:block;font-size:17px;font-variant-numeric:tabular-nums}
.mm-pill{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:650;padding:5px 10px;border-radius:30px;background:var(--mm-soft)}.mm-dot{width:8px;height:8px;display:inline-block;border-radius:50%;background:currentColor;flex-shrink:0}
.mm-meter{display:flex;height:5px;background:var(--mm-soft);border-radius:6px;overflow:hidden}.mm-meter>span{height:100%}
.mm-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(210px,.65fr);gap:30px;align-items:center;margin:0 0 24px}.mm-hero-name{display:flex;flex-direction:column;align-items:flex-start;gap:10px}.mm-description{color:var(--mm-muted);max-width:620px;line-height:1.6}
.mm-status{border:0!important;border-left:1px solid var(--mm-line)!important;background:transparent!important;border-radius:0!important;margin:0!important;padding:4px 0 4px 28px!important}.mm-status-line{gap:10px!important}.mm-status-name{font-size:24px!important;letter-spacing:-.5px}.mm-status-time{font-size:26px!important;letter-spacing:-1px;font-variant-numeric:tabular-nums;font-family:inherit!important;margin-left:auto}
.mm-tabs{display:flex;gap:4px;border-bottom:1px solid var(--mm-line);margin-bottom:22px;overflow-x:auto}.mm-tabs button{border:0!important;border-radius:0!important;background:transparent!important;padding:13px 18px!important;white-space:nowrap;color:var(--mm-muted)!important;border-bottom:3px solid transparent!important;font-weight:600}.mm-tabs button[aria-selected=true]{color:var(--mm-accent)!important;border-bottom-color:var(--mm-accent)!important}
.mm-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:20px}.mm-kpi{border:1px solid var(--mm-line);background:var(--mm-surface);border-radius:14px;padding:16px 18px;min-width:0}.mm-kpi-value{font-size:clamp(21px,3cqi,30px);font-weight:700;letter-spacing:-.8px;font-variant-numeric:tabular-nums;margin:6px 0 2px;line-height:1.25}.mm-kpi small{color:var(--mm-muted);font-size:11px;display:block}
.mm-lower-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:start}.mm-flow{padding:22px!important;overflow:hidden}.mm-flow-title{font-size:17px!important;font-weight:700;letter-spacing:-.3px!important;color:var(--primary-text-color)!important}.mm-flow-subtitle{margin:3px 0 18px;color:var(--mm-muted);font-size:12px}.mm-flow-toolbar{gap:5px!important;margin-bottom:24px!important}.mm-flow-toolbar [aria-pressed=true]{background:var(--mm-soft)!important;border-color:var(--mm-accent)!important}
.mm-flow-axis{position:relative;display:block!important;height:18px;margin-left:calc(var(--mm-label) + 12px)!important;padding-left:0!important;margin:0 0 10px calc(var(--mm-label) + 12px)!important;font-variant-numeric:tabular-nums;font-size:11px!important}.mm-flow-axis>div{position:absolute;width:auto;overflow:visible;white-space:nowrap}.mm-flow-axis>div:not(:first-child){transform:translateX(-50%)}.mm-flow-axis>div:last-child{transform:translateX(-100%)}
.mm-flow-row{height:42px!important;gap:12px!important;margin-bottom:8px!important}.mm-flow-label{flex:0 0 var(--mm-label)!important;font-size:12px!important;gap:7px!important;min-width:0}.mm-flow-track{height:28px!important;border-radius:6px!important;background-color:var(--mm-soft)!important;background-image:linear-gradient(to right,var(--mm-line) 1px,transparent 1px);background-size:16.6667% 100%}.mm-flow-compact{height:42px!important}
.mm-now{left:calc(var(--mm-label) + 12px + (100% - var(--mm-label) - 12px) * var(--now-ratio))!important;background:var(--mm-accent)!important}.mm-navigator{margin:18px 0 4px calc(var(--mm-label) + 12px)!important;height:22px!important;background:var(--mm-soft)!important;border:1px solid var(--mm-line)}.mm-navigator>div{background:var(--mm-accent)!important;opacity:.6}
.mm-filters{border:0!important;border-top:1px solid var(--mm-line)!important;border-radius:0!important;padding:18px 0 0!important;margin:18px 0 0!important;background:transparent!important}.mm-filters button{min-height:34px;font-size:12px!important}.mm-section-heading{font-size:12px!important;font-weight:700;letter-spacing:1px!important;margin-bottom:14px!important}
.mm-summary-row{display:grid!important;grid-template-columns:10px minmax(65px,1fr) auto 76px 56px;gap:10px!important;padding:12px 0!important;font-size:13px!important}.mm-summary-row>div{min-width:0;overflow-wrap:anywhere}.mm-input-time{white-space:nowrap;font-size:12px;color:var(--primary-text-color)!important;font-weight:650}
.mm-event-row{padding:13px 0!important;display:grid!important;grid-template-columns:110px minmax(70px,1fr) minmax(0,1fr) 70px;gap:10px!important}.mm-events-list{max-height:420px;overflow:auto}.mm-error{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 18px;border:1px solid var(--error-color,#cf5252);border-radius:12px;margin-bottom:18px;color:var(--error-color,#cf5252)}
.mm-empty{padding:55px 24px;text-align:center;background:var(--mm-surface);border:1px dashed var(--mm-line);border-radius:18px;color:var(--mm-muted)}.mm-empty strong{display:block;font-size:20px;color:var(--primary-text-color);margin-bottom:8px}.mm-empty button{margin-top:18px}
details>summary{cursor:pointer;font-size:14px!important;font-weight:650;padding:4px 0;list-style-position:inside}details[open]>summary{margin-bottom:14px}
.mm-report-controls{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px!important;margin:20px 0}.mm-report-controls label{display:flex;flex-direction:column;gap:7px;color:var(--mm-muted);font-size:12px!important}.mm-report-controls .mm-primary{grid-column:1/-1;justify-self:start}.mm-report-controls input{width:100%;color-scheme:normal}.mm-primary{background:var(--mm-accent)!important;color:var(--text-primary-color,#fff)!important;border-color:var(--mm-accent)!important;font-weight:650}.mm-primary:hover{filter:brightness(1.08);background:var(--mm-accent)!important}
.mm-report-periods{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.mm-single-period{grid-template-columns:1fr}.mm-report-period{min-width:0}.mm-report-table{border:1px solid var(--mm-line);border-radius:12px;padding:16px;margin-top:20px!important}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{text-align:left;padding:11px 8px!important;white-space:nowrap;font-size:13px}td:not(:first-child),th:not(:first-child){text-align:right}tr:last-child td{border-bottom:0!important}tbody tr:hover{background:var(--mm-soft)}.mm-report-table td:first-child{white-space:normal}
.mm-storage-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.mm-storage-item{background:var(--mm-soft);padding:16px;border-radius:12px;overflow-wrap:anywhere}.mm-storage-item strong{display:block;font-size:20px;margin-top:5px;letter-spacing:-.4px}.mm-diagnostic-row{padding:14px 0;border-bottom:1px solid var(--mm-line);line-height:1.8}
.mm-card{display:block;padding:18px!important;overflow:hidden;background:var(--mm-surface);border:1px solid var(--mm-line);border-radius:16px}.mm-card-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:16px}.mm-card-heading strong{font-size:19px;letter-spacing:-.5px}.mm-card .mm-status{border:0!important;padding:0!important;margin:0 0 18px!important}.mm-card .mm-flow{padding:0!important;border:0!important;border-radius:0!important;background:transparent!important}.mm-card .mm-flow-toolbar{margin-bottom:15px!important}.mm-card .mm-flow-toolbar button{min-height:32px;padding:5px 8px!important;font-size:11px!important}.mm-card .mm-flow-toolbar select{min-width:0;max-width:120px;font-size:11px!important;min-height:32px}.mm-card .mm-flow-row{height:34px!important}.mm-card .mm-flow-track{height:24px!important}.mm-card .mm-summary{margin:18px 0 0!important;padding:16px 0 0!important;border:0!important;border-top:1px solid var(--mm-line)!important;border-radius:0!important;background:transparent!important}
.mm-editor{padding:8px;display:grid;gap:12px}.mm-editor label{border:1px solid var(--mm-line);padding:14px;border-radius:12px;margin:0!important;display:flex!important;align-items:center;justify-content:space-between;gap:12px}.mm-editor select{max-width:65%}.mm-editor-note{color:var(--mm-muted);font-size:13px;margin-bottom:4px}
@container (max-width:760px){.mm-report-periods{grid-template-columns:1fr}.mm-shell{padding:16px 14px 28px}.mm-hero{grid-template-columns:1fr;gap:20px}.mm-status{border-left:0!important;border-top:1px solid var(--mm-line)!important;padding:18px 0 0!important}.mm-lower-grid{grid-template-columns:1fr}.mm-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.mm-topbar{gap:8px;margin-bottom:20px}.mm-brand{width:100%}.mm-flow{padding:16px!important}}
@container (max-width:440px){.mm-flow-axis>div:nth-child(even){display:none}.mm-tabs button{padding:11px 13px!important}.mm-flow-toolbar{gap:4px!important}.mm-flow-toolbar button{padding:6px 8px!important;font-size:11px!important;min-height:34px}.mm-flow-toolbar select{max-width:130px}.mm-summary-row{grid-template-columns:8px minmax(45px,1fr) auto 80px!important;gap:7px!important}.mm-activation{grid-column:2/-1;text-align:left!important;font-size:11px}.mm-report-controls,.mm-storage-grid{grid-template-columns:1fr}.mm-event-row{grid-template-columns:84px minmax(60px,1fr) 76px}.mm-event-row>div:last-child{white-space:nowrap;font-size:11px}.mm-event-source{grid-column:2;grid-row:2}.mm-status-name{font-size:21px!important}.mm-status-time{font-size:23px!important}.mm-flow-subtitle{font-size:11px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
`;
function named(node,name){node.className=name;return node;}
function styledRoot(root){root.appendChild(el("style",null,CSS));}
function heading(title,subtitle){var box=el("div");box.appendChild(named(el("div",null,title),"mm-section-heading"));if(subtitle)box.appendChild(named(el("div",null,subtitle),"mm-subtle"));return box;}


  class MachineMonitorCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
      this._connection = null;
      this._pendingRefresh = false;
      this._detailRequest = 0;
      this._machines = [];
      this._selected = null;
      this._period = "today";
      this._customStart = null;
      this._customEnd = null;
      this._mode = "detailed";
      this._rowSort = "custom";
      this._sort = "name";
      this._eventSort = "newest";
      this._visible = {};
      this._zoom = 1;
      this._panMs = 0;
      this._detail = null;
      this._states = [];
      this._error = null;
      this._loading = true;
      this._view = "overview";
      this._workspace = "monitor";
      this._downtime = null;
      this._dirty = true;
      this._timer = null;
      this._liveTimer = null;
      this._debounce = null;
      this._unsubEvent = null;
      this._liveNode = null;
      this._liveSince = null;
      this._offlineNode = null;
      this._offlineSince = null;
      this._refreshing = false;
      this._report = null;
      this._reportDates = {};
      this._reportOpen = false;
      this._reportRequest = 0;
      this._drag = null;
      this._controlRefresh = null;
      this.shadowRoot.addEventListener("focusout", () => {
        if (this._controlRefresh) clearTimeout(this._controlRefresh);
        this._controlRefresh = setTimeout(() => { this._controlRefresh = null; if (this.isConnected) this._render(); }, 0);
      });
      this.addEventListener("pointermove", this._moveNavigator.bind(this));
      this.addEventListener("pointerup", this._endNavigator.bind(this));
      this.addEventListener("pointercancel", this._endNavigator.bind(this));
    }

    static getStubConfig() {
      return { type: "custom:machine-monitor-card", mode: "detailed", period: "today" };
    }

    setConfig(config) {
      this._config = Object.assign(
        { type: "custom:machine-monitor-card" }, config || {});
      if (config && config.period) this._period = config.period;
      if (config && config.sort_by) this._sort = config.sort_by;
      if (config && (config.mode === "compact" || config.mode === "detailed")) this._mode = config.mode;
      if (config && config.row_sort) this._rowSort = config.row_sort;
      this._dirty = true;
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      setHassLanguage(hass);
      if (this.isConnected) this._startConnection();
    }

    _startConnection() {
      if (!this._hass || this._connection === this._hass.connection) return;
      this._stopConnection();
      var connection = this._hass.connection;
      this._connection = connection;
      this._loadStates();
      this._refreshCurrent();
      var self = this;
      // Subscription errors leave polling alive, and reconnect retries it.
      this._unsubEvent = connection.subscribeEvents(
        this._onMachineEvent.bind(this), "machine_monitor_state_changed"
      ).catch(function () { return null; });
      this._timer = setInterval(function () { self._refreshCurrent(); }, 5000);
      this._liveTimer = setInterval(function () { self._tickLive(); }, 1000);
    }

    _stopConnection() {
      if (this._timer) clearInterval(this._timer);
      if (this._liveTimer) clearInterval(this._liveTimer);
      if (this._debounce) clearTimeout(this._debounce);
      if (this._controlRefresh) clearTimeout(this._controlRefresh);
      this._controlRefresh = null;
      if (this._unsubEvent) {
        Promise.resolve(this._unsubEvent).then(function (un) { if (un) un(); });
      }
      this._timer = this._liveTimer = this._debounce = null;
      this._unsubEvent = null;
      this._connection = null;
      this._detailRequest++;
      this._reportRequest++;
      this._endNavigator();
      if (TIP) TIP.style.display = "none";
    }

    connectedCallback() { languageViews.add(this); this._startConnection(); this._dirty = true; this._render(); }
    disconnectedCallback() { languageViews.delete(this); this._stopConnection(); }

    getCardSize() { return 8; }

    _onMachineEvent(event) {
      this._scheduleRefresh();
    }

    _scheduleRefresh() {
      if (this._debounce) clearTimeout(this._debounce);
      var self = this;
      this._debounce = setTimeout(function () {
        self._debounce = null;
        self._refreshCurrent();
      }, 250);
    }

    _tickLive() {
      if (this._liveNode && this._liveSince) {
        this._liveNode.textContent = hms((Date.now() - this._liveSince) / 1000);
      }
      if (this._offlineNode && this._offlineSince) {
        this._offlineNode.textContent =
          hms((Date.now() - this._offlineSince) / 1000);
      }
    }

    _callWs(type, payload) {
      if (!this._hass) return Promise.reject(new Error("no hass"));
      return this._hass.callWS(Object.assign({ type: type }, payload || {}));
    }

    async _loadStates() {
      try {
        var res = await this._callWs("machine_monitor/states");
        this._states = res.states || [];
        this._dirty = true;
        this._render();
      } catch (err) {
        this._dirty = true;
        this._error = t("Cannot load states: ") + err.message;
        this._render();
      }
    }

    async _loadOverview() {
      try {
        var res = await this._callWs("machine_monitor/overview");
        this._machines = res.machines || [];
        if (!this._selected && this._machines.length) {
          this._selected = this._machines[0].machine_id;
        }
        this._loading = false;
        this._error = null;
        this._dirty = true;
        this._render();
      } catch (err) {
        this._loading = false;
        this._dirty = true;
        this._error = t("Cannot load machines: ") + err.message;
        this._render();
      }
    }

    async _refreshCurrent() {
      if (!this._hass || !this.isConnected) return;
      if (this._refreshing) { this._pendingRefresh = true; return; }
      this._refreshing = true;
      try {
        do {
          this._pendingRefresh = false;
          await this._loadOverview();
          if (this._selected && this._view === "machine") await this._loadDetail();
        } while (this._pendingRefresh && this.isConnected);
      } finally {
        this._refreshing = false;
      }
    }

    async _loadDetail() {
      if (!this._selected) return;
      var request = ++this._detailRequest;
      var machineId = this._selected;
      var period = this._period;
      var range = this._periodRange();
      try {
        // Keep the complete input list. Visibility is strictly local display.
        var res = await this._callWs("machine_monitor/timeline", {
          machine_id: machineId, period: period,
          start: range.start.toISOString(), end: range.end.toISOString()
        });
        if (request !== this._detailRequest || machineId !== this._selected || period !== this._period) return;
        this._detail = res;
        this._error = null;
        this._adoptVisibility(res);
        this._downtime = res.stats && res.stats.downtime;
      } catch (err) {
        if (request !== this._detailRequest) return;
        this._dirty = true;
        this._error = t("Cannot load timeline: ") + err.message;
      }
      this._dirty = true;
      this._render();
    }

    _adoptVisibility(res) {
      var rows = res && res.input_timeline && res.input_timeline.rows || [];
      for (var i = 0; i < rows.length; i++) {
        if (typeof this._visible[rows[i].slot] !== "boolean") {
          this._visible[rows[i].slot] = rows[i].visible !== false && rows[i].enabled !== false;
        }
      }
    }

    async _select(machineId) {
      this._report = null;
      this._reportBusy = false;
      this._reportError = null;
      this._reportDates = {};
      this._reportRequest++;
      this._workspace = "monitor";
      this._selected = machineId;
      this._view = "machine";
      this._detail = null;
      this._visible = {};
      this._zoom = 1;
      this._panMs = 0;
      this._dirty = true;
      this._render();
      await this._loadDetail();
    }

    async _setPeriod(period) {
      this._period = period;
      this._zoom = 1;
      this._panMs = 0;
      this._dirty = true;
      this._render();
      await this._loadDetail();
    }

    _setMode(mode) { this._mode = mode; this._dirty = true; this._render(); }
    _setRowSort(sort) { this._rowSort = sort; this._dirty = true; this._render(); }

    _toggleVisible(slot) {
      this._visible[slot] = this._visible[slot] === false;
      this._dirty = true;
      this._render();
    }

    _allVisible(value) {
      var keys = Object.keys(this._visible);
      for (var i = 0; i < keys.length; i++) this._visible[keys[i]] = value;
      this._dirty = true;
      this._render();
    }

    _zoomIn() { this._zoom = Math.min(200, this._zoom * 2); this._dirty = true; this._render(); }
    _zoomOut() { this._zoom = Math.max(1, this._zoom / 2); if (this._zoom === 1) this._panMs = 0; this._dirty = true; this._render(); }
    _jumpNow() { this._setNavigatorFraction(1); }

    _setNavigatorFraction(fraction) {
      var span = this._baseSpan();
      this._panMs = (Math.max(0, Math.min(1, fraction)) - 0.5) * (span - span / this._zoom);
      this._dirty = true;
      this._render();
    }

    _moveNavigator(event) {
      if (!this._drag || event.pointerId !== this._drag.id) return;
      var drag = this._drag;
      this._setNavigatorFraction(drag.fraction + (event.clientX - drag.x) / drag.travel);
    }

    _endNavigator() {
      if (this._drag && this.hasPointerCapture && this.hasPointerCapture(this._drag.id)) {
        this.releasePointerCapture(this._drag.id);
      }
      this._drag = null;
    }

    _renderNavigator() {
      var self = this, range = this._viewRange(), span = this._baseSpan();
      var width = Math.min(1, range.span / span), travel = 1 - width;
      var fraction = travel ? Math.max(0, Math.min(1, this._panMs / (span * travel) + 0.5)) : 0;
      var track = el("div", { margin: "12px 0 4px 96px", height: "18px", position: "relative",
        background: "var(--divider-color)", borderRadius: "5px", touchAction: "none", cursor: "pointer" });
      track.className = "mm-navigator";
      track.title = t("Drag to navigate the selected period");
      track.setAttribute("role", "scrollbar");
      track.setAttribute("aria-label", t("Real Flow time navigator"));
      track.setAttribute("aria-orientation", "horizontal");
      track.setAttribute("aria-valuemin", "0");
      track.setAttribute("aria-valuemax", "100");
      track.setAttribute("aria-valuenow", String(Math.round(fraction * 100)));
      track.tabIndex = 0;
      var thumb = el("div", { position: "absolute", top: "2px", bottom: "2px", borderRadius: "4px",
        background: "var(--primary-color)", width: (width * 100) + "%", left: (fraction * travel * 100) + "%" });
      track.appendChild(thumb);
      track.onpointerdown = function (event) {
        if (self._zoom === 1 || (event.button != null && event.button !== 0)) return;
        event.preventDefault();
        var rect = track.getBoundingClientRect();
        var initial = fraction;
        if (event.target !== thumb) initial = Math.max(0, Math.min(1, ((event.clientX - rect.left) / rect.width - width / 2) / travel));
        self._drag = { id: event.pointerId, x: event.clientX, fraction: initial, travel: Math.max(1, rect.width * travel) };
        // Capture on the stable custom element; child rows may be redrawn while dragging.
        self.setPointerCapture(event.pointerId);
        self._setNavigatorFraction(initial);
      };
      track.onkeydown = function (event) {
        var next = event.key === "Home" ? 0 : event.key === "End" ? 1 :
          event.key === "ArrowLeft" ? fraction - 0.05 : event.key === "ArrowRight" ? fraction + 0.05 : null;
        if (next !== null) { event.preventDefault(); self._setNavigatorFraction(next); }
      };
      return track;
    }
    _panLeft() { this._panMs -= this._baseSpan() * 0.25 / this._zoom; this._dirty = true; this._render(); }
    _panRight() { this._panMs += this._baseSpan() * 0.25 / this._zoom; this._dirty = true; this._render(); }

    _baseSpan() {
      var data = this._detail && this._detail.input_timeline;
      var r = data ? { start: new Date(data.start), end: new Date(data.end) } : this._periodRange();
      return Math.max(1, r.end.getTime() - r.start.getTime());
    }

    _viewRange() {
      var data = this._detail && this._detail.input_timeline;
      var r = data ? { start: new Date(data.start), end: new Date(data.end) } : this._periodRange();
      var span0 = r.end.getTime() - r.start.getTime();
      var span = Math.max(1, span0 / this._zoom);
      var center = (r.start.getTime() + r.end.getTime()) / 2 + this._panMs;
      center = Math.max(r.start.getTime() + span / 2, Math.min(r.end.getTime() - span / 2, center));
      return {
        start: new Date(center - span / 2),
        end: new Date(center + span / 2),
        span: span
      };
    }

    _periodRange() {
      var now = new Date();
      var id = this._period;
      var start;
      if (id === "custom") {
        return { start: this._customStart || new Date(now.getTime() - 86400000), end: this._customEnd || now };
      }
      if (id === "today") {
        start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      } else if (id === "yesterday") {
        return {
          start: new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1),
          end: new Date(now.getFullYear(), now.getMonth(), now.getDate())
        };
      } else if (id === "week") {
        var d = new Date(now);
        var day = (d.getDay() + 6) % 7;
        start = new Date(d.getFullYear(), d.getMonth(), d.getDate() - day);
      } else if (id === "last_week") {
        var d2 = new Date(now);
        var day2 = (d2.getDay() + 6) % 7;
        start = new Date(d2.getFullYear(), d2.getMonth(), d2.getDate() - day2 - 7);
        return { start: start, end: new Date(d2.getFullYear(), d2.getMonth(), d2.getDate() - day2) };
      } else if (id === "last_month") {
        return { start: new Date(now.getFullYear(), now.getMonth() - 1, 1), end: new Date(now.getFullYear(), now.getMonth(), 1) };
      } else if (id === "month") {
        start = new Date(now.getFullYear(), now.getMonth(), 1);
      } else {
        var found = PERIODS.find(function (p) { return p.id === id; });
        start = new Date(now.getTime() - (found ? found.hours : 24) * 3600 * 1000);
      }
      return { start: start, end: now };
    }

    _render() {
      if (!this._dirty) return;
      var active = this.shadowRoot.activeElement;
      if (active && active.tagName === "INPUT") return;
      if (active && active.id && active.id.startsWith("mm-tab-")) this._focusTab=active.id.slice(7);
      this._dirty = false;
      var root = this.shadowRoot;
      root.innerHTML = "";
      this._liveNode = this._offlineNode = null;
      if (TIP) TIP.style.display = "none";
      styledRoot(root);
      this.setAttribute("lang",language());
      var shell = named(el("div"), "mm-shell"); root.appendChild(shell);
      shell.appendChild(this._renderHeader());
      if (this._error) {
        var alert = named(el("div"), "mm-error"); alert.setAttribute("role", "alert");
        alert.appendChild(el("span", null, translatedError(this._error)));
        var retry = el("button", BTN, t("Try again")); retry.onclick = () => this._refreshCurrent();
        alert.appendChild(retry); shell.appendChild(alert);
        if (!this._detail && !this._machines.length) return;
      }
      if (this._loading && !this._machines.length) {
        var loading = named(el("div"), "mm-empty"); loading.setAttribute("role", "status");
        loading.appendChild(el("strong", null, t("Connecting to your workshop")));
        loading.appendChild(el("div", null, t("Loading machines and their latest activity…")));
        shell.appendChild(loading); return;
      }
      if (!this._machines.length) {
        var empty = named(el("div"), "mm-empty");
        empty.appendChild(el("strong", null, t("Your workshop starts here")));
        empty.appendChild(el("div", null, t("Add Machine Monitor from Settings > Devices & services to connect your first machine.")));
        shell.appendChild(empty); return;
      }
      shell.appendChild(this._view === "overview" ? this._renderOverview() : this._renderMachine());
      if(this._focusTab && root.getElementById) { root.getElementById("mm-tab-"+this._focusTab)?.focus({preventScroll:true});this._focusTab=null; }
    }

    _renderHeader() {
      var bar = named(el("div"), "mm-topbar");
      var brand = named(el("div"), "mm-brand"), logo = named(el("span"), "mm-logo");
      logo.setAttribute("aria-hidden", "true");
      for (var i=0; i<3; i++) logo.appendChild(el("i"));
      brand.appendChild(logo); brand.appendChild(el("span", null, "Machine Monitor")); bar.appendChild(brand);
      if (this._view === "machine") {
        var back = el("button", BTN, t("← All machines"));
        back.onclick = () => { this._view = "overview"; this._dirty = true; this._render(); };
        bar.appendChild(back);
        var periodSel = el("select", SEL); periodSel.setAttribute("aria-label", t("History period"));
        PERIODS.forEach(p => { var o=el("option",null,t(p.label));o.value=p.id;o.selected=p.id===this._period;periodSel.appendChild(o); });
        periodSel.onchange = () => this._setPeriod(periodSel.value); bar.appendChild(periodSel);
        if (this._period === "custom") {
          var customRange = this._periodRange();
          ["start", "end"].forEach(key => {
            var input=el("input",SEL); input.type="datetime-local";
            input.title=key === "start" ? t("Range start") : t("Range end"); input.setAttribute("aria-label", input.title);
            var dt=customRange[key]; input.value=new Date(dt.getTime()-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);
            input.onchange=() => {
              var value=new Date(input.value); if (isNaN(value.getTime())) return;
              var range=this._periodRange();range[key]=value;
              if (range.end<=range.start || range.start>new Date()) { input.setCustomValidity(t("Choose a past start and a later end"));input.reportValidity();return; }
              input.setCustomValidity("");this._customStart=range.start;this._customEnd=range.end;
              this._zoom=1;this._panMs=0;this._loadDetail();
            };
            bar.appendChild(input);
          });
        }
      }
      var refresh = el("button", BTN, t("↻ Refresh")); refresh.onclick=()=>this._refreshCurrent();
      refresh.title=t("Refresh current data");bar.appendChild(refresh);bar.appendChild(languageSettings(this));
      return bar;
    }

    _renderOverview() {
      var wrap=el("div"), head=named(el("div"),"mm-pagehead"), title=el("div");
      title.appendChild(named(el("div",null,t("WORKSHOP OVERVIEW")),"mm-caption"));
      title.appendChild(named(el("div",null,t("Your machines, at a glance.")),"mm-title"));
      var online=this._machines.filter(m=>!m.offline).length;
      title.appendChild(named(el("div",{marginTop:"9px"},this._machines.length+t(" machines · ")+online+t(" online · Today's activity")),"mm-subtle"));head.appendChild(title);
      var sortSel=el("select",SEL);sortSel.setAttribute("aria-label",t("Sort machines"));
      [["name",t("Name")],["state",t("State")],["work",t("Work time")],["idle",t("Idle time")],["activity",t("Last activity")]].forEach(o=>{
        var opt=el("option",null,t("Sort: ")+o[1]);opt.value=o[0];opt.selected=o[0]===this._sort;sortSel.appendChild(opt);
      });
      sortSel.onchange=()=>{this._sort=sortSel.value;this._dirty=true;this._render();};head.appendChild(sortSel);wrap.appendChild(head);
      var grid=named(el("div"),"mm-fleet-grid");
      this._machines.slice().sort(MACHINE_SORTS[this._sort]||MACHINE_SORTS.name).forEach(m=>grid.appendChild(this._renderMachineRow(m)));
      wrap.appendChild(grid);return wrap;
    }

    _renderMachineRow(m) {
      var row=named(el("button",BTN),"mm-machine-tile");row.style.setProperty("--machine-color",m.offline?"#8c97a3":m.state_color||"var(--mm-accent)");
      row.setAttribute("aria-label",t("Open ")+m.name);row.onclick=()=>this._select(m.machine_id);
      var head=named(el("div"),"mm-tile-head");head.appendChild(el("strong",null,m.name));head.appendChild(el("span",{color:"var(--mm-muted)",fontSize:"20px"},"↗"));row.appendChild(head);
      if(m.description)row.appendChild(named(el("div",null,m.description),"mm-subtle"));
      var state=named(el("div"),"mm-tile-state"),pill=named(el("span",{color:m.state_color||"inherit"}),"mm-pill");
      pill.appendChild(named(el("span"),"mm-dot"));pill.appendChild(el("span",null,m.offline?t("Offline"):semanticLabel(m.state,m.state_label)));state.appendChild(pill);
      state.appendChild(named(el("span",null,m.offline?t("Last seen ")+fmtClock(m.last_seen):fmtDuration(m.state_duration)),"mm-subtle"));row.appendChild(state);
      var stats=named(el("div"),"mm-tile-stats");
      [[t("Work"),fmtDuration(m.work_seconds)],[t("Non-work"),fmtDuration(m.idle_seconds)],[t("Work share"),Number(m.work_percent||0).toFixed(1)+"%"]].forEach(item=>{
        var cell=el("div");cell.appendChild(named(el("span",null,item[0]),"mm-subtle"));cell.appendChild(el("strong",null,item[1]));stats.appendChild(cell);
      });row.appendChild(stats);
      var meter=named(el("div"),"mm-meter");meter.appendChild(el("span",{width:Math.max(0,Math.min(100,m.work_percent||0))+"%",background:"var(--mm-accent)"}));row.appendChild(meter);
      return row;
    }

    _setWorkspace(value, focusTab=false) {
      if(focusTab)this._focusTab=value;
      this._workspace=value;
      if(value==="reports")this._reportOpen=true;
      this._dirty=true;this._render();
    }

    _renderWorkspaceNav() {
      var nav=named(el("div"),"mm-tabs");nav.setAttribute("role","tablist");nav.setAttribute("aria-label",t("Machine workspace"));
      [["monitor",t("Monitor")],["reports",t("Reports")],["diagnostics",t("Diagnostics")]].forEach(item=>{
        var button=el("button",BTN,item[1]);button.id="mm-tab-"+item[0];button.setAttribute("role","tab");
        button.tabIndex=this._workspace===item[0]?0:-1;
        button.setAttribute("aria-selected",String(this._workspace===item[0]));button.setAttribute("aria-controls","mm-panel-"+item[0]);
        button.onclick=()=>this._setWorkspace(item[0],true);
        button.onkeydown=event=>{
          var keys=["monitor","reports","diagnostics"],index=keys.indexOf(item[0]);
          if(event.key==="ArrowRight")index=(index+1)%3;
          else if(event.key==="ArrowLeft")index=(index+2)%3;
          else if(event.key==="Home")index=0;else if(event.key==="End")index=2;else return;
          event.preventDefault();this._setWorkspace(keys[index],true);
        };
        nav.appendChild(button);
      });return nav;
    }

    _renderKPIs(d) {
      var st=d.stats||{},total=(st.work_seconds||0)+(st.idle_seconds||0),range=d.input_timeline||{};
      var seconds=Math.max(0,(new Date(range.end)-new Date(range.start))/1000),offline=st.offline_seconds||0;
      var grid=named(el("div"),"mm-kpis");
      [[t("Productive time"),fmtDuration(st.work_seconds),total?(st.work_seconds/total*100).toFixed(1)+t("% of included known time"):t("No included known time")],
       [t("Non-productive time"),fmtDuration(st.idle_seconds),t("Idle and other non-work states")],
       [t("Offline"),fmtDuration(offline),seconds?(offline/seconds*100).toFixed(1)+t("% of selected period"):t("Unknown machine activity")],
       [t("Downtimes"),String((st.downtime||{}).count||0),t("Longest ")+fmtDuration((st.downtime||{}).longest_seconds)]].forEach(item=>{
        var tile=named(el("div"),"mm-kpi");tile.appendChild(named(el("div",null,item[0]),"mm-subtle"));tile.appendChild(named(el("div",null,item[1]),"mm-kpi-value"));tile.appendChild(el("small",null,item[2]));grid.appendChild(tile);
      });return grid;
    }

    _renderMachine() {
      var d=this._detail;
      if(!d)return named(el("div",null,t("Loading machine activity…")),"mm-empty");
      var wrap=el("div"),hero=named(el("div"),"mm-hero"),name=named(el("div"),"mm-hero-name");
      name.appendChild(named(el("div",null,t("MACHINE WORKSPACE")),"mm-caption"));name.appendChild(named(el("div",null,d.name||t("Machine")),"mm-title"));
      if(d.description)name.appendChild(named(el("div",null,d.description),"mm-description"));
      var live=named(el("span"),"mm-pill");live.appendChild(named(el("span",{color:(d.snapshot||{}).offline?"#8c97a3":"var(--mm-accent)"}),"mm-dot"));live.appendChild(el("span",null,(d.snapshot||{}).offline?t("Data unavailable"):t("Monitoring online")));name.appendChild(live);
      hero.appendChild(name);hero.appendChild(this._renderCurrentStatus(d));wrap.appendChild(hero);wrap.appendChild(this._renderWorkspaceNav());
      var monitor=el("div"),reports=el("div"),diagnostics=el("div");
      [["monitor",monitor],["reports",reports],["diagnostics",diagnostics]].forEach(pair=>{
        pair[1].id="mm-panel-"+pair[0];pair[1].setAttribute("role","tabpanel");pair[1].setAttribute("aria-labelledby","mm-tab-"+pair[0]);pair[1].hidden=this._workspace!==pair[0];
      });
      monitor.appendChild(this._renderKPIs(d));
      var flow=this._renderRealFlow(d);flow.appendChild(this._renderInputFilters(d));monitor.appendChild(flow);
      var lower=named(el("div"),"mm-lower-grid");lower.appendChild(this._renderInputSummary(d));lower.appendChild(this._renderStats(d));monitor.appendChild(lower);
      monitor.appendChild(this._renderEvents(d));reports.appendChild(this._renderReports(d));
      diagnostics.appendChild(heading(t("Machine diagnostics"),t("Storage and source details for investigating missing or unavailable data.")));
      diagnostics.appendChild(this._renderHistory(d));diagnostics.appendChild(this._renderSourceDiagnostics(d));
      wrap.appendChild(monitor);wrap.appendChild(reports);wrap.appendChild(diagnostics);return wrap;
    }

    _renderCurrentStatus(d) {
      var s = d.snapshot || {};
      var box = named(el("div", SECTION), "mm-status");
      box.appendChild(el("div", {
        fontSize: "11px", letterSpacing: "1.5px",
        color: "var(--secondary-text-color)", marginBottom: "6px" },
        t("CURRENT STATUS")));

      var line = el("div", {
        display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" });
      line.appendChild(el("span", {
        width: "14px", height: "14px", borderRadius: "50%",
        background: s.state_color || "#888", display: "inline-block" }));
      var stateLabel = el("span", {
        fontSize: "22px", fontWeight: "700",
        color: s.state_color || "inherit" },
        semanticLabel(s.state,s.state_label));
      stateLabel.className = "mm-status-name"; line.appendChild(stateLabel);
      line.className = "mm-status-line";

      var duration = el("span", {
        fontSize: "15px", color: "var(--secondary-text-color)",
        fontFamily: "monospace" });
      duration.className = "mm-status-time";
      this._liveNode = duration;
      this._liveSince = s.state_since ? new Date(s.state_since).getTime() : Date.now();
      duration.textContent = hms((Date.now() - this._liveSince) / 1000);
      line.appendChild(duration);
      box.appendChild(line);

      if (s.offline) {
        var offLine = el("div", {
          fontSize: "12px", color: "var(--error-color, #f44336)",
          marginTop: "4px", fontFamily: "monospace" });
        offLine.appendChild(el("span", null, t("Offline for: ")));
        this._offlineNode = el("span");
        this._offlineSince = s.offline_since ?
          new Date(s.offline_since).getTime() : Date.now();
        this._offlineNode.textContent =
          hms((Date.now() - this._offlineSince) / 1000);
        offLine.appendChild(this._offlineNode);
        box.appendChild(offLine);
        var reason = s.offline_reason || {};
        var sources = reason.sources || [];
        if (sources.length) {
          box.appendChild(el("div", { marginTop: "6px", fontSize: "12px" }, t("Unavailable sources:")));
          sources.forEach(function (source) {
            box.appendChild(el("div", { fontSize: "12px", overflowWrap: "anywhere" },
              source.name + " / " + source.slot + " — " + source.entity_id + " = " +
              (source.ha_state == null ? t("missing") : source.ha_state) +
              (source.source_error === "own_entity" ? t(" (error: own Machine Monitor entity)") : "")));
          });
        } else if (reason.code) {
          box.appendChild(el("div", { fontSize: "12px" },
            reason.code === "monitoring_disabled" ? t("Monitoring disabled") : t("No enabled sources")));
        }
      }

      var meta = [];
      if (s.last_seen) meta.push(t("last seen ") + fmtClock(s.last_seen));
      if (s.recovered_at) meta.push(t("recovered ") + fmtClock(s.recovered_at));
      if (meta.length) {
        box.appendChild(el("div", {
          fontSize: "11px", color: "var(--secondary-text-color)",
          marginTop: "4px" }, meta.join(" | ")));
      }
      return box;
    }

    _renderStats(d) {
      var st = d.stats || {};
      var states = (st.states || []).filter(function (s) {
        return s.state !== "offline" && s.seconds > 0;
      });
      var box = named(el("div", SECTION), "mm-statistics");
      box.appendChild(el("div", {
        fontSize: "11px", letterSpacing: "1.5px",
        color: "var(--secondary-text-color)", marginBottom: "8px" },
        t("SEMANTIC STATISTICS")));

      var total = (st.work_seconds || 0) + (st.idle_seconds || 0);
      if (total > 0) {
        var bar = el("div", {
          display: "flex", height: "18px", borderRadius: "9px",
          overflow: t("hidden"), marginBottom: "10px" });
        states.forEach(function (s) {
          var segment=el("div", { width: (s.seconds / total * 100) + "%", background: s.color });
          segment.title=semanticLabel(s.state,s.label)+" "+fmtDuration(s.seconds);bar.appendChild(segment);
        });
        box.appendChild(bar);
      }

      var grid = el("div", {
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
        gap: "6px" });
      states.forEach(function (s) {
        var item = el("div", {
          display: "flex", alignItems: "center",
          justifyContent: "space-between", padding: "4px 8px",
          borderRadius: "6px", background: s.color + "1f",
          border: "1px solid " + s.color + "44" });
        var left = el("span", {
          fontSize: "12px", display: "flex", alignItems: "center", gap: "5px" });
        left.appendChild(el("span", {
          width: "8px", height: "8px", borderRadius: "2px",
          background: s.color, display: "inline-block" }));
        left.appendChild(el("span", null, semanticLabel(s.state,s.label)));
        item.appendChild(left);
        var pct = total > 0 ? (s.seconds / total * 100).toFixed(1) : "0.0";
        item.appendChild(el("span",
          { fontSize: "12px", fontWeight: "700" }, pct + "%"));
        grid.appendChild(item);
      });
      box.appendChild(grid);

      var foot = el("div", {
        fontSize: "12px", color: "var(--secondary-text-color)",
        marginTop: "8px", display: "flex", gap: "14px", flexWrap: "wrap" });
      foot.appendChild(el("span", null,
        t("Work ") + fmtDuration(st.work_seconds || 0)));
      foot.appendChild(el("span", null, t("Percentages: included known time ") + fmtDuration(total)));
      foot.appendChild(el("span", null,
        t("Idle ") + fmtDuration(st.idle_seconds || 0)));
      if (st.offline_seconds > 0) {
        foot.appendChild(el("span", null,
          t("Offline ") + fmtDuration(st.offline_seconds)));
      }
      if (this._downtime && this._downtime.count) {
        foot.appendChild(el("span", null,
          t("Downtimes ") + this._downtime.count +
          t(" (max ") + fmtDuration(this._downtime.longest_seconds) + ")"));
      }
      box.appendChild(foot);
      return box;
    }

    _renderRealFlow(d) {
      var data = d.input_timeline || { rows: [] };
      var rowsAll = data.rows || [];
      var range = this._viewRange();
      var self = this;
      var box = named(el("div", SECTION), "mm-flow");

      var toolbar = el("div", {
        display: "flex", alignItems: "center", gap: "6px",
        flexWrap: "wrap", marginBottom: "8px" });
      box.appendChild(el("div", {
        fontSize: "11px", letterSpacing: "1.5px",
        color: "var(--secondary-text-color)", width: "100%" }, "REAL FLOW"));

      [["detailed", t("Detailed")], ["compact", t("Compact")]].forEach(function (m) {
        var b = el("button", Object.assign({}, BTN, {
          fontWeight: self._mode === m[0] ? "700" : "400",
          borderColor: self._mode === m[0] ?
            "var(--primary-color)" : "var(--divider-color)" }), m[1]);
        b.setAttribute("aria-pressed", String(self._mode === m[0]));
        b.onclick = function () { self._setMode(m[0]); };
        toolbar.appendChild(b);
      });

      var sortSel = el("select", Object.assign({}, SEL, { width: "auto" }));
      ROW_SORTS.forEach(function (o) {
        var opt = el("option", null, t(o[1]));
        opt.value = o[0];
        if (o[0] === self._rowSort) opt.selected = true;
        sortSel.appendChild(opt);
      });
      sortSel.setAttribute("aria-label", t("Real Flow row order"));
      sortSel.onchange = function () { self._setRowSort(sortSel.value); };
      toolbar.appendChild(sortSel);

      toolbar.appendChild(el("div", { flex: "1" }));

      var self2 = this;
      var minus = el("button", BTN, t("Zoom -"));
      minus.onclick = function () { self2._zoomOut(); };
      var plus = el("button", BTN, t("Zoom +"));
      plus.onclick = function () { self2._zoomIn(); };
      var nowB = el("button", BTN, t("Now"));
      nowB.onclick = function () { self2._jumpNow(); };
      var left = el("button", BTN, "<");
      left.onclick = function () { self2._panLeft(); };
      var right = el("button", BTN, ">");
      right.onclick = function () { self2._panRight(); };
      [left, minus, plus, right, nowB].forEach(function (b) {
        toolbar.appendChild(b);
      });
      toolbar.className = "mm-flow-toolbar";
      box.appendChild(toolbar);

      box.children[0].className = "mm-flow-title";
      box.appendChild(named(el("div", null, t("Independent physical signals · ") + fmtDateTime(range.start) + " — " + fmtDateTime(range.end)), "mm-flow-subtitle"));
      var axis = el("div", {
        display: "flex", justifyContent: "space-between",
        fontSize: "10px", color: "var(--secondary-text-color)",
        marginBottom: "3px", paddingLeft: "96px" });
      var i;
      for (i = 0; i <= 6; i++) {
        axis.appendChild(el("div", {left: (i / 6 * 100) + "%"}, (range.span > 172800000 ? function(value) { return new Date(value).toLocaleDateString(language(),{month:"short",day:"numeric"}); } : fmtClock)(
          new Date(range.start.getTime() + range.span * i / 6).toISOString())));
      }
      axis.className = "mm-flow-axis";
      box.appendChild(axis);

      if (!rowsAll.length) {
        box.appendChild(el("div", {
          fontSize: "12px", color: "var(--secondary-text-color)",
          padding: "8px 0" }, t("No physical inputs configured.")));
        return box;
      }

      var rows = rowsAll.slice();
      var order = data.row_order || [];
      var pos = {};
      order.forEach(function (slot, idx) { pos[slot] = idx; });
      rows.sort(function (a, b) {
        var pa = typeof pos[a.slot] === "number" ? pos[a.slot] : 999;
        var pb = typeof pos[b.slot] === "number" ? pos[b.slot] : 999;
        if (pa !== pb) return pa - pb;
        return a.slot.localeCompare(b.slot);
      });

      if (this._rowSort === "name") {
        rows.sort(function (a, b) { return a.name.localeCompare(b.name); });
      } else if (this._rowSort === "duration") {
        rows.sort(function (a, b) { return (b.on_seconds || 0) - (a.on_seconds || 0); });
      } else if (this._rowSort === "activations") {
        rows.sort(function (a, b) { return (b.activations || 0) - (a.activations || 0); });
      } else if (this._rowSort === "last") {
        rows.sort(function (a, b) {
          return String(b.last_activity || "").localeCompare(
            String(a.last_activity || ""));
        });
      }

      rows = rows.filter(function (r) { return self._visible[r.slot] !== false; });
      var rowsBox = el("div", { position: "relative" });

      var offline = d.offline_periods || [];
      function addOffline(track) {
        offline.forEach(function (op) {
          var clipped = clipInterval(op);
          if (!clipped) return;
          var band = el("div", {
            position: "absolute", top: "0", bottom: "0",
            left: clipped.left + "%",
            width: clipped.width + "%",
            background: "repeating-linear-gradient(45deg, #9e9e9e99 0 6px, #9e9e9e55 6px 12px)",
            border: "1px dashed #9e9e9e", boxSizing: "border-box", zIndex: "3"
          });
          band.title = t("OFFLINE (unavailable)\nStart: ") + fmtDateTime(op.start) +
            t("\nEnd: ") + (op.open ? t("NOW") : fmtDateTime(op.end)) +
            t("\nDuration: ") + fmtDuration(op.duration);
          track.appendChild(band);
        });
      }

      function clipInterval(iv) {
        var startMs = new Date(iv.start).getTime();
        // Null end is only legitimate for an open interval; never treat null as epoch.
        var endMs = iv.end == null && iv.open ? Date.now() : new Date(iv.end).getTime();
        if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return null;
        var s = Math.max(startMs, range.start.getTime());
        var e = Math.min(endMs, Date.now(), range.end.getTime());
        return e > s ? { left: (s - range.start.getTime()) / range.span * 100,
                         width: (e - s) / range.span * 100 } : null;
      }

      var rowH = 20;
      var compact = this._mode === "compact";

      if (compact) {
        // One shared horizontal band; each slot keeps its own colour and a
        // small vertical offset so simultaneous inputs stay distinguishable.
        var track = el("div", {
          flex: "1 1 0", position: "relative", height: "34px",
          background: "var(--divider-color)", borderRadius: "5px",
          overflow: t("hidden"), cursor: "crosshair" });
        track.className = "mm-flow-track mm-flow-compact";
        addOffline(track);
        rows.forEach(function (r, idx) {
          (r.intervals || []).forEach(function (iv) {
            var clipped = clipInterval(iv);
            if (!clipped) return;
            var leftPct = clipped.left;
            var widthPct = clipped.width;
            var bar = el("div", {
              position: "absolute", left: leftPct + "%",
              width: widthPct + "%",
              top: (2 + (idx % 4) * 7) + "px", height: "6px",
              zIndex: "4", background: r.color, borderRadius: "2px", opacity: "0.95" });
            bar.tabIndex=0;bar.setAttribute("role","button");
            bar._inputColor = r.color;
            bar.title = t("Input: ") + r.name + t("\nState: ON\nStart: ") +
              fmtDateTime(iv.observed_start || iv.start) + t("\nEnd: ") + (iv.open ? t("NOW") : fmtDateTime(iv.end)) +
              t("\nDuration: ") + fmtDuration(iv.duration);
            bar.setAttribute("aria-label",bar.title);
            track.appendChild(bar);
          });
        });
        var compactRow = el("div", ROW, null);
        compactRow.appendChild(el("div", {
          flex: "0 0 90px", fontSize: "11px", fontWeight: "600" },
          t("All inputs")));
        compactRow.className = "mm-flow-row";
        compactRow.children[0].className = "mm-flow-label";
        compactRow.appendChild(track);
        rowsBox.appendChild(compactRow);
      } else {
        rows.forEach(function (r) {
          var row = el("div", {
            display: "flex", alignItems: "center", gap: "6px",
            height: rowH + "px", marginBottom: "2px",
            position: "relative", zIndex: "4" });
          var label = el("div", {
            flex: "0 0 90px", fontSize: "11px", fontWeight: "600",
            color: r.color, overflow: t("hidden"),
            textOverflow: "ellipsis", whiteSpace: "nowrap",
            display: "flex", alignItems: "center", gap: "4px" });
          label.appendChild(el("span", {
            width: "7px", height: "7px", borderRadius: "2px",
            background: r.color, display: "inline-block",
            flex: "0 0 7px" }));
          label.appendChild(el("span", null, r.name));
          label.title = r.name; label.className = "mm-flow-label";
          row.className = "mm-flow-row";
          row.appendChild(label);

          var track2 = el("div", {
            flex: "1 1 0", position: "relative", height: "14px",
            background: "var(--divider-color)", borderRadius: "4px",
            overflow: t("hidden"), cursor: "crosshair" });

          track2.className = "mm-flow-track";
          addOffline(track2);
          (r.intervals || []).forEach(function (iv) {
            var clipped = clipInterval(iv);
            if (!clipped) return;
            var leftPct = clipped.left;
            var widthPct = clipped.width;
            var bar = el("div", {
              position: "absolute", left: leftPct + "%",
              width: widthPct + "%", top: "1px", bottom: "1px",
              zIndex: "4", background: r.color, borderRadius: "2px", opacity: "0.9" });
            bar.tabIndex=0;bar.setAttribute("role","button");
            bar._inputColor = r.color;
            bar.title = t("Input: ") + r.name + t("\nState: ON\nStart: ") +
              fmtDateTime(iv.observed_start || iv.start) + t("\nEnd: ") + (iv.open ? t("NOW") : fmtDateTime(iv.end)) +
              t("\nDuration: ") + fmtDuration(iv.duration);
            bar.setAttribute("aria-label",bar.title);
            track2.appendChild(bar);
          });

          row.appendChild(track2);
          rowsBox.appendChild(row);
        });
      }

      var nowPct = (Date.now() - range.start.getTime()) / range.span * 100;
      if (nowPct >= 0 && nowPct <= 100) {
        var marker = el("div", {
          position: "absolute", top: "0", bottom: "0",
          left: "calc(96px + (100% - 96px) * " + (nowPct / 100) + ")",
          width: "2px", background: "#f44336", opacity: "0.8",
          pointerEvents: "none", zIndex: "6" });
        marker.className = "mm-now"; marker.style.setProperty("--now-ratio", String(nowPct / 100));
        rowsBox.appendChild(marker);
      }

      if (!rows.length) {
        var offlineRow = el("div", ROW);
        offlineRow.appendChild(el("div", { flex: "0 0 90px", fontSize: "11px" }, t("Availability")));
        var offlineTrack = el("div", { flex: "1 1 0", position: "relative", height: "20px", overflow: t("hidden") });
        addOffline(offlineTrack);
        offlineRow.className = "mm-flow-row";offlineRow.children[0].className = "mm-flow-label";offlineTrack.className = "mm-flow-track";
        offlineRow.appendChild(offlineTrack);
        rowsBox.appendChild(offlineRow);
        box.appendChild(el("div", {
          fontSize: "12px", color: "var(--secondary-text-color)",
          padding: "8px 0" }, t("All inputs are hidden by the filter.")));
      }

      box.appendChild(rowsBox);
      box.appendChild(this._renderNavigator());
      var history = d.history || {};
      if (history.available_from && new Date(data.start) < new Date(history.available_from)) {
        box.appendChild(el("div", { fontSize: "12px", marginTop: "6px" }, t("History available from: ") + fmtDateTime(history.available_from)));
      }

      var tipEl = tip();
      function showTip(ev) {
        var target=ev.target;
        if(!target || !target.title){tipEl.style.display="none";return;}
        var rect=target.getBoundingClientRect(),x=Number.isFinite(ev.clientX)?ev.clientX:rect.left,
            y=Number.isFinite(ev.clientY)?ev.clientY:rect.bottom;
        tipEl.style.display="block";tipEl.style.whiteSpace="pre-line";
        tipEl.style.left=Math.max(8,Math.min(window.innerWidth-278,x+14))+"px";
        tipEl.style.top=Math.max(8,Math.min((window.innerHeight||800)-180,y+14))+"px";
        tipEl.style.borderLeft="4px solid "+(target._inputColor||"#9e9e9e");tipEl.textContent=target.title;
      }
      rowsBox.addEventListener("mousemove",showTip);
      rowsBox.addEventListener("click",showTip);
      rowsBox.addEventListener("keydown",function(event){
        if(event.key==="Escape")tipEl.style.display="none";
        else if(event.key==="Enter"||event.key===" "){event.preventDefault();showTip(event);}
      });
      rowsBox.addEventListener("focusout",function(){tipEl.style.display="none";});
      rowsBox.addEventListener("mouseleave",function(){tipEl.style.display="none";});

      return box;
    }

    _renderInputFilters(d) {
      var rows = (d.input_timeline && d.input_timeline.rows) || [];
      var self = this;
      if (!rows.length) return el("div", {}, null);
      var box = named(el("div", SECTION), "mm-filters");
      box.appendChild(el("div", {
        fontSize: "11px", letterSpacing: "1.5px",
        color: "var(--secondary-text-color)", marginBottom: "6px" },
        t("INPUT FILTERS")));

      var all = el("button", BTN, t("All"));
      all.onclick = function () { self._allVisible(true); };
      var none = el("button", BTN, t("None"));
      none.onclick = function () { self._allVisible(false); };
      var wrap = el("div", {
        display: "flex", flexWrap: "wrap", gap: "6px",
        alignItems: "center" });
      wrap.appendChild(all);
      wrap.appendChild(none);

      rows.forEach(function (r) {
        var active = self._visible[r.slot] !== false;
        var chip = el("button", {
          display: "inline-flex", alignItems: "center", gap: "5px",
          padding: "3px 10px", borderRadius: "12px", fontSize: "12px",
          cursor: "pointer",
          border: "1px solid " + r.color + (active ? "" : "33"),
          background: active ? r.color + "26" : "transparent",
          color: active ? r.color : "var(--secondary-text-color)",
          opacity: active ? "1" : "0.5" });
        chip.appendChild(el("span", {
          width: "8px", height: "8px", borderRadius: "2px",
          background: r.color, display: "inline-block" }));
        chip.appendChild(el("span", null, r.name));
        chip.setAttribute("aria-pressed", String(active));
        chip.setAttribute("aria-label", (active ? t("Hide ") : t("Show ")) + r.name + t(" in Real Flow"));
        chip.onclick = function () { self._toggleVisible(r.slot); };
        wrap.appendChild(chip);
      });
      box.appendChild(wrap);
      return box;
    }

    _renderHistory(d) {
      var h=d.history||{},box=el("details",SECTION);
      box.open=this._historyOpen == null ? this._workspace === "diagnostics" : this._historyOpen;
      box.ontoggle=()=>{if(box.isConnected)this._historyOpen=box.open;};
      box.appendChild(el("summary",null,t("HISTORY STORAGE")));
      var grid=named(el("div"),"mm-storage-grid");
      [[t("Retention:"),(h.retention_days||30)+t(" days")],[t("Persistent file:"),h.size_bytes==null?t("Not yet available"):h.size_bytes.toLocaleString(language())+t(" bytes")],
       [t("Oldest record:"),fmtDateTime(h.oldest_record)],[t("Newest record:"),fmtDateTime(h.newest_record)],
       [t("Physical intervals:"),String(h.physical_intervals||0)],[t("Semantic intervals:"),String(h.semantic_intervals||0)]].forEach(item=>{
        var tile=named(el("div"),"mm-storage-item");tile.appendChild(named(el("div",null,item[0]),"mm-subtle"));tile.appendChild(el("strong",null,item[1]));grid.appendChild(tile);
      });box.appendChild(grid);
      box.appendChild(named(el("div",{marginTop:"16px"},t("Change retention and shifts in Settings > Devices & services > Machine Monitor > Configure > Machine settings.")),"mm-subtle"));
      return box;
    }

    async _loadReports() {
      var dates = this._reportDates, payload = { machine_id: this._selected };
      try {
        ["start", "end", "compare_start", "compare_end"].forEach(function (key) {
          if (dates[key]) payload[key] = new Date(dates[key]).toISOString();
        });
        if (!payload.start || !payload.end || new Date(payload.start) >= new Date(payload.end)) throw new Error(t("Choose a valid period A"));
        if (Boolean(payload.compare_start) !== Boolean(payload.compare_end)) throw new Error(t("Choose both dates for period B"));
        var request = ++this._reportRequest, machineId = this._selected;
        this._reportBusy = true; this._reportError = null;
        this._dirty = true; this._render();
        var result = await this._callWs("machine_monitor/reports", payload);
        if (request !== this._reportRequest || machineId !== this._selected) return;
        this._report = result;
      } catch (error) {
        if (request && request !== this._reportRequest) return;
        this._reportError = error.message;
      } finally {
        if (!request || request === this._reportRequest) { this._reportBusy = false; this._dirty = true; this._render(); }
      }
    }

    _renderReports(d) {
      var self = this, box = el("details", SECTION);
      box.open = this._reportOpen;
      box.ontoggle = function () { if (box.isConnected) self._reportOpen = box.open; };
      box.appendChild(el("summary", { cursor: "pointer" }, t("REPORTS — ") + d.name));
      box.appendChild(el("div", { fontSize: "12px", margin: "8px 0" }, t("Select local dates for period A and optional comparison B. Reports are calculated when requested.")));
      var range = this._periodRange(), controls = el("div", { display: "flex", flexWrap: "wrap", gap: "8px" });
      [["start", t("Period A · From")], ["end", t("Period A · To")], ["compare_start", t("Period B · From (optional)")], ["compare_end", t("Period B · To (optional)")]].forEach(function (item) {
        var key = item[0], label = el("label", { fontSize: "12px" }, item[1] + " ");
        if (!(key in self._reportDates)) {
          var dt = key === "start" ? range.start : key === "end" ? range.end : null;
          self._reportDates[key] = dt ? new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "";
        }
        var input = el("input", SEL); input.type = "datetime-local"; input.value = self._reportDates[key]; input.setAttribute("aria-label", item[1]);
        input.onchange = function () { self._reportDates[key] = input.value; };
        label.appendChild(input); controls.appendChild(label);
      });
      controls.className = "mm-report-controls";
      var run = named(el("button", BTN, this._reportBusy ? t("Calculating...") : t("Generate report / compare")), "mm-primary");
      run.disabled = Boolean(this._reportBusy);
      run.onclick = function () { self._loadReports(); };
      controls.appendChild(run); box.appendChild(controls);
      if (this._reportError) box.appendChild(el("div", { color: "var(--error-color)" }, translatedError(this._reportError)));
      var report = this._report;
      if (!report) return box;
      var reportTarget = box;
      function table(title, rows) {
        var section = named(el("div", { marginTop: "12px", overflowX: "auto" }), "mm-report-table");
        section.appendChild(el("div", { fontWeight: "600", marginBottom: "5px" }, title));
        var grid = el("table", { width: "100%", fontSize: "12px", borderCollapse: "collapse" });
        rows.forEach(function (cells) {
          var row = el("tr");
          cells.forEach(function (cell) { row.appendChild(el("td", { padding: "4px", borderBottom: "1px solid var(--divider-color)" }, cell)); });
          grid.appendChild(row);
        });
        section.appendChild(grid); reportTarget.appendChild(section);
      }
      var metricLabels = { total_seconds: t("Total period"), known_seconds: t("Known monitored time"), offline_seconds: t("Offline"), unrecorded_seconds: t("Unrecorded / unknown"), work_seconds: t("Productive time"), idle_seconds: t("Idle"), work_percent: t("Work share"), idle_percent: t("Idle share"), offline_percent: t("Offline share"), work_cycles: t("Work cycles"), downtime_count: t("Downtimes"), longest_work_seconds: t("Longest work"), longest_idle_seconds: t("Longest idle"), longest_downtime_seconds: t("Longest downtime") };
      function metric(key, value) { return key.endsWith("seconds") ? fmtDuration(value) : key.endsWith("percent") ? value + "%" : String(value); }
      if (report.comparison) table(t("B versus A"), [[t("Metric"), "A", "B", t("Change")]].concat(report.comparison.map(function (m) { return [metricLabels[m.metric] || m.metric.replace(/_/g, " "), metric(m.metric, m.a), metric(m.metric, m.b), m.change == null ? t("N/A (A = 0)") : (m.change > 0 ? "+" : "") + m.change + " " + t(m.unit)]; })));
      var periods = named(el("div"), report.b ? "mm-report-periods" : "mm-report-periods mm-single-period");
      box.appendChild(periods);
      ["a", "b"].forEach(function (key) {
        var r = report[key]; if (!r) return;
        reportTarget = named(el("div"), "mm-report-period");periods.appendChild(reportTarget);
        var metrics = ["total_seconds", "known_seconds", "offline_seconds", "unrecorded_seconds", "work_seconds", "idle_seconds", "work_percent", "idle_percent", "offline_percent", "work_cycles", "downtime_count", "longest_work_seconds", "longest_idle_seconds", "longest_downtime_seconds"];
        table(t("Period ") + key.toUpperCase() + " — " + fmtDateTime(r.start) + " – " + fmtDateTime(r.end), metrics.map(function (m) { return [metricLabels[m] || m.replace(/_/g, " "), metric(m, r[m] || 0)]; }));
        table(t("Semantic states ") + key.toUpperCase(), Object.keys(r.states).map(function (state) { return [semanticLabel(state), fmtDuration(r.states[state])]; }));
        table(t("Physical inputs ") + key.toUpperCase(), [[t("Input"), t("ON time"), t("Activations")]].concat(r.inputs.map(function (input) { return [input.name, fmtDuration(input.on_seconds), input.activations]; })));
        var h = report.history || {};
        if (h.available_from && new Date(r.start) < new Date(h.available_from)) box.appendChild(el("div", null, t("History available from: ") + fmtDateTime(h.available_from)));
      });
      reportTarget = box;
      box.appendChild(el("div", { fontSize: "12px", marginTop: "8px" }, t("Work/idle %: known time included in statistics. Offline %: full period. Unrecorded time is unknown. Physical inputs can overlap; their totals need not sum to the period. Cycles count work starts inside the period.")));
      table(t("Shifts — period A — ") + report.timezone, [[t("Shift"), t("Known"), t("Work"), t("Idle"), t("Offline"), t("Work %"), t("Idle %"), t("Downtimes")]].concat(report.shifts.map(function (r) { return [r.name, fmtDuration(r.known_seconds), fmtDuration(r.work_seconds), fmtDuration(r.idle_seconds), fmtDuration(r.offline_seconds), r.work_percent + "%", r.idle_percent + "%", r.downtime_count]; })));
      if (!report.shifts.length) box.appendChild(el("div", null, t("Configure shifts in Machine settings: Name | HH:MM | HH:MM, one per line. Overnight shifts are supported.")));
      return box;
    }

    _renderSourceDiagnostics(d) {
      var box = el("details", SECTION);
      box.open = this._sourceOpen == null ? this._workspace === "diagnostics" : this._sourceOpen;
      box.ontoggle = () => { if (box.isConnected) this._sourceOpen = box.open; };
      box.appendChild(el("summary", { cursor: "pointer", fontSize: "12px" }, t("SOURCE DIAGNOSTICS")));
      (d.source_diagnostics || []).forEach(function (source) {
        var line = named(el("div", { marginTop: "8px", fontSize: "12px", overflowWrap: "anywhere" }), "mm-diagnostic-row");
        line.appendChild(el("div", null, source.slot + " / " + source.name + " — " + source.entity_id));
        line.appendChild(el("div", null, t("Semantic: ") + semanticLabel(source.semantic_state) +
          " | HA: " + (source.ha_state == null ? t("missing") : source.ha_state) +
          t(" | Available: ") + (source.available ? t("yes") : t("no")) +
          t(" | Physical: ") + (source.physical_on == null ? t("UNKNOWN") : source.physical_on ? t("ON") : t("OFF")) +
          t(" | Enabled: ") + (source.enabled ? t("yes") : t("no")) +
          t(" | Real Flow in profile: ") + (source.show_in_timeline === false ? t("hidden") : t("visible"))));
        line.appendChild(el("div", null, t("Last state change: ") +
          (source.last_changed ? fmtDateTime(source.last_changed) : t("unknown")) +
          (source.source_error ? t(" | Error: ") + source.source_error : "")));
        box.appendChild(line);
      });
      return box;
    }

    _renderInputSummary(d) {
      var rows = (d.input_timeline && d.input_timeline.rows) || [];
      var box = named(el("div", SECTION), "mm-summary");
      box.appendChild(el("div", {
        fontSize: "11px", letterSpacing: "1.5px",
        color: "var(--secondary-text-color)", marginBottom: "6px" },
        t("PHYSICAL INPUTS")));
      if (!rows.length) {
        box.appendChild(el("div", {
          fontSize: "12px", color: "var(--secondary-text-color)" },
          t("No inputs configured.")));
        return box;
      }
      rows.forEach(function (r) {
        var row = el("div", {
          display: "flex", alignItems: "center", gap: "8px",
          padding: "4px 0", fontSize: "12px",
          borderBottom: "1px solid var(--divider-color)" });
        row.className = "mm-summary-row";
        row.appendChild(el("span", {
          width: "9px", height: "9px", borderRadius: "2px",
          background: r.color, display: "inline-block" }));
        row.appendChild(el("div",
          { fontWeight: "600", flex: "1 1 0" }, r.name));
        var on = el("span", {
          padding: "2px 8px", borderRadius: "4px", fontSize: "11px",
          fontWeight: "700",
          background: r.on ? r.color + "33" : "var(--divider-color)",
          color: r.on ? r.color : "var(--secondary-text-color)" },
          r.available === false || r.on == null ? t("UNKNOWN") : (r.on ? t("ON") : t("OFF")));
        row.appendChild(on);
        row.appendChild(el("div", {
          fontFamily: "monospace", color: "var(--secondary-text-color)",
          flex: "0 0 76px", textAlign: "right" },
          fmtDuration(r.on_seconds)));
        row.appendChild(el("div", {
          color: "var(--secondary-text-color)", flex: "0 0 90px",
          textAlign: "right" },
          (r.activations || 0) + t(" act.")));
        row.children[3].className = "mm-input-time";
        row.children[4].className = "mm-activation";
        box.appendChild(row);
      });
      return box;
    }

    _renderEvents(d) {
      var events = (d.events || []).slice();
      events.sort(EVENT_SORT[this._eventSort] || EVENT_SORT.newest);
      var box = named(el("div", SECTION), "mm-events");
      var head = el("div", {
        display: "flex", alignItems: "center", marginBottom: "6px" });
      head.appendChild(el("div", {
        fontSize: "11px", letterSpacing: "1.5px",
        color: "var(--secondary-text-color)" }, t("SEMANTIC EVENTS")));
      head.appendChild(el("div", { flex: "1" }));
      var self = this;
      var sortSel = el("select", Object.assign({}, SEL, { width: "auto" }));
      [["newest", t("Newest first")], ["oldest", t("Oldest first")],
       ["longest", t("Longest first")], ["shortest", t("Shortest first")]]
        .forEach(function (o) {
          var opt = el("option", null, t(o[1]));
          opt.value = o[0];
          if (o[0] === self._eventSort) opt.selected = true;
          sortSel.appendChild(opt);
        });
      sortSel.onchange = function () {
        self._eventSort = sortSel.value;
        self._dirty = true;
        self._render();
      };
      head.appendChild(sortSel);
      box.appendChild(head);

      if (!events.length) {
        box.appendChild(el("div", {
          fontSize: "12px", color: "var(--secondary-text-color)" },
          t("No semantic events in this period.")));
        return box;
      }

      var list = named(el("div"), "mm-events-list");
      box.appendChild(list);
      var limit = this._config.max_events || 30;
      events.slice(0, limit).forEach(function (ev) {
        var row = el("div", {
          display: "flex", alignItems: "center", gap: "8px",
          padding: "4px 0", fontSize: "12px",
          borderBottom: "1px solid var(--divider-color)" });
        row.className = "mm-event-row";
        row.appendChild(el("div", {
          fontFamily: "monospace",
          color: "var(--secondary-text-color)", flex: "0 0 84px" },
          fmtClock(ev.start) + "-" + fmtClock(ev.end)));
        var state = el("div", {
          display: "flex", alignItems: "center", gap: "5px",
          flex: "1 1 0", fontWeight: "600",
          color: ev.color || "inherit" });
        state.appendChild(el("span", {
          width: "8px", height: "8px", borderRadius: "2px",
          background: ev.color, display: "inline-block" }));
        state.appendChild(el("span", null, semanticLabel(ev.state,ev.state_label)));
        row.appendChild(state);
        if (ev.input_name) {
          row.appendChild(el("div", {
            color: "var(--secondary-text-color)", flex: "1 1 0" },
            ev.input_name));
        }
        row.appendChild(el("div", {
          fontFamily: "monospace", flex: "0 0 70px", textAlign: "right" },
          fmtDuration(ev.duration)));
        if (ev.input_name) row.children[2].className = "mm-event-source";
        row.children[row.children.length-1].style.gridColumn = "-2 / -1";
        list.appendChild(row);
      });
      return box;
    }
  }


  class MachineMonitorMachineCard extends MachineMonitorCard {
    static getStubConfig() { return { type: "custom:machine-monitor-machine-card", period: "today", mode: "detailed", show_status: true, show_totals: true, show_offline: true }; }
    static getConfigElement() { return document.createElement("machine-monitor-machine-editor"); }
    setConfig(config) {
      var changed = this._selected !== config.machine_id;
      this._config = Object.assign({}, MachineMonitorMachineCard.getStubConfig(), config);
      this._period = this._config.period;
      this._mode = this._config.mode;
      this._selected = config.machine_id || null;
      this._view = "machine";
      this._loading = false;
      if (changed) { this._detail = null; this._visible = {}; }
      this._zoom = 1; this._panMs = 0; this._dirty = true; this._render();
      if (this._hass) this._refreshCurrent();
    }
    async _loadStates() {}
    async _refreshCurrent() {
      if (!this._hass || !this.isConnected || !this._selected) return;
      if (this._refreshing) { this._pendingRefresh = true; return; }
      this._refreshing = true;
      try {
        do { this._pendingRefresh = false; await this._loadDetail(); }
        while (this._pendingRefresh && this.isConnected);
      } finally { this._refreshing = false; }
    }
    _onMachineEvent(event) {
      if (!event || !event.data || !event.data.machine_id || event.data.machine_id === this._selected) this._scheduleRefresh();
    }
    _render() {
      if (!this._dirty) return;
      // Keep native date/selection controls alive while the user is editing.
      var active = this.shadowRoot.activeElement;
      if (active && active.tagName === "INPUT") return;
      if (active && active.id && active.id.startsWith("mm-tab-")) this._focusTab=active.id.slice(7);
      this._dirty = false;
      this.shadowRoot.innerHTML = "";
      this._liveNode = this._offlineNode = null;
      styledRoot(this.shadowRoot);
      this.setAttribute("lang",language());
      var card = named(el("ha-card", { padding: "12px", display: "block" }), "mm-card");
      this.shadowRoot.appendChild(card);
      if (!this._selected) { card.appendChild(el("div", null, t("Select a machine in the card editor."))); return; }
      if (this._error) card.appendChild(el("div", { color: "var(--error-color)" }, translatedError(this._error)));
      var d = this._detail;
      if (!d) { card.appendChild(el("div", null, t("Loading Machine Monitor..."))); return; }
      var name = named(el("div"), "mm-card-heading"); name.appendChild(el("strong", null, d.name));
      name.appendChild(named(el("span", null, t(PERIODS.find(p => p.id === this._period)?.label || this._period)), "mm-subtle"));card.appendChild(name);card.appendChild(languageSettings(this));
      if (this._config.show_status !== false) card.appendChild(this._renderCurrentStatus(d));
      var data = this._config.show_offline === false ? Object.assign({}, d, { offline_periods: [] }) : d;
      card.appendChild(this._renderRealFlow(data));
      if (this._config.show_totals !== false) card.appendChild(this._renderInputSummary(d));
    }
  }

  class MachineMonitorMachineEditor extends HTMLElement {
    connectedCallback() { languageViews.add(this); this._render(); }
    disconnectedCallback() { languageViews.delete(this); }
    constructor() { super(); this.attachShadow({ mode: "open" }); this._config = {}; this._machines = []; }
    setConfig(config) { this._config = Object.assign({}, MachineMonitorMachineCard.getStubConfig(), config); this._render(); }
    set hass(hass) {
      this._hass = hass;
      setHassLanguage(hass);
      if (this._connection === hass.connection) return;
      this._connection = hass.connection;
      hass.callWS({ type: "machine_monitor/overview" }).then(result => { this._machines = result.machines || []; this._error = null; this._render(); })
        .catch(error => { this._error = error.message; this._render(); });
    }
    _change(key, value) {
      this._config = Object.assign({}, this._config, { [key]: value });
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
    }
    _render() {
      this.shadowRoot.innerHTML = "";
      styledRoot(this.shadowRoot);
      this.setAttribute("lang",language());
      var root = named(el("div"), "mm-editor"), self = this;
      this.shadowRoot.appendChild(root);
      root.appendChild(languageSettings(this));
      root.appendChild(named(el("div", null, t("Choose a machine and make this card yours.")), "mm-editor-note"));
      if (this._error) root.appendChild(el("div", null, translatedError(this._error)));
      var choices = [
        ["machine_id", t("Machine"), [["", t("Select a machine")]].concat(this._machines.map(m => [m.machine_id, m.name]))],
        ["period", t("Period"), [["1h", t("1 h")], ["6h", t("6 h")], ["12h", t("12 h")], ["today", t("Today")], ["24h", t("24 h")]]],
        ["mode", t("Real Flow mode"), [["detailed", t("Detailed")], ["compact", t("Compact")]]]
      ];
      choices.forEach(function (field) {
        var label = el("label", { display: "block", margin: "12px 0" }, field[1] + " "), select = el("select", SEL);
        field[2].forEach(function (choice) { var o = el("option", null, choice[1]); o.value = choice[0]; o.selected = self._config[field[0]] === choice[0]; select.appendChild(o); });
        select.onchange = function () { self._change(field[0], select.value); };
        label.appendChild(select); root.appendChild(label);
      });
      [["show_status", t("Show current status")], ["show_totals", t("Show input totals")], ["show_offline", t("Show offline periods")]].forEach(function (field) {
        var label = el("label", { display: "block", margin: "12px 0" }), input = el("input");
        input.type = "checkbox"; input.checked = self._config[field[0]] !== false;
        input.onchange = function () { self._change(field[0], input.checked); };
        label.appendChild(input); label.appendChild(el("span", null, field[1])); root.appendChild(label);
      });
    }
  }
  if (!customElements.get("machine-monitor-machine-card")) customElements.define("machine-monitor-machine-card", MachineMonitorMachineCard);
  if (!customElements.get("machine-monitor-machine-editor")) customElements.define("machine-monitor-machine-editor", MachineMonitorMachineEditor);

  if (!customElements.get("machine-monitor-card")) {
    customElements.define("machine-monitor-card", MachineMonitorCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some(card => card.type === "machine-monitor-machine-card")) {
    window.customCards.push({ type: "machine-monitor-machine-card", name: "Machine Monitor", preview: true,
      description: "One machine: current status, physical Real Flow and input totals. Visual editor included." });
  }
  if (!window.customCards.some(function (card) { return card.type === "machine-monitor-card"; })) {
    window.customCards.push({
      type: "machine-monitor-card",
      name: "Machine Monitor — Full UI",
      preview: true,
      description: "Machine overview, physical Real Flow, statistics, input filters and events."
    });
  }
  localizeCardMetadata();
})();
