# SplitEasy

**SplitEasy** — do'stlar, guruhdoshlar yoki xonadoshlar birgalikda qilgan xarajatlarni yozib boradigan va "kim kimga qancha qarzdor" ekanini avtomatik hisoblab beradigan veb-ilova (Splitwise'ning soddalashtirilgan varianti).

> **Misol:** 4 do'st sayohatga chiqdi. Ali mehmonxonaga 400 000 so'm, Vali taksiga 100 000 so'm, Sardor ovqatga 300 000 so'm to'ladi. Ilova eng kam sondagi to'lov bilan hammani hisob-kitob qilib beradi: *"Dilshod → Ali: 200 000 so'm"* va *"Vali → Sardor: 100 000 so'm"*.

Loyiha "Dasturiy ta'minot loyihalash va testlash" fanidan amaliy loyiha sifatida ishlab chiqilmoqda.

## Mundarija

- [Imkoniyatlar](#imkoniyatlar)
- [Texnologiyalar](#texnologiyalar)
- [Arxitektura](#arxitektura)
- [Loyiha tuzilmasi](#loyiha-tuzilmasi)
- [O'rnatish va ishga tushirish](#ornatish-va-ishga-tushirish)
- [API](#api)
- [Jamoa](#jamoa)
- [Ish jarayoni (Git)](#ish-jarayoni-git)
- [Hujjatlar](#hujjatlar)

---

## Imkoniyatlar

- **Mehmon rejimi:** tezkor hisob ro'yxatdan o'tmasdan ishlaydi, lekin ma'lumotlar saqlanmaydi
  (tepada ogohlantirish chiqadi). Ro'yxatdan o'tgach, mehmon kiritgan hisob yangi profilga
  ko'chiriladi va keyingi barcha o'zgarishlar bazaga avtomatik saqlanadi
- Ro'yxatdan o'tish va kirish (parollar xeshlangan, JWT token)
- Guruh yaratish, a'zo qo'shish; a'zoni chiqarish — faqat balansi 0 bo'lsa (FR-7)
- Xarajat qo'shish, **tahrirlash** va o'chirish (muallif yoki guruh egasi) va uni 4 xil usulda bo'lish:
  - **teng** — summa ishtirokchilar soniga teng bo'linadi;
  - **aniq summalar** — har bir ishtirokchi uchun summa qo'lda kiritiladi;
  - **foiz bo'yicha** — foizlar yig'indisi 100 bo'lishi shart;
  - **ulushlar bo'yicha** — summa ulushlarga proporsional bo'linadi.
- Xarajatlar ro'yxati: sana bo'yicha, sahifalab, kategoriya bo'yicha filtr
- Har bir a'zoning sof balansi va eng kam o'tkazmali hisob-kitob rejasi
- To'lovni "to'landi" deb belgilash (summa qarzdan oshmaydi)
- Bildirishnomalar — Observer orqali: ilova ichida va email (ishlab chiqishda fake, logga yoziladi)
- Xarajatlarni **CSV va JSON** formatida eksport qilish (Factory, yangi format osongina qo'shiladi)

Pul summalari faqat butun son (`int`, so'mda) bilan hisoblanadi — `float` ishlatilmaydi.

---

## Texnologiyalar

| Yo'nalish | Texnologiya |
|---|---|
| Dasturlash tili | Python 3.12 |
| Backend | FastAPI |
| Ma'lumotlar bazasi / ORM | SQLite, SQLAlchemy 2.x |
| Migratsiyalar | Alembic |
| Validatsiya | Pydantic |
| Frontend | Jinja2, HTML/CSS, Bootstrap |
| Testlash | pytest, pytest-cov, unittest.mock |
| Kod sifati | Ruff, Black |
| CI | GitHub Actions |
| Bog'liqliklarni boshqarish | Poetry |

---

## Arxitektura

Loyiha 4 qatlamli arxitekturaga ega. Barcha bog'liqliklar domain qatlami tomon yo'naladi.

```
[ API / Web qatlami ]        FastAPI routerlar, Jinja2 sahifalar
          ↓
[ Service qatlami ]          biznes mantiq (ExpenseService, GroupService, ...)
          ↓
[ Domain qatlami ]           sof Python: modellar, bo'lish strategiyalari, balans
          ↑
[ Repository qatlami ]       bazaga kirish (interfeys + SQLAlchemy implementatsiyasi)
```

**Asosiy qoida:** domain qatlami FastAPI, SQLAlchemy yoki boshqa tashqi kutubxonani import qilmaydi. Servislar repository'larning abstrakt interfeysiga bog'liq.

Qo'llanilgan design patternlar: **Strategy**, **Factory**, **Repository**, **Observer**, **Unit of Work**. Batafsil: [`DESIGN.md`](DESIGN.md).

---

## Loyiha tuzilmasi

```
split-easy/
├── .github/workflows/  # CI: ruff, black, pytest --cov-fail-under=80
├── app/
│   ├── domain/         # sof Python: modellar, pul, strategiyalar, balans, reja, hodisalar (events)
│   ├── services/       # biznes mantiq (Auth, Group, Expense, Settlement, Export, Notifiers, ...)
│   ├── repositories/
│   │   ├── interfaces/ # abstrakt repository'lar va Unit of Work
│   │   ├── sqlalchemy/ # ORM modellari, repository'lar, Unit of Work, xom SQL hisobotlar
│   │   └── in_memory.py # ikkinchi implementatsiya (testlar uchun)
│   ├── exporters/      # CSV, JSON eksport va ExporterFactory
│   ├── infrastructure/ # sozlamalar, baza ulanishi, parol xeshlash va JWT
│   ├── api/            # FastAPI routerlar (/api/...)
│   ├── web/            # Jinja2 sahifalar: auth, group, expense, notification
│   ├── templates/      # Jinja2 shablonlar
│   ├── static/         # CSS va JS
│   └── main.py
├── migrations/         # Alembic migratsiyalari (0001–0007)
├── scripts/            # seed.py, benchmark.py, draw_erd.py
├── docs/               # texnik topshiriq, DB.md, ERD, schema.sql, benchmark.md
├── tests/
│   ├── unit/           # domain va servislar (bazasiz, veb'siz)
│   └── integration/    # API, sahifalar, baza, SQL hisobotlar
├── DESIGN.md
├── pyproject.toml
└── README.md
```

---

## O'rnatish va ishga tushirish

Quyidagi qadamlar toza papkaga klon qilib tekshirilgan: o'rnatish va migratsiya taxminan
20 soniya oladi.

### 1. Talablar

- Python 3.12
- Git
- Poetry: `pip install poetry`

### 2. Repozitoriyni yuklab olish

```bash
git clone https://github.com/satorovramazonbek/split-easy.git
cd split-easy
```

### 3. Bog'liqliklarni o'rnatish

```bash
poetry install
```

### 4. Ma'lumotlar bazasini yaratish

```bash
poetry run alembic upgrade head
```

Bo'sh bazadan to'liq sxema (7 ta jadval va indekslar) yaratiladi; standart holatda
loyiha papkasidagi `spliteasy.db` fayli. Boshqa bazaga `SPLITEASY_DATABASE_URL` orqali
ulanish mumkin. JWT tokenlari server qayta ishga tushganda ham ishlashi uchun
`SPLITEASY_SECRET_KEY` ni o'rnating (namuna: [`.env.example`](.env.example)).
Sxema tavsifi: [`docs/DB.md`](docs/DB.md).

### 5. Ilovani ishga tushirish

```bash
poetry run uvicorn app.main:app --reload
```

- Tezkor hisob (ro'yxatdan o'tmasdan): http://127.0.0.1:8000
- Ro'yxatdan o'tish / kirish: http://127.0.0.1:8000/register, http://127.0.0.1:8000/login
- Guruhlarim va hisobotlar: http://127.0.0.1:8000/groups
- API hujjatlari (Swagger): http://127.0.0.1:8000/docs — barcha API yo'llari `/api/`
  bilan boshlanadi, masalan `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/groups`

### 6. Testlar

```bash
poetry run pytest                                     # barcha testlar
poetry run pytest --cov=app --cov-report=term-missing # qamrov va qoplanmagan qatorlar
poetry run ruff check .                               # kod sifati
poetry run black --check .                            # formatlash
```

CI har bir PR va `main`ga push'da shu tekshiruvlarni bajaradi; qamrov 80% dan past
bo'lsa (`--cov-fail-under=80`), CI qizil bo'ladi.

### 7. Katta ma'lumot va benchmark (ixtiyoriy)

```bash
poetry run python scripts/seed.py          # spliteasy-seed.db: 100 000 xarajat, ~10 s
poetry run python scripts/benchmark.py     # indekssiz / indeks bilan -> docs/benchmark.md
```

Seed deterministik (`--seed 42`), barcha foydalanuvchilar paroli `secret123`. Natijalar
tahlili: [`docs/DB.md`](docs/DB.md), 5-bo'lim.

---

## API

To'liq interaktiv hujjat: http://127.0.0.1:8000/docs (Swagger). Kirish va ro'yxatdan
o'tishdan boshqa barcha endpointlar `Authorization: Bearer <token>` talab qiladi.

| Metod | Yo'l | Tavsif | Kod |
|---|---|---|---|
| POST | `/api/auth/register` | Ro'yxatdan o'tish | 201 |
| POST | `/api/auth/login` | Kirish, token qaytaradi | 200 |
| GET, PATCH | `/api/auth/me` | Profil, ismni o'zgartirish (FR-4) | 200 |
| GET, POST | `/api/groups` | Mening guruhlarim, guruh yaratish | 200, 201 |
| GET, DELETE | `/api/groups/{id}` | Guruh, o'chirish (soft delete) | 200, 204 |
| POST | `/api/groups/{id}/members` | A'zo qo'shish (faqat egasi) | 201 |
| DELETE | `/api/groups/{id}/members/{user_id}` | A'zoni chiqarish (balans 0 bo'lsa) | 204 |
| GET | `/api/groups/{id}/expenses?page=&category=` | Xarajatlar ro'yxati | 200 |
| POST | `/api/groups/{id}/expenses` | Xarajat qo'shish | 201 |
| GET, PUT, DELETE | `/api/groups/{id}/expenses/{eid}` | Ko'rish, tahrirlash, o'chirish | 200, 200, 204 |
| GET | `/api/groups/{id}/balances` | A'zolar balanslari | 200 |
| GET | `/api/groups/{id}/settle-plan` | Hisob-kitob rejasi | 200 |
| GET, POST | `/api/groups/{id}/settlements` | To'lovlar tarixi, to'lovni qayd etish | 200, 201 |
| GET | `/api/groups/{id}/export?format=csv\|json` | Eksport | 200 |
| GET | `/api/groups/{id}/reports/...` | Xom SQL hisobotlar (kategoriya, oylar, ...) | 200 |
| GET | `/api/reports/overview` | Barcha guruhlar bo'yicha umumiy holat | 200 |
| GET | `/api/notifications` | Mening bildirishnomalarim | 200 |
| PATCH | `/api/notifications/{id}/read` | O'qildi deb belgilash | 200 |
| POST | `/api/notifications/read-all` | Hammasini o'qildi deb belgilash | 200 |
| POST | `/api/calculate`, `/api/expenses/preview` | Tezkor hisob (mehmon, saqlanmaydi) | 200 |
| GET, PUT, DELETE | `/api/quick-split/draft` | Kirgan foydalanuvchining tezkor hisobi | 200, 200, 204 |

Xato kodlari: `400` noto'g'ri ma'lumot, `401` token yo'q, `403` ruxsat yo'q, `404` topilmadi,
`409` ziddiyat (email band, balansi 0 bo'lmagan a'zo), `422` so'rov formati noto'g'ri.

---

## Jamoa

| A'zo | Mas'uliyat |
|---|---|
| **Ramazonbek** | Backend va biznes mantiq: domain, pul moduli, bo'lish strategiyalari, balans va hisob-kitob, xarajat servisi, Expense va Settlement API, Observer, eksport, DESIGN.md |
| **Aziza** | Ma'lumotlar bazasi, Repository va Frontend: ERD, SQLAlchemy, repository'lar, Alembic, constraint'lar, tranzaksiyalar, Auth va Group API, Jinja2 va Bootstrap, SQL hisobotlar va optimizatsiya, README va DB.md |

---

## Ish jarayoni (Git)

1. `main` — barqaror kod, to'g'ridan-to'g'ri push qilinmaydi.
2. Har bir vazifa uchun alohida branch: `feature/split-strategy`, `feature/database-models`, `docs/erd` va hokazo.
3. Tayyor ish **Pull Request** orqali yuboriladi va GitHub Issue'ga bog'lanadi (`Closes #12`).
4. Ikkinchi a'zo **code review** qiladi; tasdiqlangan va CI muvaffaqiyatli o'tgan PR `main`ga birlashtiriladi.

Commit xabarlari [Conventional Commits](https://www.conventionalcommits.org) bo'yicha yoziladi:

```
feat: add percentage split strategy
test: add tests for equal split rounding
fix: correct remainder distribution
docs: add ERD and normalization analysis
```

---

## Hujjatlar

- [`docs/texnik_topshiriq.pdf.pdf`](docs/texnik_topshiriq.pdf.pdf) — texnik topshiriq
- [`DESIGN.md`](DESIGN.md) — arxitektura, design patternlar va SOLID printsiplari
- [`docs/DB.md`](docs/DB.md) — jadvallar, normalizatsiya, cheklovlar, indekslar, tranzaksiyalar
- [`docs/erd.png`](docs/erd.png) — ERD (`poetry run python scripts/draw_erd.py` bilan yangilanadi)
- [`docs/schema.sql`](docs/schema.sql) — qo'lda yozilgan sxema (Alembic natijasi bilan bir xil)
- [`docs/benchmark.md`](docs/benchmark.md) — indekslar o'lchovi va `EXPLAIN QUERY PLAN`
