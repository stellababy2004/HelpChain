# HelpChain — Stability Lockdown Checklist

## 0. Rule of the day

- [ ] Днес не добавям нови feature-и
- [ ] Днес не правя нов redesign
- [ ] Днес не пипам homepage / footer / colors / AI ideas
- [ ] Днес правя само: diagnose → fix → verify → lock

## 1. Start clean

### Branch

- [ ] `git status` е чист или разбирам точно какво има вътре
- [ ] създаден е branch:

```bash
git checkout -b fix/stability-lockdown
```

### Snapshot

- [ ] имам последен commit point
- [ ] знам в коя среда работя
- [ ] знам кой server/process пускам

## 2. Database source of truth

### Runtime DB

- [ ] проверих кой е реалният `SQLALCHEMY_DATABASE_URI`
- [ ] потвърдих коя е canonical local DB
- [ ] потвърдих, че app runtime сочи към същата DB
- [ ] потвърдих, че admin чете от същата DB
- [ ] потвърдих, че public create пише в същата DB

### Must be true

- [ ] няма split между `hc_local_dev.db` и `app_clean.db`
- [ ] знам коя DB е source of truth

### Notes

- [ ] записах си DB path някъде (локално/markdown)

## 3. Request creation — public flow

### Create request

- [ ] отворих public request form
- [ ] попълних:
- [ ] category
- [ ] objet
- [ ] description
- [ ] name
- [ ] phone
- [ ] email
- [ ] submit работи
- [ ] success message е реален, не фалшив

### DB verification

- [ ] новият request съществува в DB
- [ ] има реално id
- [ ] structure_id е правилен
- [ ] status е очакван
- [ ] deleted_at е null
- [ ] is_archived не го скрива

### Admin verification

- [ ] новият request се вижда в `/admin/requests`
- [ ] `/admin/requests/<id>` се отваря без 404
- [ ] request е в правилния tenant scope

## 4. Request creation — admin flow

### Create from admin

- [ ] създадох нов request от admin
- [ ] със selected structure
- [ ] без selected structure
- [ ] и в двата случая create работи

### Verify

- [ ] redirect след create е правилен
- [ ] detail page се отваря
- [ ] request се вижда в list-а
- [ ] structure assignment е правилен

## 5. Admin requests queue — structural stability

### Layout

- [ ] board използва пълната ширина на екрана
- [ ] няма голямо празно място вдясно
- [ ] row-овете не изглеждат отрязани
- [ ] header е на мястото си
- [ ] header не overlap-ва първия ред
- [ ] sticky behavior е стабилен или graceful

### Row rendering

- [ ] няма letter-by-letter wrapping
- [ ] title е най-четимият елемент
- [ ] metadata line е подредена
- [ ] category labels са human-readable
- [ ] priority rail е вързан към priority
- [ ] status/risk/category/date са сканируеми
- [ ] actions стоят стабилно вдясно

### Dropdown

- [ ] status dropdown се вижда целият
- [ ] не се clip-ва
- [ ] z-index е наред
- [ ] parent wrappers не го режат

## 6. Admin queue — resolution test

Провери на:

- [ ] 1280px
- [ ] 1366px
- [ ] 1440px
- [ ] 1600px
- [ ] 1920px

За всяка ширина:

- [ ] board ползва добре ширината
- [ ] row alignment е стабилен
- [ ] dropdown се вижда
- [ ] няма broken clipping
- [ ] filters/header/rows са подравнени

## 7. Inline status change

### Interaction

- [ ] мога да сменя status от queue screen
- [ ] менюто се отваря изцяло
- [ ] изборът работи
- [ ] badge-ът се update-ва
- [ ] няма layout breakage

### Data

- [ ] status промяната се записва реално
- [ ] след refresh остава записана
- [ ] detail page показва същия нов status
- [ ] няма permission/regression проблем

## 8. Submit form stability

### Step flow

- [ ] Step 1 = Situation
- [ ] Step 2 = Coordonnées
- [ ] Step 3 = Confirmation

### Step 1

- [ ] category field е видим
- [ ] category suggestions са видими
- [ ] няма duplicate pills
- [ ] “Choisir une catégorie” е правилен placeholder
- [ ] “Objet de la demande” е ясен
- [ ] description textarea е ясна
- [ ] urgence helper text е правилен

### Submission

- [ ] submit работи
- [ ] request се създава реално
- [ ] request се вижда в admin
- [ ] detail page се отваря

## 9. Hidden fallback audit

Провери дали има останали скрити рискове:

- [ ] `structure_id = 1`
- [ ] implicit default structure fallback
- [ ] `before_insert` / `before_flush` hooks
- [ ] duplicate DB config paths
- [ ] hidden archived/deleted filters
- [ ] query scope mismatch между create/list/detail

### Conclusion

- [ ] няма втори скрит механизъм, който може да върне bug-а
- [ ] или има, и е описан/фиксиран

## 10. Smoke test — public surfaces

### Public pages

- [ ] homepage се отваря
- [ ] contact form се отваря
- [ ] submit request form се отваря
- [ ] legal page се отваря
- [ ] privacy page се отваря
- [ ] terms page се отваря
- [ ] securite се отваря
- [ ] architecture се отваря
- [ ] gouvernance се отваря

### Basic functionality

- [ ] няма obvious 500
- [ ] няма broken links в nav/footer
- [ ] forms не хвърлят front-end error

## 11. Smoke test — admin surfaces

- [ ] admin login работи
- [ ] dashboard се отваря
- [ ] requests list се отваря
- [ ] request detail се отваря
- [ ] filters работят
- [ ] bulk select работи
- [ ] status change работи
- [ ] няма 404 за новосъздадени заявки

## 12. Final lock

### Documentation

- [ ] записах root causes
- [ ] записах applied fixes
- [ ] записах каква е canonical local DB
- [ ] записах как се проверява create → admin flow

### Commit

- [ ] `git status` е ясен
- [ ] commit message е stabilization-oriented

Пример:

```bash
git commit -m "fix(stability): align tenant-scoped request creation and stabilize admin request operations"
```

### Stop rule

- [ ] не започвам нов feature след последния fix
- [ ] приключвам деня само след green smoke test

## Quick pass / fail table

### PASS if:

- [ ] request create works
- [ ] request appears in admin
- [ ] detail page opens
- [ ] admin queue is readable and stable
- [ ] dropdown works
- [ ] one DB source of truth exists
- [ ] no hidden fallback remains

### FAIL if even one is true:

- [ ] success flash but no DB row
- [ ] DB row exists but detail 404 because of wrong structure
- [ ] different processes use different DB files
- [ ] queue still clips/breaks at common desktop widths
- [ ] status menu still gets cut off

## Working rule for every fix tomorrow

За всяка промяна:

- [ ] 1 fix
- [ ] 1 verification
- [ ] 1 conclusion

Не:

- [ ] 7 промени наведнъж
- [ ] после “май работи”
