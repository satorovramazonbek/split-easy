# SplitEasy — Tizim arxitekturasi va loyihalash hujjati

**Loyiha nomi:** SplitEasy  
**Hujjat nomi:** Tizim arxitekturasi (System Design)  
**Versiya:** 1.0  
**Holati:** Dastlabki loyiha  
**Jamoa:** Ramazonbek va Aziza

---

## 1. Loyiha haqida

SplitEasy — birgalikda xarajat qiladigan insonlar o‘rtasida xarajatlarni hisoblash, taqsimlash va qarzdorliklarni boshqarish uchun mo‘ljallangan veb-ilova.

Ilovaning asosiy maqsadi — guruh a'zolari o‘rtasidagi umumiy xarajatlarni adolatli taqsimlash, kim qancha to‘lashi yoki olishi kerakligini aniqlash va qarzlarni hisob-kitob qilish jarayonini avtomatlashtirish.

### Loyihaning asosiy imkoniyatlari

- Foydalanuvchini ro‘yxatdan o‘tkazish va tizimga kirish.
- Guruhlar yaratish va boshqarish.
- Guruhga yangi a'zolar qo‘shish va ularni chiqarish.
- Umumiy xarajatlarni kiritish.
- Xarajatlarni turli usullarda taqsimlash.
- Guruh a'zolari o‘rtasidagi qarzdorlikni hisoblash.
- Qarzdorliklarni yopish uchun optimal to‘lov rejasini tuzish.
- To‘lovlarni qayd etish.
- Foydalanuvchilarga bildirishnomalar yuborish.
- Xarajatlarni CSV va JSON formatlarida eksport qilish.
- Xarajatlar bo‘yicha hisobotlar tayyorlash.

## 2. Foydalaniladigan texnologiyalar

| Qism | Texnologiya |
|---|---|
| Dasturlash tili | Python 3.12 |
| Backend freymvorki | FastAPI |
| Ma'lumotlar bazasi | SQLite |
| ORM | SQLAlchemy |
| Migratsiyalar | Alembic |
| Ma'lumotlarni tekshirish | Pydantic |
| Shablonlar tizimi | Jinja2 |
| Frontend | HTML, CSS, Bootstrap |
| Testlash | Pytest |
| Kod sifatini tekshirish | Ruff, Black |
| Kutubxonalarni boshqarish | Poetry |
| CI/CD | GitHub Actions |
| Parollarni himoyalash | Passlib (bcrypt) yoki Argon2 |

## 3. Tizim arxitekturasi

SplitEasy loyihasi to‘rt qatlamli arxitektura asosida ishlab chiqiladi.

Bunday arxitektiyaning asosiy maqsadi — foydalanuvchi interfeysi, biznes mantiqi va ma'lumotlar bazasi bilan ishlash qismlarini bir-biridan ajratish.

### 3.1. Arxitektura qatlamlari

**1. API / Web qatlami**

Foydalanuvchi va tizim o‘rtasidagi aloqani ta'minlaydi.

Vazifalari:
- HTTP so‘rovlarini qabul qilish.
- FastAPI orqali marshrutlarni boshqarish.
- Kiruvchi ma'lumotlarni tekshirish.
- Javoblarni shakllantirish.
- Jinja2 yordamida sahifalarni chiqarish.

**2. Service qatlami**

Ilovaning asosiy amaliy jarayonlarini boshqaradi.

Vazifalari:
- Biznes jarayonlarini bajarish.
- Domen obyektlari bilan ishlashni muvofiqlashtirish.
- Ma'lumotlar bazasi operatsiyalarini boshqarish.
- Repository interfeyslari orqali ma'lumot olish va saqlash.
- Bir nechta amaliy operatsiyalarni yagona jarayonga birlashtirish.

Asosiy xizmatlar:
- AuthService
- GroupService
- ExpenseService
- SettlementService
- NotificationService

**3. Domain qatlami**

Loyihaning asosiy biznes qoidalari va hisoblash algoritmlari joylashadi.

Vazifalari:
- Asosiy domen modellarini yaratish.
- Pul qiymatlarini hisoblash.
- Xarajatlarni taqsimlash strategiyalarini amalga oshirish.
- Qarzdorliklarni hisoblash.
- To‘lov rejasini shakllantirish.

**Muhim qoida:** Domain qatlami FastAPI va SQLAlchemy kabi tashqi texnologiyalarga bog‘liq bo‘lmasligi kerak.

**4. Repository qatlami**

Ma'lumotlarni saqlash va olish bilan shug‘ullanadi.

Vazifalari:
- Repository interfeyslarini belgilash.
- Ma'lumotlar bazasi bilan ishlash.
- SQLAlchemy orqali ma'lumotlarni boshqarish.
- SQLite bazasiga murojaat qilish.
- Ma'lumotlarni saqlash va qidirish.

Service qatlami ma'lumotlar bazasining aniq implementatsiyasiga emas, Repository interfeyslariga bog‘lanadi.

### 3.2. Arxitektura sxemasi

```text
             FOYDALANUVCHI
                    |
                    v
          +-------------------+
          |     API / Web     |
          | FastAPI / Jinja2  |
          +-------------------+
                    |
                    v
          +-------------------+
          |     SERVICE       |
          | AuthService       |
          | GroupService      |
          | ExpenseService    |
          +-------------------+
                    |
                    v
          +-------------------+
          |      DOMAIN       |
          | Models            |
          | Money             |
          | Strategies        |
          | Balance           |
          +-------------------+
                    |
                    v
          +-------------------+
          |    REPOSITORY     |
          | Interfaces        |
          | SQLAlchemy        |
          +-------------------+
                    |
                    v
          +-------------------+
          |      SQLITE       |
          | Ma'lumotlar bazasi|
          +-------------------+
```

**Bog‘liqlik qoidasi:** Tizimdagi bog‘liqliklar Domain qatlamiga yo‘nalishi kerak. Domain qatlami tashqi freymvorklar va ma'lumotlar bazasiga bog‘lanmasligi lozim.

## 4. Loyiha papkalari tuzilishi

```text
split-easy/
├── .github/
│   ├── workflows/ci.yml          # ruff, black, pytest --cov-fail-under=80
│   ├── pull_request_template.md  # PR tavsifi shabloni (nima, nega, qanday test qilindi)
│   └── ISSUE_TEMPLATE/           # feature / bug shablonlari
├── app/
│   ├── domain/                   # sof Python (FastAPI/SQLAlchemy importi yo'q)
│   │   ├── models.py             # User, Group, Expense, ExpenseShare, Settlement, Notification
│   │   ├── money.py              # butun so'mda bo'lish, qoldiqni taqsimlash
│   │   ├── split_strategies.py   # Strategy: SplitStrategy + 4 ta implementatsiya
│   │   ├── split_strategy_factory.py  # Factory: SplitStrategyFactory, split_amount()
│   │   ├── balance.py            # sof balans (FR-16)
│   │   ├── settlement.py         # greedy hisob-kitob rejasi (FR-17)
│   │   └── events.py             # Observer: ExpenseAdded, SettlementRecorded, EventBus
│   ├── services/                 # biznes jarayonlari (faqat interfeyslarga bog'liq)
│   │   ├── auth_service.py, group_service.py
│   │   ├── expense_service.py    # xarajat: qo'shish, ro'yxat, tahrirlash, o'chirish
│   │   ├── settlement_service.py # balans, reja, to'lov
│   │   ├── notifiers.py          # Observer kuzatuvchilari: InAppNotifier, EmailNotifier
│   │   ├── notification_service.py, export_service.py, report_service.py
│   │   └── quick_split_service.py, quick_split_draft_service.py, messages.py
│   ├── repositories/
│   │   ├── interfaces/           # Protocol'lar: UserRepository, ExpenseReader/Writer, ...
│   │   ├── sqlalchemy/           # 1-implementatsiya: ORM, xom SQL hisobotlar, UnitOfWork
│   │   └── in_memory.py          # 2-implementatsiya: testlar uchun (dict'larda)
│   ├── exporters/                # Factory: ExporterFactory, CsvExporter, JsonExporter
│   ├── infrastructure/           # sozlamalar, baza ulanishi, argon2/JWT, FakeEmailSender
│   ├── api/                      # JSON routerlar (/api/...) va dependencies.py (DI)
│   ├── web/                      # HTML sahifalar: auth, group, expense, notification
│   ├── templates/, static/
│   └── main.py
├── migrations/                   # Alembic 0001–0007
├── scripts/                      # seed.py, benchmark.py, draw_erd.py
├── docs/                         # DB.md, erd.png, schema.sql, benchmark.md, TZ
└── tests/
    ├── unit/                     # domain + servislar (In-Memory repo va Mock bilan)
    └── integration/              # API, sahifalar, baza, SQL, repository kontraktlari
```

## 5. Domen modeli

### 5.1. Asosiy obyektlar

**User — Foydalanuvchi**

- id — foydalanuvchining unikal identifikatori.
- username — foydalanuvchi nomi.
- email — elektron pochta manzili.
- password_hash — parolning himoyalangan xeshi.
- created_at — yaratilgan sana.

**Group — Guruh**

- id — guruh identifikatori.
- name — guruh nomi.
- created_by — guruhni yaratgan foydalanuvchi.
- created_at — yaratilgan sana.

**GroupMember — Guruh a'zosi**

- id — yozuv identifikatori.
- group_id — guruh identifikatori.
- user_id — foydalanuvchi identifikatori.
- joined_at — guruhga qo‘shilgan vaqt.

**Expense — Xarajat**

- id — xarajat identifikatori.
- group_id — guruh identifikatori.
- paid_by — xarajatni to‘lagan foydalanuvchi.
- title — xarajat nomi.
- amount — xarajat summasi.
- currency — valyuta.
- split_type — taqsimlash turi.
- created_at — yaratilgan sana.

**ExpenseShare — Xarajat ulushi**

- id — yozuv identifikatori.
- expense_id — xarajat identifikatori.
- user_id — foydalanuvchi identifikatori.
- amount — foydalanuvchining ulushi.

**Settlement — Hisob-kitob**

- id — to‘lov identifikatori.
- group_id — guruh identifikatori.
- from_user — pul yuboruvchi.
- to_user — pul oluvchi.
- amount — to‘lov summasi.
- settled_at — to‘lov amalga oshirilgan vaqt.

**Notification — Bildirishnoma**

- id — bildirishnoma identifikatori.
- user_id — bildirishnoma oluvchi.
- message — bildirishnoma matni.
- is_read — o‘qilganlik holati.
- created_at — yaratilgan sana.

## 6. Pul qiymatlari bilan ishlash

Pul qiymatlarini hisoblashda `float` turidan foydalanish taqiqlanadi. Chunki bu turdagi sonlarda aniqlik bilan bog‘liq muammolar yuzaga kelishi mumkin.

Pul qiymatlari quyidagi usullardan biri bilan saqlanadi:

- Eng kichik pul birligini ifodalovchi `int`.
- Aniqlikni saqlovchi `Decimal`.

Masalan:

```python
total_amount = 10000
```

Bu qiymat ikki xonali kasr qismiga ega valyutada 100.00 ni anglatishi mumkin.

Barcha taqsimlash algoritmlari natijasida ishtirokchilar ulushlarining yig‘indisi boshlang‘ich xarajat summasiga aynan teng bo‘lishi shart.

Bo‘linishdan qolgan eng kichik pul birliklari oldindan belgilangan, takrorlanuvchi tartibda ishtirokchilarga taqsimlanadi.

## 7. Xarajatlarni taqsimlash strategiyalari

SplitEasy tizimida xarajatlarni taqsimlashning to‘rtta usuli mavjud bo‘ladi.

### 7.1. Teng taqsimlash (Equal Split)

Umumiy xarajat barcha ishtirokchilarga teng taqsimlanadi.

Misol:

```text
Umumiy xarajat: 120 000 so‘m
Ishtirokchilar: 3 nafar

A foydalanuvchi: 40 000 so‘m
B foydalanuvchi: 40 000 so‘m
C foydalanuvchi: 40 000 so‘m
```

### 7.2. Aniq summa bo‘yicha taqsimlash (Exact Split)

Har bir ishtirokchi uchun alohida summa belgilanadi.

Misol:

```text
Umumiy xarajat: 120 000 so‘m

A foydalanuvchi: 50 000 so‘m
B foydalanuvchi: 40 000 so‘m
C foydalanuvchi: 30 000 so‘m
```

Barcha summalar yig‘indisi umumiy xarajatga teng bo‘lishi shart.

### 7.3. Foiz bo‘yicha taqsimlash (Percentage Split)

Xarajat ishtirokchilarga belgilangan foizlar asosida taqsimlanadi.

Misol:

```text
Umumiy xarajat: 100 000 so‘m

A foydalanuvchi: 50%
B foydalanuvchi: 30%
C foydalanuvchi: 20%
```

Foizlar yig‘indisi 100% bo‘lishi shart.

### 7.4. Ulush bo‘yicha taqsimlash (Shares Split)

Xarajat har bir ishtirokchining ulushiga qarab taqsimlanadi.

Misol:

```text
Umumiy xarajat: 120 000 so‘m

A foydalanuvchi: 2 ulush
B foydalanuvchi: 1 ulush
C foydalanuvchi: 1 ulush

A foydalanuvchi: 60 000 so‘m
B foydalanuvchi: 30 000 so‘m
C foydalanuvchi: 30 000 so‘m
```

### Strategy Pattern — Strategiya namunasi

Har bir taqsimlash usuli umumiy interfeys orqali amalga oshiriladi.

```python
class SplitStrategy:
    def split(self, total_amount, participants):
        raise NotImplementedError
```

Ushbu interfeys asosida quyidagi sinflar yaratiladi:

- EqualSplitStrategy
- ExactSplitStrategy
- PercentageSplitStrategy
- SharesSplitStrategy

Bu yondashuv yangi taqsimlash usullarini mavjud algoritmlarni o‘zgartirmasdan qo‘shish imkonini beradi.

## 8. Qarzdorlikni hisoblash

Balance moduli guruh a'zolarining kimga qancha qarzi borligini yoki kim qancha pul olishi kerakligini hisoblaydi.

- Musbat balans — foydalanuvchi pul olishi kerak.
- Manfiy balans — foydalanuvchi pul to‘lashi kerak.
- Nol balans — foydalanuvchining qarzi yoki oladigan puli yo‘q.

Misol:

```text
A foydalanuvchi: +50 000
B foydalanuvchi: -30 000
C foydalanuvchi: -20 000

Jami: 0
```

Guruhdagi barcha foydalanuvchilarning balanslari yig‘indisi doimo nolga teng bo‘lishi kerak.

## 9. Qarzdorlikni yopish algoritmi

Tizim qarzdorliklarni imkon qadar kam miqdordagi to‘lovlar orqali yopish uchun Greedy Algorithm — ochko‘z algoritmdan foydalanadi.

Algoritmning ishlash tartibi:

1. Har bir guruh a'zosining balansini hisoblash.
2. Pul oluvchilar va pul to‘lovchilarni ajratish.
3. Eng ko‘p qarzi bor foydalanuvchi va eng ko‘p pul olishi kerak bo‘lgan foydalanuvchini tanlash.
4. Ularning qarzdorliklari orasidagi eng kichik summani aniqlash.
5. To‘lov operatsiyasini yaratish.
6. Har ikki foydalanuvchining balansini yangilash.
7. Barcha balanslar nolga teng bo‘lguncha jarayonni takrorlash.

Natijada qarzdorliklarni yopish uchun qulay to‘lov rejasi shakllantiriladi.

## 10. Loyihada foydalaniladigan loyihalash naqshlari

Har bir pattern uchun: qaysi muammoni hal qiladi, nega aynan shu yerda va patternsiz kod
qanday bo'lardi (TZ, 8-bo'lim).

### 10.1. Strategy — xarajatni bo'lish usullari

- **Qayerda:** `app/domain/split_strategies.py` — `SplitStrategy` (abstrakt klass) va
  `EqualSplitStrategy`, `ExactSplitStrategy`, `PercentageSplitStrategy`,
  `SharesSplitStrategy`.
- **Muammo:** to'rt xil bo'lish qoidasi bor, har birining o'z tekshiruvi (foizlar = 100,
  aniq summalar = umumiy summa) va hammasi uchun bitta umumiy yaxlitlash qoidasi.
- **Nega shu yerda:** servis faqat `strategy.split(total, participants)` ni chaqiradi va
  qaysi usul ekanini bilmaydi. Umumiy qadamlar (summa musbat, ishtirokchilar takrorlanmaydi,
  yig'indi = summa) bazaviy klassda bir marta yozilgan, har bir usul faqat `_calculate` ni
  yozadi.
- **Patternsiz:** `ExpenseService` ichida `if split_type == "equal": ... elif "exact": ...`
  zanjiri bo'lardi. Yangi usul qo'shish uchun servisni o'zgartirish kerak bo'lardi va har bir
  tarmoqni alohida test qilib bo'lmasdi.

### 10.2. Factory — strategiya va eksportyorni nomi bo'yicha yaratish

- **Qayerda:** `SplitStrategyFactory.create("percentage")`
  (`app/domain/split_strategy_factory.py`) va `ExporterFactory.create("csv")`
  (`app/exporters/factory.py`).
- **Muammo:** foydalanuvchi usul yoki formatni **matn** ko'rinishida yuboradi (`"shares"`,
  `?format=json`), kod esa konkret klassni bilishi kerak.
- **Nega shu yerda:** nom → klass moslash bitta registrda (`_registry`) turadi. Yangi format
  — bitta klass va `ExporterFactory.register("xlsx", XlsxExporter)`; servis ham, API ham
  o'zgarmaydi (FR-25). Buni `tests/unit/test_exporters.py` dagi
  `test_new_format_is_added_without_changing_existing_code` testi ko'rsatadi.
- **Patternsiz:** API routerida `if format == "csv": CsvExporter() elif ...` — har yangi
  formatda router, servis va testlar o'zgaradi.

### 10.3. Repository — bazaga kirishni ajratish

- **Qayerda:** interfeyslar `app/repositories/interfaces/` (Protocol): `UserRepository`,
  `GroupRepository`, `ExpenseRepository` (= `ExpenseReader` + `ExpenseWriter`),
  `SettlementRepository`, `NotificationRepository`, `ReportRepository` (+ `BalanceReader`).
  **Ikki implementatsiya:** `app/repositories/sqlalchemy/` va `app/repositories/in_memory.py`.
- **Muammo:** biznes qoidalari (kim xarajat qo'sha oladi, balans 0 bo'lsa chiqarish) bazaga
  bog'liq bo'lmasligi va bazasiz test qilinishi kerak (NFR-4).
- **Nega shu yerda:** servislar konstruktorda interfeysni oladi. Ishlab chiqarishda SQLAlchemy,
  unit testlarda In-Memory beriladi (`tests/unit/test_expense_service.py`). Ikkalasi bir xil
  kontraktga amal qilishini `tests/integration/test_repository_contracts.py` tekshiradi
  (har bir test ikki marta ishlaydi).
- **Patternsiz:** servislar ichida `session.query(...)` bo'lardi — har bir servis testiga
  baza kerak bo'lardi va SQL o'zgarsa, biznes kodi ham o'zgarardi.

### 10.4. Observer (Event Bus) — bildirishnomalar

- **Qayerda:** hodisalar va `EventBus` — `app/domain/events.py` (`ExpenseAdded`,
  `SettlementRecorded`). Kuzatuvchilar — `app/services/notifiers.py` (`InAppNotifier`,
  `EmailNotifier`, umumiy `Notifier` interfeysi). Ulash — `app/api/dependencies.py`,
  `get_event_bus()`.
- **Muammo:** xarajat yoki to'lov saqlanganda bir nechta ish bajarilishi kerak: ilova ichida
  bildirishnoma (FR-20, FR-21), email (FR-22), kelajakda SMS yoki Telegram. TZ talabi:
  **`ExpenseService` bildirishnoma klasslarini bilmasligi kerak.**
- **Nega shu yerda:** servis faqat `self._events.publish(ExpenseAdded(...))` deydi. Kim
  tinglayotganini bilmaydi. Yangi kanal — yangi klass va `register_notifier(bus, ...)`
  qatori; servis o'zgarmaydi. Testda bus o'rniga `Mock()` beriladi va hodisa yuborilgani
  tekshiriladi (`test_adding_expense_publishes_expense_added_event`).
- **Tranzaksiya:** hodisa `uow.commit()` dan **oldin**, Unit of Work ichida e'lon qilinadi.
  `InAppNotifier` so'rovning sessiyasidan foydalanadi, shuning uchun xarajat, ulushlar va
  bildirishnomalar bitta tranzaksiyada saqlanadi (TZ 10.4). Bildirishnoma yozilmasa, xarajat
  ham saqlanmaydi (`test_expense_and_notifications_are_saved_together`).
- **Patternsiz:** `ExpenseService` `NotificationRepository` va `EmailSender` ni bevosita
  chaqirardi: uchta vazifa bitta klassda (SRP buzilishi) va har yangi kanal uchun servis
  o'zgarardi (OCP buzilishi).

### 10.5. Unit of Work — tranzaksiya chegarasi servisda (bonus)

- **Qayerda:** `app/repositories/interfaces/unit_of_work.py`,
  `app/repositories/sqlalchemy/unit_of_work.py`, `InMemoryUnitOfWork`.
- **Muammo:** xarajat va uning barcha ulushlari, tahrirlashda eski ulushlarni o'chirish va
  yangilarini yozish, to'lov va bildirishnoma — yo hammasi saqlanadi, yo hech narsa.
- **Nega shu yerda:** qaysi yozuvlar bir butun ekanini faqat servis biladi:
  `with uow: ... uow.commit()`. `commit()` siz yoki xato bilan chiqilsa — rollback.

### 10.6. Adapter va Decorator (bonus, qo'llanilmagan)

Valyuta kursi API'si (Adapter) va loglovchi/keshlovchi wrapper (Decorator) TZ'da bonus.
Loyihada tashqi valyuta xizmati yo'q, shuning uchun "chiroyli ko'rinishi uchun" pattern
qo'shilmadi (TZ, 19-bo'lim: "Patternni majburan qo'llamang").

## 11. SOLID tamoyillari

| Tamoyil | Loyihadagi aniq misol (fayl → klass) | Qanday amal qilinadi |
|---|---|---|
| **S** — Single Responsibility | `app/services/expense_service.py` → `ExpenseService`; `settlement_service.py` → `SettlementService`; `notifiers.py` → `InAppNotifier`, `EmailNotifier`; `export_service.py` → `ExportService`; `auth_service.py` → `AuthService` | `ExpenseService` faqat xarajat qoidalarini biladi. To'lov, bildirishnoma, eksport va autentifikatsiya alohida klasslarda. Veb qatlami ham mavzular bo'yicha bo'lingan: `app/web/auth_pages.py`, `group_pages.py`, `expense_pages.py`, `notification_pages.py` |
| **O** — Open/Closed | `app/domain/split_strategy_factory.py` → `SplitStrategyFactory.register()`; `app/exporters/factory.py` → `ExporterFactory.register()`; `app/domain/events.py` → `EventBus.subscribe()` | Yangi bo'lish usuli, eksport formati yoki bildirishnoma kanali — yangi klass va bitta ro'yxatdan o'tkazish qatori. Mavjud kod o'zgarmaydi |
| **L** — Liskov Substitution | `SplitStrategy` ning 4 ta implementatsiyasi; `SqlAlchemy*Repository` ↔ `InMemory*Repository` (`app/repositories/in_memory.py`) | Har qanday strategiya bir xil kontraktga amal qiladi: ulushlar yig'indisi = summa. Repository'lar uchun `tests/integration/test_repository_contracts.py` bir xil testlarni ikkala implementatsiyada ishlatadi |
| **I** — Interface Segregation | `app/repositories/interfaces/expense_repository.py` → `ExpenseReader`, `ExpenseWriter`; `report_repository.py` → `BalanceReader` ⊂ `ReportRepository`; `app/services/notifiers.py` → `Notifier`, `EmailSender`; `app/domain/events.py` → `EventPublisher` | `GroupService` va `SettlementService` butun hisobotlar interfeysini emas, faqat `BalanceReader.member_balances()` ni oladi. Servisga butun `EventBus` emas, faqat `publish()` li `EventPublisher` kerak |
| **D** — Dependency Inversion | `ExpenseService(uow: UnitOfWork, events: EventPublisher)`; `SettlementService(uow, balances: BalanceReader, events)`; `GroupService(groups, users, balances)`; `EmailNotifier(sender: EmailSender, users)` | Servislar abstraksiyalarni konstruktor orqali oladi va o'zi yaratmaydi. Konkret klasslar faqat bitta joyda — `app/api/dependencies.py` (composition root) — ulanadi. Testlar o'sha konstruktorlarga In-Memory repo va `Mock` beradi |

### 11.1. Texnik topshiriqdan ongli chetlanishlar

| TZ | Loyihada | Sabab |
|---|---|---|
| 3-bo'lim: Mehmon "faqat ro'yxatdan o'tish va kirish sahifalarini ko'ra oladi" | Mehmon **Tezkor hisob** sahifasidan foydalana oladi: ma'lumotlar faqat brauzer xotirasida turadi va hech narsa saqlanmaydi (tepada ogohlantirish chiqadi) | Mahsulot qarori: foydalanuvchi ilovani ro'yxatdan o'tmasdan sinab ko'radi. Ro'yxatdan o'tgach, kiritgan hisobi profilga ko'chiriladi. Guruhlar, xarajatlar va hisobotlarga mehmon kira olmaydi — avtorizatsiya qoidasi (NFR-1) o'zgarmagan |
| FR-7: "faqat balansi 0 bo'lsa" chiqarish | Balans 0 bo'lmasa — 409. Balans 0 va tarixi bor a'zo `group_members.left_at` bilan "chiqib ketgan" deb belgilanadi (migratsiya `0007`), tarixi yo'q a'zo o'chiriladi | Xarajat va to'lovlar a'zolik qatoriga FK (`ON DELETE RESTRICT`) bilan bog'langan: tarix yo'qolmasligi uchun qator saqlanadi |
| 11-bo'lim: `/auth/...`, `/groups/...` | Hamma JSON yo'llar `/api/` prefiksi bilan | HTML sahifalar (`/groups`, `/login`) bilan to'qnashmasligi uchun |
| FR-18: to'lov | To'lov summasi qarzdan oshmasligi kerak | "To'landi" tugmasini ikki marta bosish qarzni kreditga aylantirib yubormasligi uchun |

## 12. Ma'lumotlar bazasi

Loyihaning dastlabki bosqichida SQLite ma'lumotlar bazasidan foydalaniladi.

SQLAlchemy ma'lumotlar bazasi bilan ishlash va ORM modellarini boshqarish uchun, Alembic esa ma'lumotlar bazasi tuzilmasidagi o‘zgarishlarni boshqarish uchun ishlatiladi.

Ma'lumotlar bazasiga qo‘yiladigan talablar:

- Tashqi kalitlar (Foreign Keys).
- Takrorlanmaslik cheklovlari (Unique Constraints).
- Kerakli indekslar.
- Tranzaksiyalarni boshqarish.
- Ma'lumotlar yaxlitligini saqlash.
- Noto‘g‘ri xarajat ulushlari kiritilishining oldini olish.

**Nega hisobotlar xom SQL'da?** Hisobotlar ko‘p jadvalni bog‘lab, `GROUP BY`, subquery, window
function va CTE bilan yig‘ma natija beradi. Bunday so‘rov qo‘lda yozilganda o‘qish,
`EXPLAIN QUERY PLAN` bilan tekshirish va indeks bilan sozlash ORM yaratgan SQL'dan ancha oson;
bitta so‘rov ko‘p obyektni xotiraga yuklamasdan natijani bazaning o‘zida hisoblaydi. Shu bilan
birga so‘rovlar `ReportRepository` interfeysi ortida turadi — servislar SQL'ni bilmaydi.
Batafsil: `docs/DB.md`, 4-bo‘lim.

## 13. Xavfsizlik

Tizim xavfsizligini ta'minlash uchun quyidagi talablar bajariladi:

- Parollar xeshlangan ko‘rinishda saqlanadi.
- Ochiq matn ko‘rinishidagi parollar bazaga yozilmaydi.
- Foydalanuvchidan kelgan ma'lumotlar tekshiriladi.
- Himoyalangan resurslarga faqat autentifikatsiyadan o‘tgan foydalanuvchilar kirishi mumkin.
- Foydalanuvchilar faqat o‘zlariga ruxsat berilgan guruh va ma'lumotlarga murojaat qila olishi kerak.
- Maxfiy kalitlar va parollar muhit o‘zgaruvchilarida (`.env`) saqlanadi.
- Maxfiy ma'lumotlar GitHub'ga yuborilmaydi.

## 14. Testlash strategiyasi

Loyihani avtomatik testlash uchun Pytest kutubxonasidan foydalaniladi.

### Unit Testlar

Quyidagi qismlar alohida tekshiriladi:

- Pul qiymatlarini hisoblash.
- Xarajatlarni taqsimlash strategiyalari.
- Balanslarni hisoblash.
- Qarzdorlikni yopish algoritmi.
- Service qatlamidagi biznes mantiqi.

### Integration Testlar

Quyidagi qismlar birgalikda tekshiriladi:

- API endpointlari.
- Ma'lumotlar bazasi operatsiyalari.
- Repository implementatsiyalari.
- Tranzaksiyalar.

### Mocking va Fake

- Servis testlari In-Memory repository'lar bilan ishlaydi (`app/repositories/in_memory.py`):
  baza ham, veb-freymvork ham kerak emas (NFR-4).
- `unittest.mock.Mock` hodisa yuboruvchi (`EventPublisher`) va email yuboruvchi
  (`EmailSender`) o'rnida ishlatiladi: `ExpenseAdded` yuborilgani va kuzatuvchi chaqirilgani
  tekshiriladi (`tests/unit/test_expense_service.py`, `test_notifiers.py`, `test_events.py`).
- Haqiqiy email yuborilmaydi: `FakeEmailSender` xatlarni faqat logga yozadi (FR-22).

**Test qamrovi talabi:** Domain va Service qatlamlari uchun kamida 80% test qamroviga erishish.

## 15. Kod sifati va CI/CD

Loyihada kod sifatini nazorat qilish uchun quyidagi vositalardan foydalaniladi:

- Ruff — koddagi xatolar va uslubiy kamchiliklarni aniqlash.
- Black — kod formatini bir xil holatga keltirish.
- Pytest — avtomatik testlarni bajarish.
- GitHub Actions — CI jarayonini avtomatlashtirish.

CI jarayoni GitHub'ga kod yuborilganda yoki Pull Request ochilganda avtomatik ishga tushadi.

Testlar loyihaga qo‘shilgan sari CI jarayoniga ham kiritiladi.

## 16. Git bilan ishlash tartibi

Loyihada Branch-Based Workflow — tarmoqlar asosidagi ishlab chiqish usuli qo‘llaniladi.

Asosiy tarmoqlar:

- `main` — barqaror va tekshirilgan kod.
- `chore/*` — konfiguratsiya va texnik xizmat vazifalari.
- `feature/*` — yangi imkoniyatlar.
- `fix/*` — xatolarni tuzatish.

Commit xabarlari Conventional Commits standartiga muvofiq yoziladi.

Misollar:

```text
feat: add expense splitting strategies
fix: correct equal split remainder calculation
test: add balance calculation tests
docs: update system design
ci: configure GitHub Actions
```

Har bir yangi imkoniyat alohida branch'da ishlab chiqiladi. O‘zgarishlar Pull Request orqali taqdim etiladi va Code Review'dan so‘ng `main` branch'ga birlashtiriladi.

## 17. Kelajakdagi rivojlantirish imkoniyatlari

Kelajakda loyihaga quyidagi imkoniyatlarni qo‘shish rejalashtirilishi mumkin:

- PostgreSQL ma'lumotlar bazasiga o‘tish.
- REST API imkoniyatlarini kengaytirish.
- Mobil ilova yaratish.
- Bir nechta valyutani qo‘llab-quvvatlash.
- Kengaytirilgan hisobotlar.
- Qo‘shimcha bildirishnoma kanallari.
- Katta hajmdagi ma'lumotlar uchun unumdorlikni oshirish.

---

**Hujjat yakuni.**