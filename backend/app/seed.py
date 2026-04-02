"""Demo seed data with deterministic UUIDs.

Designed to demonstrate all key RBAC concepts:
- Role as occupation vs resource group (case 0)
- Many-to-many via @members and declared roles (case 1)
- Multi-tiered access within same org (case 2)
- Different resource categorization / bundling (case 3)
- Role exchange lifecycle (case 4)
- Foreign propagation stop (case 4b)
- Multi-level exchange establishment (case 5)
"""

import uuid

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


NAMESPACE = uuid.UUID("e58ed763-928c-4155-bee9-fae2cee20735")


def _id(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, key))


def _pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ── Organizations ────────────────────────────────────────────────────────────
# Tree A: Авіабригада «Схід» (main demo org, 3 levels)
# Tree B: Бригада «Захід» (foreign partner, 2 levels)
# Tree C: Бригада «Північ» (second foreign, for propagation stop demo)

ORGS = [
    # ── Tree A ──
    {"id": _id("org:Авіабригада Схід"), "name": "Авіабригада «Схід»",
     "description": "Головна організація демо. Містить підрозділи з різними рівнями доступу та категоріями ресурсів.",
     "parent_id": None},
    {"id": _id("org:Ескадрилья Альфа"), "name": "Ескадрилья «Альфа»",
     "description": "Дочірній підрозділ бригади. Має власні ресурси та ролі, що демонструють багаторівневий доступ.",
     "parent_id": _id("org:Авіабригада Схід")},
    {"id": _id("org:Ланка А1"), "name": "Ланка А-1",
     "description": "Низовий підрозділ із кількома пілотами. Демонструє масове призначення через @members та ролі.",
     "parent_id": _id("org:Ескадрилья Альфа")},
    {"id": _id("org:Ланка А2"), "name": "Ланка А-2",
     "description": "Другий низовий підрозділ. Окремі ролі для спеціалізованого доступу.",
     "parent_id": _id("org:Ескадрилья Альфа")},
    {"id": _id("org:Ескадрилья Браво"), "name": "Ескадрилья «Браво»",
     "description": "Сестринський підрозділ до Альфи. Демонструє що сусідні підрозділи НЕ мають латерального доступу через обмін (вертикальна лінія).",
     "parent_id": _id("org:Авіабригада Схід")},
    # ── Tree B ──
    {"id": _id("org:Бригада Захід"), "name": "Бригада «Захід»",
     "description": "Зовнішня організація для демонстрації обміну ролями. Надає ролі бригаді «Схід» через обмін.",
     "parent_id": None},
    {"id": _id("org:Підрозділ З1"), "name": "Підрозділ З-1",
     "description": "Дочірній підрозділ «Заходу». Має власний обмін з Ескадрильєю Альфа (демо багаторівневого обміну).",
     "parent_id": _id("org:Бригада Захід")},
    {"id": _id("org:Підрозділ З2"), "name": "Підрозділ З-2",
     "description": "Другий дочірній підрозділ «Заходу». Доступний через вертикальну лінію після обміну.",
     "parent_id": _id("org:Бригада Захід")},
    # ── Tree C ──
    {"id": _id("org:Бригада Північ"), "name": "Бригада «Північ»",
     "description": "Друга зовнішня організація. Має обмін зі «Сходом», але ролі «Заходу» НЕ мають поширюватися сюди (демо зупинки поширення).",
     "parent_id": None},
    {"id": _id("org:Підрозділ П1"), "name": "Підрозділ П-1",
     "description": "Дочірній підрозділ «Півночі».",
     "parent_id": _id("org:Бригада Північ")},
]

# ── Users ────────────────────────────────────────────────────────────────────

USERS = [
    # superadmin
    {"id": _id("user:admin"), "username": "admin",
     "description": "Суперадмін. Бачить усі організації, ролі та ресурси. Може керувати всіма обмінами.",
     "password_hash": _pw("admin123"), "password": "admin123",
     "org_id": _id("org:Авіабригада Схід"),
     "is_superadmin": True, "is_org_admin": True},

    # Tree A admins
    {"id": _id("user:адмін-схід"), "username": "адмін-схід",
     "description": "Адмін бригади «Схід». Бачить своє піддерево та обміни. Може встановлювати обміни від імені бригади.",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Авіабригада Схід"),
     "is_superadmin": False, "is_org_admin": True},
    {"id": _id("user:адмін-альфа"), "username": "адмін-альфа",
     "description": "Адмін ескадрильї «Альфа». Демонструє багаторівневий обмін: самостійно встановив обмін з Підрозділом З-1 (кейс 5).",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Ескадрилья Альфа"),
     "is_superadmin": False, "is_org_admin": True},

    # Tree A pilots — low-level users for many-to-many demo (case 1)
    {"id": _id("user:пілот-а1-1"), "username": "пілот-а1-1",
     "description": "Пілот Ланки А-1. Отримує доступ до ефірів через @members (кейс 1: масове призначення). Також призначена роль «пілот» для спец. ресурсів.",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Ланка А1"),
     "is_superadmin": False, "is_org_admin": False},
    {"id": _id("user:пілот-а1-2"), "username": "пілот-а1-2",
     "description": "Другий пілот Ланки А-1. Демонструє що новий користувач одразу отримує базові дозволи через @members.",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Ланка А1"),
     "is_superadmin": False, "is_org_admin": False},
    {"id": _id("user:пілот-а1-3"), "username": "пілот-а1-3",
     "description": "Третій пілот Ланки А-1. Має лише @members — базові дозволи без спец. ролей.",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Ланка А1"),
     "is_superadmin": False, "is_org_admin": False},
    {"id": _id("user:пілот-а2-1"), "username": "пілот-а2-1",
     "description": "Пілот Ланки А-2. Окремий від А-1, але через @members ескадрильї має спільні дозволи рівня Альфа.",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Ланка А2"),
     "is_superadmin": False, "is_org_admin": False},

    # Dispatcher at brigade level (case 0: role as occupation)
    {"id": _id("user:диспетчер-схід"), "username": "диспетчер-схід",
     "description": "Диспетчер бригади «Схід» (кейс 0: роль як посада). Має роль «диспетчер», яка включає перегляд ресурсів підрозділів.",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Авіабригада Схід"),
     "is_superadmin": False, "is_org_admin": False},

    # Red specialist (case 3: color-based categorization)
    {"id": _id("user:червоний-спец"), "username": "червоний-спец",
     "description": "Спеціаліст «червоної» категорії (кейс 3: різне бандлювання ресурсів). Має широкий доступ до «червоних» ресурсів через свою роль, обмежений до інших.",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Ескадрилья Альфа"),
     "is_superadmin": False, "is_org_admin": False},

    # Tree B users
    {"id": _id("user:адмін-захід"), "username": "адмін-захід",
     "description": "Адмін бригади «Захід». Бачить обмін зі «Сходом» зі свого боку. Надає та приймає ролі через обмін (кейс 4).",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Бригада Захід"),
     "is_superadmin": False, "is_org_admin": True},
    {"id": _id("user:оператор-з1"), "username": "оператор-з1",
     "description": "Оператор Підрозділу З-1. Демонструє доступ через вертикальну лінію: отримує ролі, надані бригадою «Захід» через обмін.",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Підрозділ З1"),
     "is_superadmin": False, "is_org_admin": False},

    # Tree C user
    {"id": _id("user:адмін-північ"), "username": "адмін-північ",
     "description": "Адмін бригади «Північ». Має обмін зі «Сходом», але НЕ повинен бачити ролі «Заходу» (кейс 4б: зупинка поширення).",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Бригада Північ"),
     "is_superadmin": False, "is_org_admin": True},
    {"id": _id("user:аналітик-п1"), "username": "аналітик-п1",
     "description": "Аналітик Підрозділу П-1. Отримує лише ролі, надані безпосередньо «Півночі» зі «Сходу», без транзитивного витоку від «Заходу».",
     "password_hash": _pw("123"), "password": "123",
     "org_id": _id("org:Підрозділ П1"),
     "is_superadmin": False, "is_org_admin": False},
]

# ── Roles ────────────────────────────────────────────────────────────────────

ROLES = [
    # ── @members (auto-created, one per org) ──
    {"id": _id("role:Авіабригада Схід/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Авіабригада Схід"), "is_org_role": True},
    {"id": _id("role:Ескадрилья Альфа/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Ескадрилья Альфа"), "is_org_role": True},
    {"id": _id("role:Ланка А1/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Ланка А1"), "is_org_role": True},
    {"id": _id("role:Ланка А2/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Ланка А2"), "is_org_role": True},
    {"id": _id("role:Ескадрилья Браво/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Ескадрилья Браво"), "is_org_role": True},
    {"id": _id("role:Бригада Захід/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Бригада Захід"), "is_org_role": True},
    {"id": _id("role:Підрозділ З1/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Підрозділ З1"), "is_org_role": True},
    {"id": _id("role:Підрозділ З2/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Підрозділ З2"), "is_org_role": True},
    {"id": _id("role:Бригада Північ/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Бригада Північ"), "is_org_role": True},
    {"id": _id("role:Підрозділ П1/@members"), "name": "@members", "description": None,
     "org_id": _id("org:Підрозділ П1"), "is_org_role": True},

    # ── Tree A: occupation roles (case 0) ──
    {"id": _id("role:Авіабригада Схід/диспетчер"), "name": "диспетчер",
     "description": "Кейс 0: роль як посада. Диспетчер має перегляд ефірів усіх підрозділів бригади через включення ролей-переглядачів.",
     "org_id": _id("org:Авіабригада Схід"), "is_org_role": False},

    # ── Tree A: resource group roles (case 0, 1, 2, 3) ──
    # Ескадрилья Альфа roles
    {"id": _id("role:Ескадрилья Альфа/перегляд-загальний"), "name": "перегляд загальний",
     "description": "Кейс 0+1: роль як група ресурсів. Надає перегляд усіх загальних (несекретних) ефірів ескадрильї. Призначена через @members — кожен новий член автоматично отримує доступ.",
     "org_id": _id("org:Ескадрилья Альфа"), "is_org_role": False},
    {"id": _id("role:Ескадрилья Альфа/перегляд-секретний"), "name": "перегляд секретний",
     "description": "Кейс 2: багаторівневий доступ. Секретні ресурси доступні лише обраним користувачам ескадрильї та адмінам вищого рівня, але не поширюються назовні.",
     "org_id": _id("org:Ескадрилья Альфа"), "is_org_role": False},
    {"id": _id("role:Ескадрилья Альфа/пілот"), "name": "пілот",
     "description": "Кейс 0+1: роль як посада + масове призначення. Пілот має повний доступ (view+comment+stream) до ефірів. Додавання ресурсу до цієї ролі автоматично поширюється на всіх пілотів.",
     "org_id": _id("org:Ескадрилья Альфа"), "is_org_role": False},
    {"id": _id("role:Ескадрилья Альфа/червоний-адмін"), "name": "червоний адмін",
     "description": "Кейс 3: різне бандлювання. Широкий доступ до 'червоних' ресурсів, обмежений до 'зелених' та 'синіх'. Типовий для спеціалізованих категорій доступу.",
     "org_id": _id("org:Ескадрилья Альфа"), "is_org_role": False},
    {"id": _id("role:Ескадрилья Альфа/зелений-адмін"), "name": "зелений адмін",
     "description": "Кейс 3: аналогічно до 'червоного адміна', але для 'зелених' ресурсів. Демонструє що категорії — нелінійна шкала, а розгалужена структура.",
     "org_id": _id("org:Ескадрилья Альфа"), "is_org_role": False},

    # Roles for exchange sharing (case 4)
    {"id": _id("role:Авіабригада Схід/для-заходу"), "name": "для Заходу",
     "description": "Кейс 4: обмін ролями. Ця роль надається партнеру «Захід» через обмін — фактично запит: «надайте своїм ресурсам доступ для цієї ролі».",
     "org_id": _id("org:Авіабригада Схід"), "is_org_role": False},
    {"id": _id("role:Авіабригада Схід/для-півночі"), "name": "для Півночі",
     "description": "Кейс 4: друга обмінна роль для партнера «Північ». Використовується для демонстрації зупинки поширення.",
     "org_id": _id("org:Авіабригада Схід"), "is_org_role": False},
    {"id": _id("role:Ескадрилья Альфа/для-з1"), "name": "для З-1",
     "description": "Кейс 5: обмінна роль дочірнього підрозділу. Альфа самостійно встановила обмін з Підрозділом З-1.",
     "org_id": _id("org:Ескадрилья Альфа"), "is_org_role": False},

    # ── Tree B roles ──
    {"id": _id("role:Бригада Захід/оператор"), "name": "оператор",
     "description": "Кейс 4: роль «Заходу», яка включає обмінну роль зі «Сходу». Оператори «Заходу» отримують доступ до ресурсів «Сходу» через цю роль.",
     "org_id": _id("org:Бригада Захід"), "is_org_role": False},
    {"id": _id("role:Бригада Захід/для-сходу"), "name": "для Сходу",
     "description": "Кейс 4: зустрічна обмінна роль. «Захід» надає цю роль «Сходу», щоб «Схід» міг призначити доступ до ресурсів «Заходу».",
     "org_id": _id("org:Бригада Захід"), "is_org_role": False},
    {"id": _id("role:Підрозділ З1/технік"), "name": "технік",
     "description": "Кейс 5: роль дочірнього підрозділу «Заходу». Включає обмінну роль від Ескадрильї Альфа.",
     "org_id": _id("org:Підрозділ З1"), "is_org_role": False},
    {"id": _id("role:Підрозділ З1/для-альфи"), "name": "для Альфи",
     "description": "Кейс 5: зустрічна обмінна роль від Підрозділу З-1 для Ескадрильї Альфа.",
     "org_id": _id("org:Підрозділ З1"), "is_org_role": False},

    # ── Tree C roles ──
    {"id": _id("role:Бригада Північ/аналітик"), "name": "аналітик",
     "description": "Кейс 4б: роль «Півночі», що включає обмінну роль зі «Сходу». Ролі «Заходу» НЕ досягають цієї ролі завдяки зупинці поширення.",
     "org_id": _id("org:Бригада Північ"), "is_org_role": False},
    {"id": _id("role:Бригада Північ/для-сходу"), "name": "для Сходу",
     "description": "Кейс 4: зустрічна обмінна роль від «Півночі».",
     "org_id": _id("org:Бригада Північ"), "is_org_role": False},
]

# ── Role inclusions ──────────────────────────────────────────────────────────

ROLE_INCLUSIONS = [
    # @members chain (child → parent)
    {"role_id": _id("role:Ескадрилья Альфа/@members"), "included_role_id": _id("role:Авіабригада Схід/@members")},
    {"role_id": _id("role:Ланка А1/@members"), "included_role_id": _id("role:Ескадрилья Альфа/@members")},
    {"role_id": _id("role:Ланка А2/@members"), "included_role_id": _id("role:Ескадрилья Альфа/@members")},
    {"role_id": _id("role:Ескадрилья Браво/@members"), "included_role_id": _id("role:Авіабригада Схід/@members")},
    {"role_id": _id("role:Підрозділ З1/@members"), "included_role_id": _id("role:Бригада Захід/@members")},
    {"role_id": _id("role:Підрозділ З2/@members"), "included_role_id": _id("role:Бригада Захід/@members")},
    {"role_id": _id("role:Підрозділ П1/@members"), "included_role_id": _id("role:Бригада Північ/@members")},

    # Case 0+1: @members includes перегляд-загальний → every member of Альфа sees general broadcasts
    {"role_id": _id("role:Ескадрилья Альфа/@members"), "included_role_id": _id("role:Ескадрилья Альфа/перегляд-загальний")},

    # Case 0: диспетчер includes перегляд-загальний (dispatcher sees squadron broadcasts)
    {"role_id": _id("role:Авіабригада Схід/диспетчер"), "included_role_id": _id("role:Ескадрилья Альфа/перегляд-загальний")},

    # Case 1: пілот includes перегляд-загальний (pilot inherits general view + gets own permissions)
    {"role_id": _id("role:Ескадрилья Альфа/пілот"), "included_role_id": _id("role:Ескадрилья Альфа/перегляд-загальний")},

    # Case 2: пілот includes перегляд-секретний (pilots see secret resources)
    {"role_id": _id("role:Ескадрилья Альфа/пілот"), "included_role_id": _id("role:Ескадрилья Альфа/перегляд-секретний")},

    # Case 3: червоний-адмін includes перегляд-загальний (red admin gets baseline view)
    {"role_id": _id("role:Ескадрилья Альфа/червоний-адмін"), "included_role_id": _id("role:Ескадрилья Альфа/перегляд-загальний")},
    # Case 3: зелений-адмін includes перегляд-загальний
    {"role_id": _id("role:Ескадрилья Альфа/зелений-адмін"), "included_role_id": _id("role:Ескадрилья Альфа/перегляд-загальний")},

    # Case 4: Захід/оператор includes Схід/для-заходу (foreign role via exchange)
    {"role_id": _id("role:Бригада Захід/оператор"), "included_role_id": _id("role:Авіабригада Схід/для-заходу")},

    # Case 4: Схід/диспетчер includes Захід/для-сходу (reverse direction)
    {"role_id": _id("role:Авіабригада Схід/диспетчер"), "included_role_id": _id("role:Бригада Захід/для-сходу")},

    # Case 4b: Північ/аналітик includes Схід/для-півночі (foreign role via exchange)
    {"role_id": _id("role:Бригада Північ/аналітик"), "included_role_id": _id("role:Авіабригада Схід/для-півночі")},

    # Case 4: Схід/для-півночі includes Захід/для-сходу
    # This is the KEY propagation test: Захід→Схід→Північ should be BLOCKED
    # because Північ is NOT on Захід's vertical line after crossing into Схід
    {"role_id": _id("role:Авіабригада Схід/для-півночі"), "included_role_id": _id("role:Бригада Захід/для-сходу")},

    # Case 5: З1/технік includes Альфа/для-з1 (sub-org exchange)
    {"role_id": _id("role:Підрозділ З1/технік"), "included_role_id": _id("role:Ескадрилья Альфа/для-з1")},

    # Case 5: Альфа/пілот includes З1/для-альфи (reverse sub-org exchange)
    {"role_id": _id("role:Ескадрилья Альфа/пілот"), "included_role_id": _id("role:Підрозділ З1/для-альфи")},
]

# ── Resources ────────────────────────────────────────────────────────────────

RESOURCES = [
    # ── Ескадрилья Альфа resources ──
    # Green (загальні ефіри — broadcasts for case 1)
    {"id": _id("res:Альфа/ефір-зелений-1"), "name": "Ефір «Зелений-1»",
     "description": "Кейс 1+3: загальний ефір, доступний через @members ескадрильї. Додавання нового такого ефіру і призначення ролі «перегляд загальний» одразу надає доступ усім членам.",
     "resource_type": "video", "org_id": _id("org:Ескадрилья Альфа")},
    {"id": _id("res:Альфа/ефір-зелений-2"), "name": "Ефір «Зелений-2»",
     "description": "Кейс 1: другий загальний ефір. Демонструє масовий доступ через одну роль.",
     "resource_type": "video", "org_id": _id("org:Ескадрилья Альфа")},

    # Red (секретні — for case 2, 3)
    {"id": _id("res:Альфа/карта-червона"), "name": "Карта «Червона»",
     "description": "Кейс 2+3: секретний документ 'червоної' категорії. Доступний лише через роль «перегляд секретний» або «червоний адмін».",
     "resource_type": "document", "org_id": _id("org:Ескадрилья Альфа")},
    {"id": _id("res:Альфа/ефір-червоний"), "name": "Ефір «Червоний»",
     "description": "Кейс 3: секретний ефір 'червоної' категорії. 'Червоний адмін' має повний доступ, інші — обмежений або відсутній.",
     "resource_type": "video", "org_id": _id("org:Ескадрилья Альфа")},

    # Blue (адмін/логістика — for case 3)
    {"id": _id("res:Альфа/звіт-синій"), "name": "Звіт «Синій»",
     "description": "Кейс 3: адміністративний документ 'синьої' категорії. 'Червоний адмін' має лише перегляд, 'зелений адмін' — теж лише перегляд.",
     "resource_type": "document", "org_id": _id("org:Ескадрилья Альфа")},

    # ── Авіабригада Схід resources ──
    {"id": _id("res:Схід/наказ"), "name": "Наказ бригади",
     "description": "Загальний наказ рівня бригади. Доступний через @members бригади (каскадується вниз до всіх підрозділів).",
     "resource_type": "document", "org_id": _id("org:Авіабригада Схід")},

    # ── Бригада Захід resources ──
    {"id": _id("res:Захід/ефір-захід"), "name": "Ефір «Захід»",
     "description": "Кейс 4: ресурс «Заходу», доступ до якого надається «Сходу» через обмінну роль «для Сходу». Диспетчер «Сходу» бачить цей ефір.",
     "resource_type": "video", "org_id": _id("org:Бригада Захід")},
    {"id": _id("res:Захід/звіт-захід"), "name": "Звіт «Захід»",
     "description": "Кейс 4: документ «Заходу». Доступний оператору «Заходу» через обмінну роль «для Заходу».",
     "resource_type": "document", "org_id": _id("org:Бригада Захід")},

    # ── Підрозділ З-1 resources ──
    {"id": _id("res:З1/ефір-з1"), "name": "Ефір «З-1»",
     "description": "Кейс 5: ресурс дочірнього підрозділу «Заходу». Пілоти «Альфа» отримують доступ через багаторівневий обмін (Альфа↔З-1).",
     "resource_type": "video", "org_id": _id("org:Підрозділ З1")},

    # ── Бригада Північ resources ──
    {"id": _id("res:Північ/аналітика"), "name": "Аналітика «Північ»",
     "description": "Кейс 4б: ресурс «Півночі». Роль «для Півночі» від «Сходу» надає доступ, але ролі «Заходу» сюди НЕ доходять.",
     "resource_type": "document", "org_id": _id("org:Бригада Північ")},
]

# ── Role-resource permissions ────────────────────────────────────────────────
# document: read=1, write=2
# video: view=1, comment=2, stream=4

PERMISSIONS = [
    # Case 1: перегляд-загальний gives view(1) to green broadcasts
    {"role_id": _id("role:Ескадрилья Альфа/перегляд-загальний"), "resource_id": _id("res:Альфа/ефір-зелений-1"), "permission_bits": 1},
    {"role_id": _id("role:Ескадрилья Альфа/перегляд-загальний"), "resource_id": _id("res:Альфа/ефір-зелений-2"), "permission_bits": 1},

    # Case 0+1: пілот gets full access (view+comment+stream=7) to green broadcasts
    {"role_id": _id("role:Ескадрилья Альфа/пілот"), "resource_id": _id("res:Альфа/ефір-зелений-1"), "permission_bits": 7},
    {"role_id": _id("role:Ескадрилья Альфа/пілот"), "resource_id": _id("res:Альфа/ефір-зелений-2"), "permission_bits": 7},

    # Case 2: перегляд-секретний gives read(1) to red resources
    {"role_id": _id("role:Ескадрилья Альфа/перегляд-секретний"), "resource_id": _id("res:Альфа/карта-червона"), "permission_bits": 1},
    {"role_id": _id("role:Ескадрилья Альфа/перегляд-секретний"), "resource_id": _id("res:Альфа/ефір-червоний"), "permission_bits": 1},

    # Case 3: червоний-адмін gets full access to red, view-only to green & blue
    {"role_id": _id("role:Ескадрилья Альфа/червоний-адмін"), "resource_id": _id("res:Альфа/карта-червона"), "permission_bits": 3},  # read+write
    {"role_id": _id("role:Ескадрилья Альфа/червоний-адмін"), "resource_id": _id("res:Альфа/ефір-червоний"), "permission_bits": 7},  # view+comment+stream
    {"role_id": _id("role:Ескадрилья Альфа/червоний-адмін"), "resource_id": _id("res:Альфа/звіт-синій"), "permission_bits": 1},    # read only

    # Case 3: зелений-адмін gets full video access to green, read-only to blue & red
    {"role_id": _id("role:Ескадрилья Альфа/зелений-адмін"), "resource_id": _id("res:Альфа/ефір-зелений-1"), "permission_bits": 7},
    {"role_id": _id("role:Ескадрилья Альфа/зелений-адмін"), "resource_id": _id("res:Альфа/ефір-зелений-2"), "permission_bits": 7},
    {"role_id": _id("role:Ескадрилья Альфа/зелений-адмін"), "resource_id": _id("res:Альфа/звіт-синій"), "permission_bits": 1},
    {"role_id": _id("role:Ескадрилья Альфа/зелений-адмін"), "resource_id": _id("res:Альфа/карта-червона"), "permission_bits": 1},

    # Brigade-level: @members of Авіабригада gets read on наказ
    {"role_id": _id("role:Авіабригада Схід/@members"), "resource_id": _id("res:Схід/наказ"), "permission_bits": 1},

    # Case 4: для-заходу gets read on наказ (Захід operators see Схід's order)
    {"role_id": _id("role:Авіабригада Схід/для-заходу"), "resource_id": _id("res:Схід/наказ"), "permission_bits": 1},

    # Case 4: для-сходу gives view on Захід's broadcast
    {"role_id": _id("role:Бригада Захід/для-сходу"), "resource_id": _id("res:Захід/ефір-захід"), "permission_bits": 1},
    # Case 4: для-заходу: Захід оператор also reads Захід's report through own role
    {"role_id": _id("role:Бригада Захід/оператор"), "resource_id": _id("res:Захід/звіт-захід"), "permission_bits": 3},

    # Case 4b: для-півночі gives read on наказ to Північ
    {"role_id": _id("role:Авіабригада Схід/для-півночі"), "resource_id": _id("res:Схід/наказ"), "permission_bits": 1},

    # Case 4: Північ grants access on their resource to the exchange role
    {"role_id": _id("role:Бригада Північ/для-сходу"), "resource_id": _id("res:Північ/аналітика"), "permission_bits": 1},

    # Case 5: для-з1 gives view on green broadcasts to З-1
    {"role_id": _id("role:Ескадрилья Альфа/для-з1"), "resource_id": _id("res:Альфа/ефір-зелений-1"), "permission_bits": 1},

    # Case 5: для-альфи gives view on З-1's broadcast to Альфа
    {"role_id": _id("role:Підрозділ З1/для-альфи"), "resource_id": _id("res:З1/ефір-з1"), "permission_bits": 1},

    # Case 5: З-1 технік also sees their own resource
    {"role_id": _id("role:Підрозділ З1/технік"), "resource_id": _id("res:З1/ефір-з1"), "permission_bits": 7},
]

# ── User roles ───────────────────────────────────────────────────────────────

USER_ROLES = [
    # @members auto-assignments
    {"user_id": _id("user:admin"), "role_id": _id("role:Авіабригада Схід/@members")},
    {"user_id": _id("user:адмін-схід"), "role_id": _id("role:Авіабригада Схід/@members")},
    {"user_id": _id("user:диспетчер-схід"), "role_id": _id("role:Авіабригада Схід/@members")},
    {"user_id": _id("user:адмін-альфа"), "role_id": _id("role:Ескадрилья Альфа/@members")},
    {"user_id": _id("user:червоний-спец"), "role_id": _id("role:Ескадрилья Альфа/@members")},
    {"user_id": _id("user:пілот-а1-1"), "role_id": _id("role:Ланка А1/@members")},
    {"user_id": _id("user:пілот-а1-2"), "role_id": _id("role:Ланка А1/@members")},
    {"user_id": _id("user:пілот-а1-3"), "role_id": _id("role:Ланка А1/@members")},
    {"user_id": _id("user:пілот-а2-1"), "role_id": _id("role:Ланка А2/@members")},
    {"user_id": _id("user:адмін-захід"), "role_id": _id("role:Бригада Захід/@members")},
    {"user_id": _id("user:оператор-з1"), "role_id": _id("role:Підрозділ З1/@members")},
    {"user_id": _id("user:адмін-північ"), "role_id": _id("role:Бригада Північ/@members")},
    {"user_id": _id("user:аналітик-п1"), "role_id": _id("role:Підрозділ П1/@members")},

    # Occupation role assignments
    {"user_id": _id("user:диспетчер-схід"), "role_id": _id("role:Авіабригада Схід/диспетчер")},
    {"user_id": _id("user:пілот-а1-1"), "role_id": _id("role:Ескадрилья Альфа/пілот")},
    {"user_id": _id("user:пілот-а1-2"), "role_id": _id("role:Ескадрилья Альфа/пілот")},
    {"user_id": _id("user:пілот-а2-1"), "role_id": _id("role:Ескадрилья Альфа/пілот")},

    # Case 3: color specialist
    {"user_id": _id("user:червоний-спец"), "role_id": _id("role:Ескадрилья Альфа/червоний-адмін")},

    # Tree B
    {"user_id": _id("user:адмін-захід"), "role_id": _id("role:Бригада Захід/оператор")},
    {"user_id": _id("user:оператор-з1"), "role_id": _id("role:Підрозділ З1/технік")},

    # Tree C
    {"user_id": _id("user:адмін-північ"), "role_id": _id("role:Бригада Північ/аналітик")},
    {"user_id": _id("user:аналітик-п1"), "role_id": _id("role:Бригада Північ/аналітик")},
]

# ── Org exchanges ────────────────────────────────────────────────────────────

EXCHANGES = [
    # Case 4: Авіабригада Схід ↔ Бригада Захід (main cross-org exchange)
    {"id": _id("exchange:Авіабригада Схід+Бригада Захід"),
     "org_a_id": min(_id("org:Авіабригада Схід"), _id("org:Бригада Захід")),
     "org_b_id": max(_id("org:Авіабригада Схід"), _id("org:Бригада Захід"))},
    # Case 4b: Авіабригада Схід ↔ Бригада Північ (for propagation stop demo)
    {"id": _id("exchange:Авіабригада Схід+Бригада Північ"),
     "org_a_id": min(_id("org:Авіабригада Схід"), _id("org:Бригада Північ")),
     "org_b_id": max(_id("org:Авіабригада Схід"), _id("org:Бригада Північ"))},
    # Case 5: Ескадрилья Альфа ↔ Підрозділ З-1 (sub-org exchange)
    {"id": _id("exchange:Ескадрилья Альфа+Підрозділ З1"),
     "org_a_id": min(_id("org:Ескадрилья Альфа"), _id("org:Підрозділ З1")),
     "org_b_id": max(_id("org:Ескадрилья Альфа"), _id("org:Підрозділ З1"))},
]

# ── Exchange roles ───────────────────────────────────────────────────────────

EXCHANGE_ROLES = [
    # Схід ↔ Захід: both sides expose roles
    {"exchange_id": _id("exchange:Авіабригада Схід+Бригада Захід"),
     "role_id": _id("role:Авіабригада Схід/для-заходу")},
    {"exchange_id": _id("exchange:Авіабригада Схід+Бригада Захід"),
     "role_id": _id("role:Бригада Захід/для-сходу")},
    # Схід ↔ Північ: both sides expose roles
    {"exchange_id": _id("exchange:Авіабригада Схід+Бригада Північ"),
     "role_id": _id("role:Авіабригада Схід/для-півночі")},
    {"exchange_id": _id("exchange:Авіабригада Схід+Бригада Північ"),
     "role_id": _id("role:Бригада Північ/для-сходу")},
    # Альфа ↔ З-1: both sides expose roles
    {"exchange_id": _id("exchange:Ескадрилья Альфа+Підрозділ З1"),
     "role_id": _id("role:Ескадрилья Альфа/для-з1")},
    {"exchange_id": _id("exchange:Ескадрилья Альфа+Підрозділ З1"),
     "role_id": _id("role:Підрозділ З1/для-альфи")},
]


# ────────────────────────────────────────────────────────────────────────────

_ALL_TABLES = [
    ("organizations", ORGS),
    ("users", USERS),
    ("roles", ROLES),
    ("role_inclusions", ROLE_INCLUSIONS),
    ("resources", RESOURCES),
    ("role_resource_permissions", PERMISSIONS),
    ("user_roles", USER_ROLES),
    ("org_exchanges", EXCHANGES),
    ("exchange_roles", EXCHANGE_ROLES),
]


async def reset(db: AsyncSession) -> None:
    """Truncate all tables and re-insert seed data."""
    await db.execute(text(
        "TRUNCATE organizations, users, resources, roles, "
        "role_inclusions, role_resource_permissions, user_roles, "
        "org_exchanges, exchange_roles CASCADE"
    ))

    for table, rows in _ALL_TABLES:
        if not rows:
            continue
        cols = list(rows[0].keys())
        col_list = ", ".join(cols)
        val_list = ", ".join(f":{c}" for c in cols)
        stmt = text(f"INSERT INTO {table} ({col_list}) VALUES ({val_list})")
        for row in rows:
            await db.execute(stmt, row)

    await db.commit()
