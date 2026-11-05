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
- [Jamoa](#jamoa)
- [Ish jarayoni (Git)](#ish-jarayoni-git)
- [Hujjatlar](#hujjatlar)

---

## Imkoniyatlar

- Ro'yxatdan o'tish va kirish (parollar xeshlangan, JWT token)
- Guruh yaratish, a'zo qo'shish va chiqarish
- Xarajat qo'shish va uni 4 xil usulda bo'lish:
  - **teng** — summa ishtirokchilar soniga teng bo'linadi;
  - **aniq summalar** — har bir ishtirokchi uchun summa qo'lda kiritiladi;
  - **foiz bo'yicha** — foizlar yig'indisi 100 bo'lishi shart;
  - **ulushlar bo'yicha** — summa ulushlarga proporsional bo'linadi.
- Har bir a'zoning sof balansi va eng kam o'tkazmali hisob-kitob rejasi
- To'lovni "to'landi" deb belgilash
- Ilova ichidagi bildirishnomalar
- Xarajatlarni CSV va JSON formatida eksport qilish

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

Rejalashtirilgan tuzilma (loyiha rivojlanishi bilan to'ldirib boriladi):

```
split-easy/
├── .github/            # CI, PR va Issue shablonlari
├── app/
│   ├── domain/         # modellar, pul, bo'lish strategiyalari, balans, hodisalar
│   ├── services/       # biznes mantiq
│   ├── repositories/   # interfeyslar, SQLAlchemy va in-memory implementatsiyalar, SQL hisobotlar
│   ├── db/             # ulanish va ORM modellari
│   ├── exporters/      # CSV, JSON eksport
│   ├── api/            # FastAPI routerlar
│   ├── templates/      # Jinja2 sahifalar
│   └── main.py
├── migrations/         # Alembic migratsiyalari
├── scripts/            # seed.py, benchmark.py
├── docs/               # texnik topshiriq, DB.md, ERD
├── tests/              # unit va integratsion testlar
├── DESIGN.md
├── pyproject.toml
└── README.md
```

---

## O'rnatish va ishga tushirish

> Loyiha ishlab chiqilish jarayonida. Quyidagi buyruqlar loyiha skeleti tayyor bo'lgach to'liq ishlaydi.

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

### 5. Ilovani ishga tushirish

```bash
poetry run uvicorn app.main:app --reload
```

- Ilova: http://127.0.0.1:8000
- API hujjatlari (Swagger): http://127.0.0.1:8000/docs

### 6. Testlar

```bash
poetry run pytest                  # barcha testlar
poetry run pytest --cov=app        # kod qamrovi bilan
poetry run ruff check .            # kod sifati
poetry run black --check .         # formatlash
```

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
- `docs/DB.md` (tayyorlanmoqda) — ERD, normalizatsiya, indekslar, benchmark, tranzaksiyalar
