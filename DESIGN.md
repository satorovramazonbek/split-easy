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

Loyiha quyidagi papka va fayllar asosida tashkil qilinadi:

```text
split-easy/
│
├── app/
│   ├── api/
│   │   ├── routes/
│   │   └── dependencies.py
│   │
│   ├── domain/
│   │   ├── models/
│   │   ├── strategies/
│   │   ├── money.py
│   │   ├── balance.py
│   │   └── settlement.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── group_service.py
│   │   ├── expense_service.py
│   │   └── settlement_service.py
│   │
│   ├── repositories/
│   │   ├── interfaces/
│   │   └── sqlalchemy/
│   │
│   ├── infrastructure/
│   │   ├── database.py
│   │   └── security.py
│   │
│   ├── templates/
│   ├── static/
│   └── main.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── migrations/
├── docs/
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── .env.example
├── .gitignore
├── alembic.ini
├── pyproject.toml
├── poetry.lock
├── README.md
└── DESIGN.md
```

Loyiha rivojlanishi davomida zaruratga qarab qo‘shimcha papka va fayllar kiritilishi mumkin.

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

### 10.1. Strategy Pattern

Xarajatlarni turli usullarda taqsimlash algoritmlarini amalga oshirish uchun foydalaniladi.

### 10.2. Repository Pattern

Ma'lumotlar bazasi bilan ishlash qismini biznes mantiqidan ajratish uchun foydalaniladi.

### 10.3. Observer Pattern / Event Bus

Tizimda sodir bo‘ladigan muhim hodisalar haqida foydalanuvchilarni xabardor qilish uchun ishlatiladi.

Misollar:

- ExpenseCreated — yangi xarajat yaratildi.
- MemberAdded — guruhga yangi a'zo qo‘shildi.
- SettlementCompleted — hisob-kitob yakunlandi.

### 10.4. Factory Pattern

Tanlangan taqsimlash turiga mos strategiya obyektini yaratish uchun foydalaniladi.

### 10.5. Adapter va Decorator Pattern

Zarur holatlarda qo‘shimcha imkoniyatlarni kengaytirish va mavjud komponentlarni moslashtirish uchun qo‘llanilishi mumkin.

## 11. SOLID tamoyillari

Loyiha SOLID tamoyillari asosida ishlab chiqiladi.

**S — Single Responsibility Principle (Yagona mas'uliyat tamoyili)**

Har bir sinf faqat bitta asosiy vazifani bajarishi kerak.

Misol: ExpenseService xarajatlar bilan bog‘liq amaliy jarayonlarni boshqaradi, BalanceCalculator esa balanslarni hisoblaydi.

**O — Open/Closed Principle (Ochiqlik va yopiqlik tamoyili)**

Tizim yangi imkoniyatlarni qo‘shishga ochiq, mavjud kodni o‘zgartirishga esa imkon qadar yopiq bo‘lishi kerak.

Misol: yangi taqsimlash strategiyasini qo‘shishda mavjud strategiyalar kodini o‘zgartirish talab qilinmasligi kerak.

**L — Liskov Substitution Principle (O‘rin almashtirish tamoyili)**

Umumiy interfeysni amalga oshirgan barcha strategiyalar bir-birining o‘rnida ishlay olishi kerak.

**I — Interface Segregation Principle (Interfeyslarni ajratish tamoyili)**

Sinf o‘zi foydalanmaydigan ortiqcha metodlarni amalga oshirishga majbur bo‘lmasligi kerak.

**D — Dependency Inversion Principle (Bog‘liqliklarni teskari yo‘naltirish tamoyili)**

Yuqori darajadagi modullar aniq implementatsiyalarga emas, abstraksiyalarga bog‘lanishi kerak.

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

### Mocking

Tashqi bog‘liqliklarni mustaqil tekshirish uchun zarur joylarda Mock obyektlardan foydalaniladi.

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