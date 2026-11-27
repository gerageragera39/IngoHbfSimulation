# Исследование совместимости маршрутов и платформ Ingolstadt Hauptbahnhof

## Резюме и методика

Для академической дискретно-событийной модели наиболее защищаемый подход — **не считать “топологически достижимый” путь автоматически разрешённым**, а строить GREEDY-совместимость на пересечении трёх видов доказательств: актуальной инфраструктурной топологии, запланированного использования и подтверждённых фактических движений. Это особенно важно для Ingolstadt Hbf, поскольку публичный DB InfraGO/ISR-план показывает стрелочные соединения и физическую конфигурацию, но не публикует полный перечень сигнализованных Fahrstraßen, фланговой защиты, ограничений маршрутизации и эксплуатационных запретов. DB InfraGO прямо описывает ISR как инфраструктурный реестр с интерактивным картографическим представлением, а полный ISR Data Service является отдельным продуктом доступа. citeturn179682view1turn569452search3

Главный результат для исследуемых Gleise 2–5 следующий. Из исходных provisional assumptions хорошо подтверждаются **RB16_S = {2,3}** и **RB16_N = {4,5}**. Для **ICE_S** выбор только Gleis 3 слишком строг: в данных имеется реальное сквозное движение ICE 1009 через Gleis 2. Для **ICE_N** данные поддерживают Gleis 4, но не дают прямого подтверждения Gleis 5. Для **RE1_S** данные поддерживают Gleis 3, но не подтверждают 2 и 5 в рассматриваемом окне; для **RE1_N** подтверждён Gleis 4, но не 5. Для RB15 и RB17 важны отдельные физические коридоры: их нельзя объединять с северным 5501/5934 только по направлению движения.

Критически важно, что наблюдаемый период CSV приходится на **23–25 ноября 2026 года**, то есть внутрь полной модернизационной блокировки Schnellfahrstrecke Nürnberg–Ingolstadt с 30 октября по 12 декабря 2026 года. DB InfraGO указывает, что в это время RE1 перенаправляется через Treuchtlingen или Augsburg, а дальние поезда также работают по изменённым схемам. Поэтому содержимое `via` в ноябрьском OpenBoards-наборе нельзя безусловно считать репрезентативным для нормальной эксплуатации SFS 5934. citeturn728334search1

Загруженные файлы были доступны локально и фактически проанализированы. `all_station_calls(2).csv` содержит 280 строк и 280 уникальных `journey_id`; `all_events(2).csv` — 590 событий по 388 поездным путешествиям. Точных полных дублей нет; в `all_events` также нет повторов по ключу `(journey_id,event_kind)`, а поле `conflicting_duplicate` равно `False` во всех 590 строках. Из 590 событий 294 — arrivals и 296 — departures; 567 имеют `time_type=REAL`, 17 — `PREVIEW`, 6 — `SCHEDULE`. 21 событие помечено cancelled. `all_station_calls` содержит уже сопоставленные arrival/departure-пары и дополнительные производные признаки (`status`, `review_reason`, задержки, scheduled/reported platform и т. д.); 86 строк имеют `candidate`, 33 — `review`, 146 — `outside_service_scope`, 11 — `outside_platform_scope`.

## Инфраструктура станции и физические коридоры

Актуальная страница DB InfraGO по станции Ingolstadt Hbf на 23 ноября 2026 года указывает для исследуемых путей следующие **Nettobaulängen** и высоты: Gleis 2 — 409 м / 76 см, Gleis 3 — 409 м / 76 см, Gleis 4 — 419 м / 76 см, Gleis 5 — 419 м / 76 см. DB InfraGO специально предупреждает, что эти значения **не должны применяться для определения допустимой длины поезда**; для этого требуется Bahnsteignutzlänge, зависящая в том числе от расположения сигналов и доступная через Infrastrukturregister. citeturn569452search0turn901166search6

| Gleis | Nettobaulänge | Высота | Bahnsteignutzlänge | Вывод для модели |
|---|---:|---:|---|---|
| 2 | 409 м | 76 см | публично в открытой странице не дана | нельзя считать 409 м эксплуатационной полезной длиной |
| 3 | 409 м | 76 см | публично в открытой странице не дана | то же |
| 4 | 419 м | 76 см | публично в открытой странице не дана | то же |
| 5 | 419 м | 76 см | публично в открытой странице не дана | то же |

Текущий APN/ISR-план Ingolstadt Hbf показывает пассажирскую группу путей 1–7 и подходы VzG 5501, 5851, 5382 и 5381. В легенде станции на плане указаны направления München–Treuchtlingen, Regensburg, Donauwörth и Augsburg; сам актуальный графический материал имеет редакционную дату 20.08.2026, а PDF был сформирован/доступен 23.11.2026. citeturn637307view0turn345688view0

Физические коридоры для моделирования следует различать так:

| Коридор | VzG | Связь с MIH | Значение |
|---|---:|---|---|
| München — Ingolstadt — Treuchtlingen | 5501 | непосредственно проходит через Hbf и Ingolstadt Nord | основной север–юг |
| Nürnberg SFS — Ingolstadt Nord | 5934 | заканчивается/вливается в район Ingolstadt Nord, далее к Hbf движение идёт по 5501 | нормальный подход ICE/RE1 со стороны Nürnberg по SFS |
| Regensburg — Ingolstadt Hbf | 5851 | самостоятельный восточный подход к Hbf | RB17 и часть сквозных Donautal-рейсов |
| Donauwörth/Ulm — Ingolstadt Hbf | 5382 | самостоятельный западно-/юго-западный подход | RB15 |
| Augsburg — Ingolstadt Hbf | 5381 | отдельный подход | в исследуемых through-services играет меньшую роль |

На официальном/актуальном плане Hbf обозначены 5501 München–Treuchtlingen, 5851 Richtung Regensburg, 5382 Richtung Donauwörth и 5381 Richtung Augsburg. citeturn637307view0 На Ingolstadt Nord сходятся 5501 и SFS 5934; независимые отраслевые базы также показывают для Ingolstadt Nord VzG 5501 и 5934. citeturn901166search12turn901166search17

Следовательно, “Nürnberg” — это не одна физическая категория. В нормальном режиме ICE/RE1 Nürnberg используют SFS 5934 до Ingolstadt Nord и затем 5501 до Hbf, тогда как поезд через Treuchtlingen подходит к Hbf по 5501 с северной стороны. Во время ноябрьской блокировки SFS 2026 эта разница особенно существенна: DB InfraGO прямо сообщает об Umleitung RE1 через Treuchtlingen/Augsburg. citeturn728334search1

Для ICE длина платформы сама по себе также недостаточна. DB указывает 200 м для ICE 3, 346 м для стандартного 12-вагонного ICE 4 и 374 м для 13-вагонного ICE 4. Формально все эти значения меньше опубликованных Nettobaulängen 409/419 м, но DB InfraGO прямо запрещает использовать Nettobaulänge как замену Bahnsteignutzlänge; кроме того, фактическая пригодность зависит от состава, остановочной позиции, сигналов, PZB/LZB/ETCS и прочих эксплуатационных параметров. citeturn221208search0turn221208search4turn221208search31turn569452search0

## Анализ OpenBoards и фактическое использование платформ

`all_events(2).csv` представляет более низкий событийный уровень: каждая строка — arrival или departure с полями `scheduled_time`, `reported_time`, `time_type`, `scheduled_platform`, `reported_platform`, cancellation-флагами и исходным JSON. `all_station_calls(2).csv` является удобным агрегированным слоем: arrival и departure сведены в одну строку, добавлены planned platform, рассчитанные задержки, статус отбора и причины review. Поэтому для определения **сквозной фактической платформы** предпочтительным критерием было: origin и destination не равны Ingolstadt Hbf; оба события присутствуют; `time_type=REAL`; journey не cancelled; arrival и departure reported platform согласуются либо явно рассматриваются отдельно.

Из 280 station calls 147 являются сквозными по простому критерию `origin != Ingolstadt Hbf` и `destination != Ingolstadt Hbf`. Они распределяются как: ICE 43, RB16 45, RE1 в категории RE — 19, ещё 2 записи RE1 классифицированы источником как RB, RB17 — 34, RB15 — 4. BRB RB13/RB14 в этом наборе в основном относятся к начинающим/заканчивающимся в Hbf движениям и поэтому исключаются из текущего simulation scope.

### Эмпирическая матрица

| Route group | Направление | Planned 2–5 | REAL reported 2–5 | Существенное наблюдение |
|---|---|---|---|---|
| ICE_S | север → München | 3 | 3: 20, 2: 1 | ICE 1009 реально прошёл через Gleis 2 вместо scheduled 3 |
| ICE_N | München → север | 4 | 4: 19 | других 2–5 не наблюдалось |
| RE1_S | север/Treuchtlingen → München | 3 | 3: 6 | 2 и 5 не наблюдались |
| RE1_N | München → север/Treuchtlingen | 4 | 4: 8 | 5 не наблюдался |
| RB16_S | Treuchtlingen/Nürnberg → München | 2/3, также 1 | 3: 17, 2: 2, также 1 | многочисленные изменения 2→3 |
| RB16_N | München → Treuchtlingen/Nürnberg | 4/5, также 6/7 | 4: 15, 5: 5, также 7 | несколько 5/6/7→4 |
| RB15 Donau→Nord | Ulm/Donauwörth → Ingolstadt Nord | среди 2–5: 4 | 3: 1 | RB15 84275 scheduled 4, REAL 3 |
| RB15 Nord→Donau | обратное направление | нет квалифицирующего наблюдения на 2–5 | нет | UNKNOWN |
| RB17 Reg→Nord | Regensburg → Ingolstadt Nord | 5/6/7 | 5: 5, 2: 1, также 6/7 | RB17 84320 scheduled 6, REAL 2; 84322 7→5 |
| RB17 Nord→Reg | Ingolstadt Nord → Regensburg | преимущественно 5, также 6 | 5: 18, также 6 | Gleis 5 очень устойчив |

Пример ICE 1009 особенно важен: 24 ноября 2026 года он был scheduled на Gleis 3, но arrival и departure reported platform равны 2, оба события `REAL`, не cancelled. Это является сильным **OBSERVED** доказательством того, что хотя бы для этого конкретного поезда и текущей эксплуатационной конфигурации complete through movement через Gleis 2 состоялось. Оно не доказывает, что любой ICE любого состава и любого северного подхода может быть переназначен на 2.

Для RB16_S данные заметно сильнее provisional assumption: типичная схема в наборе — scheduled Gleis 2, но реальный переход на 3. Для RB16_N наблюдаются оба Gleis 4 и 5, причём Gleis 4 часто принимает поезда, запланированные на 5/6/7. Поэтому именно для RB16 заданные ранее множества {2,3} и {4,5} имеют наиболее хорошую эмпирическую основу.

Набор имеет существенное ограничение: он покрывает фактически около полутора суток и аномальный строительный период. Следовательно, отсутствие платформы в этом наборе **не является доказательством несовместимости**. Кроме того, `PREVIEW` не следует интерпретировать как фактическое движение, а cancelled-события — как доказательство использования пути.

## Инфраструктурная матрица доказательств

Статусы ниже относятся именно к исследуемым Gleise 2–5. **PLAUSIBLE** означает, что текущая схема путей не даёт очевидного топологического противоречия, но не публикует достаточной информации для утверждения о разрешённой сигнализованной Fahrstraße. Ни одна комбинация не помечена `INCOMPATIBLE`, потому что в найденных публичных документах нет явного запрета для рассматриваемой пары route/platform. Это методологически важнее, чем “дорисовывать” запреты из отсутствия наблюдений. APN подтверждает сложную систему стрелочных связей в обоих горловинах, но не является interlocking route table. citeturn345688view0turn179682view1

| Route group | Gleis 2 | Gleis 3 | Gleis 4 | Gleis 5 |
|---|---|---|---|---|
| ICE_S | PLAUSIBLE + OBSERVED | PLAUSIBLE + SCHEDULED + OBSERVED | PLAUSIBLE | PLAUSIBLE |
| ICE_N | PLAUSIBLE | PLAUSIBLE | PLAUSIBLE + SCHEDULED + OBSERVED | PLAUSIBLE |
| RE1_S | ASSUMED/PLAUSIBLE | SCHEDULED + OBSERVED | PLAUSIBLE | ASSUMED/PLAUSIBLE |
| RE1_N | PLAUSIBLE | PLAUSIBLE | SCHEDULED + OBSERVED | ASSUMED/PLAUSIBLE |
| RB16_S | SCHEDULED + OBSERVED | SCHEDULED + OBSERVED | PLAUSIBLE | PLAUSIBLE |
| RB16_N | PLAUSIBLE | PLAUSIBLE | SCHEDULED + OBSERVED | SCHEDULED + OBSERVED |
| RB15 Donau→Nord | UNKNOWN | OBSERVED | SCHEDULED | UNKNOWN |
| RB15 Nord→Donau | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| RB17 Reg→Nord | OBSERVED | UNKNOWN | UNKNOWN | SCHEDULED + OBSERVED |
| RB17 Nord→Reg | UNKNOWN | UNKNOWN | UNKNOWN | SCHEDULED + OBSERVED |

Здесь `VERIFIED` намеренно не присвоен ни одной полной corridor–platform–corridor комбинации. Найденный DB InfraGO APN достаточно авторитетен для физической инфраструктуры и направлений, но публичная информация не содержит полного сигнально-маршрутного разрешения для конкретного сквозного движения. Присвоить `VERIFIED` только на основании нарисованных стрелок означало бы смешать топологию с эксплуатационной авторизацией.

## Рекомендуемая матрица для FIXED_DB и GREEDY

Для базового эксперимента я рекомендую **консервативное множество GREEDY**, в которое входят только платформы, имеющие прямое SCHEDULED или REAL OBSERVED подтверждение для данной сквозной route group. Топологически возможные, но не наблюдавшиеся платформы лучше вынести в отдельный sensitivity scenario, например `GREEDY_EXPANDED`, а не включать молча в основной GREEDY.

| Route group | Incoming corridor | Outgoing corridor | Рекомендуемые 2–5 | Confidence | Оценка provisional assumption |
|---|---|---|---|---|---|
| ICE_S | north via Ingolstadt Nord; normal SFS 5934→5501 / diversion-period ambiguity | München, 5501 | **2, 3** | medium-high | `3` слишком узко |
| ICE_N | München, 5501 | north via Ingolstadt Nord; normal 5501→5934 | **4** | high для 4, low для 5 | `4,5` частично не подтверждено |
| RE1_S | north/Treuchtlingen via 5501 in observed closure timetable | München, 5501 | **3** | medium | `2,3,5` слишком широко для baseline |
| RE1_N | München, 5501 | north/Treuchtlingen via 5501 | **4** | medium-high | `4,5` — 5 не подтверждён |
| RB16_S | Treuchtlingen/Nürnberg via 5501 | München, 5501 | **2, 3** | high | подтверждено |
| RB16_N | München, 5501 | Treuchtlingen/Nürnberg via 5501 | **4, 5** | high | подтверждено |
| RB15_DONAU_NORD | Donauwörth/Ulm, 5382 | Ingolstadt Nord via 5501 | **3, 4** | medium | новая route group |
| RB15_NORD_DONAU | Ingolstadt Nord via 5501 | Donauwörth/Ulm, 5382 | **нет базового разрешения из 2–5** | low | данных недостаточно |
| RB17_REG_NORD | Regensburg, 5851 | Ingolstadt Nord via 5501 | **2, 5** | medium | новая route group |
| RB17_NORD_REG | Ingolstadt Nord via 5501 | Regensburg, 5851 | **5** | high | новая route group |

Для FIXED_DB следует сохранить фактически scheduled platform из каждой строки входных данных, даже если он лежит за пределами 2–5, если конкретная запись остаётся в модели. Это важно для RB15/RB17/RB16, где в исходном наборе встречаются 1, 6 и 7. Если модель искусственно ограничена только Gleise 2–5, такие рейсы должны либо исключаться, либо иметь явное preprocessing-rule; нельзя автоматически “подменять” их ближайшей разрешённой платформой.

Для GREEDY базовая логика может выглядеть концептуально как `candidate_platform ∈ recommended_allowed(route_group)` плюс отдельная проверка длины/типа состава, если такая информация станет доступна. Для ICE особенно не следует трактовать `{2,3}` как универсальное разрешение: наблюдение ICE 1009 на Gleis 2 говорит о реальной осуществимости конкретного движения, но не о любой двойной тяге, любом типе ICE или нормальном SFS-режиме.

## Ограничения, исторические данные и научная защищаемость

Публично удалось получить актуальную станционную конфигурацию, структурные размеры платформ, VzG-подходы, современный APN-план и эмпирические DB/OpenBoards-платформенные назначения. DB InfraGO подтверждает, что ISR содержит более детальные инфраструктурные сведения, а ISR Data Service предоставляет данные по платформам, Betriebsstellen, Streckenabschnitten и туннелям; при этом Data Service является платным продуктом для Zugangsberechtigte. citeturn569452search3turn569452search4

Не удалось публично подтвердить полный набор разрешённых Einfahr-/Ausfahrstraßen по каждой платформе, сигнальные зависимости, flank protection, временные LST-ограничения и точные platform Nutzlängen для 2–5 в форме, пригодной для независимого доказательства всех вариантов. Поэтому любые дополнительные “возможные” комбинации, выведенные только из рисунка стрелок, должны оставаться `PLAUSIBLE`, а не `VERIFIED`.

Дополнительные исторические OpenBoards-наблюдения **существенно улучшили бы** матрицу. Наиболее полезен был бы период не менее нескольких недель вне строительных окон, желательно с включённой SFS 5934, поскольку текущая выборка приходится на чрезвычайно нетипичный период полного закрытия Nürnberg–Ingolstadt. DB InfraGO прямо датирует эту Sperrung 30.10–12.12.2026. citeturn728334search1

Для следующей итерации исследования стоит собирать один связанный набор полей: `journey_id`, номер поезда, дата, vehicle/formation type, origin/destination, ближайший предыдущий и следующий operational point, scheduled platform, reported platform, REAL/PREVIEW/SCHEDULE, cancellation, время смены платформы и исходный snapshot. Особенно ценны реальные platform changes: они являются естественным экспериментом, показывающим, какие альтернативы фактически использовала диспетчеризация.

Для университетской DES-модели предложенная базовая матрица научно приемлема, если в документации явно зафиксировать три допущения: она моделирует **совместимость на уровне платформенной переадресации**, а не полноценное Stellwerk; результаты применимы к исследуемой выборке и текущей инфраструктурной эпохе, а не ко всем будущим Fahrplanjahr; и `UNKNOWN`/`PLAUSIBLE` не равны `INCOMPATIBLE`.

## CSV-ready результат и источники

Создан фактический CSV с одной строкой на каждую пару `route_group × platform` для Gleise 2–5, всего 40 строк. Он содержит требуемые поля `route_group,incoming_corridor,outgoing_corridor,platform,evidence_status,recommended_allowed,source,justification`.

[Скачать CSV-матрицу совместимости](sandbox:/mnt/data/ingolstadt_hbf_platform_compatibility.csv)

Ключевые источники исследования: актуальная страница DB InfraGO по Ingolstadt Hbf с размерами и официальным предупреждением о различии Nettobaulänge/Bahnsteignutzlänge; Infrastrukturregister и описание ISR Data Service; актуальный APN/ISR-план MIH; DB InfraGO-уведомление о полной блокировке SFS Nürnberg–Ingolstadt в период рассматриваемых данных; официальные DB-спецификации длины ICE. citeturn569452search0turn569452search3turn179682view1turn345688view0turn728334search1turn221208search0turn221208search4turn221208search31