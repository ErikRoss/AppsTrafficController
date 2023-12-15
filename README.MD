## Хост

**URL:** `http://38.54.122.209:5000/api`

## Аутентификация

Для аутентификации при запросах используется токен доступа, который необходимо передавать в заголовке `Authorization` вместе с префиксом `Bearer`. Получить токен можно при помощи запроса на эндпоинт `/login`.

```
Authorization: Bearer <access_token>
```

## Эндпоинты

### Авторизация

**URL:** `/login`

**Метод:** `POST`

**Доступ:** `admin`, `user`

**Тело запроса:**

```json
{
    "username": "testuser",
    "password": "testpassword"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `username` | Строка | Имя пользователя | Да | 50 |
| `password` | Строка | Пароль | Да | 120 |

**Ответ в случае успеха**

```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "user": {
        "domains": [],
        "email": "test2@test.com",
        "id": 7,
        "telegram": "testtelegram",
        "username": "testuser-2"
    }
}
```
**\*access_token** - токен доступа, который необходимо использовать для авторизации в других запросах.


### Регистрация пользователя

**URL:** `/users/register`

**Метод:** `POST`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "username": "testuser",
    "email": "test@test.com",
    "password": "testpassword",
    "telegram": "testtelegram",
    "role": "user"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `username` | Строка | Уникальное имя пользователя | Да | 50 |
| `email` | Строка | Уникальный Email | Да | 120 |
| `password` | Строка | Пароль | Да | 120 |
| `telegram` | Строка | Telegram | Нет | 35 |
| `role` | Строка | Роль пользователя (`user` или `admin`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "User registered successfully."
}
```

### Получение списка всех пользователей

**URL:** `/users`

**Метод:** `GET`

**Доступ:** `admin`

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|page|Целое число|Номер страницы|Нет (default: 1)||
|per_page|Целое число|Количество записей на странице|Нет (default: 50)||
|search_query|Строка|Поиск по `username`/`email`/`telegram` пользователя|Нет||

**Ответ:**

```json
{
    "users": [
        {
            "allowed_apps": [
                {
                    "id": 18,
                    "title": "Test App 1"
                }
            ],
            "domains": [
                {
                    "domain": "test.com",
                    "id": 1
                },
                {
                    "domain": "test2.com",
                    "id": 2
                }
            ],
            "email": "test@test.com",
            "id": 1,
            "telegram": "testtelegram",
            "username": "testuser",
            "status": "active",
            "balance": 0.00,
            "role": "user"
        },
        {
            "allowed_apps": [],
            "domains": [],
            "email": "test2@test.com",
            "id": 2,
            "telegram": "testtelegram2",
            "username": "testuser2",
            "status": "active",
            "balance": 0.00,
            "role": "admin"
        }
    ]
}
```

### Получение пользователя по ID

**URL:** `/users/<int:user_id>`

**Метод:** `GET`

**Доступ:** `admin`, `user` c `user.id` = `user_id`

**Ответ:**

```json
{
    "user": {
        "allowed_apps": [],
        "domains": [],
        "email": "test@test.com",
        "id": 1,
        "username": "testuser",
        "telegram": "testtelegram",
        "status": "active",
        "balance": 0.00,
        "role": "user"
    }
}
```

### Изменение статуса пользователя

**URL:** `/users/update_status`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "status": "inactive"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID пользователя | Да | |
| `status` | Строка | Статус пользователя (`active` или `inactive`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "User status updated successfully."
}
```

### Изменение роли пользователя

**URL:** `/users/update_role`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "role": "admin"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID пользователя | Да | |
| `role` | Строка | Роль пользователя (`user` или `admin`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "User role updated successfully."
}
```

### Пополнение баланса пользователя

**URL:** `/users/add_balance`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "amount": 100
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID пользователя | Да | |
| `amount` | Число с плавающей запятой | Сумма пополнения | Да | |

**Ответ в случае успеха:**

```json
{
    "message": "User balance added successfully."
}
```

### Списание средств с баланса пользователя

**URL:** `/users/subtract_balance`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "amount": 100
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID пользователя | Да | |
| `amount` | Число с плавающей запятой | Сумма списания | Да | |

**Ответ в случае успеха:**

```json
{
    "message": "User balance subtracted successfully."
}
```

### Получить список транзакций пользователя

**URL:** `/users/<int:user_id>/transactions`

**Метод:** `GET`

**Доступ:** `admin`, `user` c `user.id` = `user_id`

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|search_query|Строка|Поиск по причине транзакции (`domain purchase`, `conversion install`, `conversion registration`, `conversion deposit`)|Нет||

**Ответ:**

```json
{
    "transactions": [
        {
            "id": 1,
            "transaction_type": "+",
            "amount": 100.00,
            "reason": "admin deposit",
            "geo": null,
            "timestamp": "Tue, 17 Oct 2023 00:00:00 GMT"
        },
        {
            "id": 2,
            "transaction_type": "-",
            "amount": 15.00,
            "reason": "domain purchase",
            "geo": "US",
            "timestamp": "Tue, 17 Oct 2023 00:00:00 GMT"
        },
        {
            "id": 3,
            "transaction_type": "-",
            "amount": 0.10,
            "reason": "conversion install",
            "geo": "US",
            "timestamp": "Tue, 17 Oct 2023 00:00:00 GMT"
        }
    ]
}
```

### Обновление пароля пользователя

**URL:** `/users/update_password`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "password": "newpassword"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID пользователя | Да | |
| `password` | Строка | Новый пароль | Да | 120 |

**Ответ в случае успеха:**

```json
{
    "message": "New password set successfully."
}
```

### Получить всех своих подпользователей (пользователей, которые привязаны к данному пользователю)

**URL:** `/users/subusers`

**Метод:** `GET`

**Доступ:** `admin`, `user`

**Ответ:**

```json
{
    "subusers": [
        {
            "name": "subuser1",
            "color": "#000000",
            "id": 1,
            "description": "subuser1 description"
        },
        {
            "name": "subuser2",
            "color": "#000000",
            "id": 2,
            "description": "subuser2 description"
        }
    ]
}
```

### Добавить подпользователя

**URL:** `/users/subusers/add`

**Метод:** `POST`

**Доступ:** `admin`, `user`

**Тело запроса:**

```json
{
    "name": "subuser1",
    "color": "#000000",
    "description": "subuser1 description"
}
```

**Ответ в случае успеха:**

```json
{
    "message": "Subuser added successfully."
}
```

### Загрузка файла

**URL:** `/upload_file`

**Метод:** `POST`

**Тело запроса:**

```json
{
    "file": "image1.png"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `file` | Файл | Загружаемый файл | Да | |

**Примечание:** если загружается архив, в нём должен находиться файл `index.html`, иначе будет возвращена ошибка `400`.

**Ответ в случае успеха:**

```json
{
    "file": "1697372400249729.png",
    "folder": "static/img/uploads"
}
```

### Получение списка всех тегов приложений

**URL:** `/apps/tags`

**Метод:** `GET`

**Доступ:** `admin`, `user`

**Ответ:**

```json
{
    "tags": [
        {
            "id": 1,
            "tag": "tag1",
            "apps": [
                1,
                2,
                3
            ]
        },
        {
            "id": 2,
            "tag": "tag2",
            "apps": [
                4
            ]
        }
    ]
}
```

### Добавление нового тега приложения

**URL:** `/apps/tags/add`

**Метод:** `POST`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "tag": "tag5"
}
```

**Ответ в случае успеха:**

```json
{
    "message": "Tag added successfully."
}
```

### Получение списка всех приложений

**URL:** `/apps`

**Метод:** `GET`

**Доступ:** `admin`, `user` (список активных приложений)

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|page|Целое число|Номер страницы|Нет (default: 1)||
|per_page|Целое число|Количество записей на странице|Нет (default: 50)||
|search_query|Строка|Поиск по `title`/`tags` приложения|Нет||

**Ответ для `admin`:**

```json
{
    "apps": [
        {
            "allowed_users": [
                {
                    "id": 1,
                    "username": "test_admin"
                },
                {
                    "id": 2,
                    "username": "test_user"
                }
            ],
            "id": 1,
            "title": "My App",
            "url": "https://myapp.com",
            "image": "static/img/uploads/1697372400249729.png",
            "operating_system": "iOS",
            "tags": ["tag1", "tag2"],
            "unique_tag": "myapp",
            "description": "My App description",
            "status": "active"
        },
        {
            "allowed_users": [],
            "id": 2,
            "title": "Another App",
            "url": "https://anotherapp.com",
            "image": "static/img/uploads/1697382997814109.png",
            "operating_system": "Android",
            "tags": ["tag3", "tag4"],
            "unique_tag": "anotherapp",
            "description": "Another App description",
            "status": "inactive"
        }
    ]
}
```

**Ответ для `user`:**

```json
{
    "apps": [
        {
            "id": 1,
            "title": "My App",
            "image": "static/img/uploads/1697372400249729.png",
            "operating_system": "iOS",
            "tags": ["tag1", "tag2"]
        },
        {
            "id": 2,
            "title": "Another App",
            "image": "static/img/uploads/1697382997814109.png",
            "operating_system": "Android",
            "tags": ["tag3", "tag4"]
        }
    ]
}
```

### Получение приложения по ID

**URL:** `/apps/<int:app_id>`

**Метод:** `GET`

**Доступ:** `admin`, `user`, если приложение активно и разрешено для пользователя

**Ответ для `admin`**

```json
{
    "app": {
        "allowed_users": [
            {
                "id": 1,
                "username": "test_admin"
            },
            {
                "id": 2,
                "username": "test_user"
            }
        ],
        "id": 1,
        "title": "My App",
        "url": "https://myapp.com",
        "image": "static/img/uploads/1697372400249729.png",
        "operating_system": "iOS",
        "tags": ["tag1", "tag2"],
        "unique_tag": "myapp",
        "description": "My App description",
        "status": "active"
    }
}
```

**Ответ для `user`**

```json
{
    "app": {
        "id": 1,
        "title": "My App",
        "image": "static/img/uploads/1697372400249729.png",
        "operating_system": "iOS",
        "tags": ["tag1", "tag2"]
    }
}
```

### Проверка уникальности названия приложения

**URL:** `apps/check_title`

**Метод:** `POST`

**Тело запроса:**

```json
{
    "title": "My App"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `title` | Строка | Название приложения | Да | 120 |

**Ответ в случае успеха:**

```json
{
    "message": "App title is unique."
}
```

**Ответ в случае ошибки:**

```json
{
    "error": "An app with this title already exists."
}
```

### Проверка уникальности URL приложения

**URL:** `apps/check_url`

**Метод:** `POST`

**Тело запроса:**

```json
{
    "url": "https://myapp.com"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `url` | Строка | URL приложения | Да | 120 |

**Ответ в случае успеха:**

```json
{
    "message": "App URL is unique."
}
```

**Ответ в случае ошибки:**

```json
{
    "error": "An app with this URL already exists."
}
```

### Добавление нового приложения

**URL:** `/apps/add`

**Метод:** `POST`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "title": "My New App",
    "url": "https://mynewapp.com",
    "image": "image3.png",
    "image_folder": "static/img/uploads",
    "operating_system": "ios",
    "tags": ["control", "test"],
    "description": "My New App description",
    "status": "active"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `title` | Строка | Название приложения | Да | 120 |
| `url` | Строка | URL приложения | Да | 120 |
| `image` | Строка | Файл изображения | Нет | 25 |
| `image_folder` | Строка | Папка с изображением | Нет | 230 |
| `operating_system` | Строка | Операционная система, для которой предназначено приложение | Да | 20 |
| `tags` | Список строк | Список тегов, связанных с приложением | Нет | 25 символов/tag |
| `description` | Строка | Описание приложения | Нет | 256 |
| `status` | Строка | Статус приложения (`active` или `inactive`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "App added successfully."
}
```

**Ответы в случае ошибки:**

```json
{
    "error": "An app with this title already exists."
}
```

```json
{
    "error": "An app with this unique tag already exists."
}
```

```json
{
    "error": "An app with this URL already exists."
}
```

### Изменение статуса приложения

**URL:** `/apps/update_status`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "status": "inactive"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID приложения | Да | |
| `status` | Строка | Статус приложения (`active`, `inactive`, `banned`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "App status updated successfully."
}
```

### Добавление разрешённых пользователей для приложения

**URL:** `/apps/allow_for_users`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "users": [
        1, 
        2, 
        3
        ]
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID приложения | Да | |
| `users` | Список | Список ID пользователей | Да | |

**Ответ в случае успеха:**

```json
{
    "message": "App allowed for users successfully."
}
```

### Удаление разрешённых пользователей для приложения

**URL:** `/apps/disallow_for_users`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "users": [
        1, 
        2, 
        3
        ]
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID приложения | Да | |
| `users` | Список | Список ID пользователей | Да | |

**Ответ в случае успеха:**

```json
{
    "message": "App disallowed for users successfully."
}
```

### Удаление приложения

**URL:** `/apps/delete/<int:app_id>`

**Метод:** `DELETE`

**Доступ:** `admin`

**Ответ в случае успеха:**

```json
{
    "message": "App deleted successfully."
}
```

### Получение списка всех кампаний

**URL:** `/campaigns`

**Метод:** `GET`

**Доступ:** `admin` (список всех кампаний), `user` (список кампаний пользователя)

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|page|Целое число|Номер страницы|Нет (default: 1)||
|per_page|Целое число|Количество записей на странице|Нет (default: 50)||
|search_query|Строка|Поиск по `title` кампании|Нет||
|archived|Булево|Показать архивные/неархивные/все кампании (`true`, `false`, `null`)|Нет (default: null)||

**Ответ:**

```json
{
  "campaigns": [
    {
      "apps": [
        {
          "description": "My New App 2 description",
          "id": 2,
          "image": "image2.png",
          "operating_system": "Android",
          "status": "inactive",
          "tags": [
            "tag1",
            "tag3"
          ],
          "title": "My New App 2",
          "unique_tag": "mynewapp2",
          "url": "https://mynewapp2.com"
        }
      ],
      "archived": false,
      "custom_parameters": {},
      "description": "My Campaign description",
      "geo": "US",
      "hash_code": "eb1d81ece0abb0e2850ba90949581c1a01dbc2de9ce32f46175600cf110f09e0",
      "id": 6,
      "landing_page": "landing2.php",
      "status": null,
      "title": "My Campaign",
      "user_id": 1,
      "user_name": "testuser",
      "subuser": {
        "id": 1,
        "name": "subuser1",
        "color": "#000000",
        "description": "subuser1 description"
      }
    },
    {
      "apps": [
        {
          "description": "My New App description",
          "id": 9,
          "image": "image3.png",
          "operating_system": "iOS",
          "status": "active",
          "tags": [
            "tag1",
            "tag2"
          ],
          "title": "My New App 4",
          "unique_tag": "mynewapp4",
          "url": "https://mynewapp4.com"
        },
        {
          "description": "My New App description",
          "id": 8,
          "image": "image3.png",
          "operating_system": "iOS",
          "status": "active",
          "tags": [
            "tag1",
            "tag2"
          ],
          "title": "My New App 3",
          "unique_tag": "mynewapp3",
          "url": "https://mynewapp3.com"
        }
      ],
    "archived": true,
      "custom_parameters": {
        "param1": "value1",
        "param2": "value2"
      },
      "description": "My New Campaign description",
      "geo": "US",
      "hash_code": "b85b82bcae58c39ea585e99c1362b098d1604f6f639bd697c9454aed945557b8",
      "id": 7,
      "landing_page": "landing2.php",
      "status": "inactive",
      "title": "My New Campaign",
      "user_id": 1,
      "user_name": "testuser",
      "subuser": null
    }
  ]
}
```

### Получение кампании по ID

**URL:** `/campaigns/<int:campaign_id>`

**Метод:** `GET`

**Доступ:** `admin`, `user` c `user_id` = `campaign.user_id`

**Ответ:**

```json
{
  "campaign": {
    "apps": [
      {
        "description": "My New App description",
        "id": 9,
        "image": "image3.png",
        "operating_system": "iOS",
        "status": "active",
        "tags": [
          "tag1",
          "tag2"
        ],
        "title": "My New App 4",
        "unique_tag": "mynewapp4",
        "url": "https://mynewapp4.com"
      },
      {
        "description": "My New App description",
        "id": 8,
        "image": "image3.png",
        "operating_system": "iOS",
        "status": "active",
        "tags": [
          "tag1",
          "tag2"
        ],
        "title": "My New App 3",
        "unique_tag": "mynewapp3",
        "url": "https://mynewapp3.com"
      }
    ],
    "apps_stats": [
        {
            "id": 9,
            "visits": 0,
            "weight": 50
        },
        {
            "id": 8,
            "visits": 0,
            "weight": 20
        },
        {
            "id": null,
            "visits": 0,
            "weight": 30
        }
    ],
    "archived": false,
    "custom_parameters": {
      "param1": "value1",
      "param2": "value2"
    },
    "description": "My New Campaign description",
    "geo": "US",
    "hash_code": "b85b82bcae58c39ea585e99c1362b098d1604f6f639bd697c9454aed945557b8",
    "id": 7,
    "landing_page": "landing2.php",
    "status": "inactive",
    "title": "My New Campaign",
    "user_id": 1,
    "user_name": "testuser"
  }
}
```

### Добавление новой кампании

**URL:** `/campaigns/add`

**Метод:** `POST`

**Доступ:** `admin`, `user`

**Тело запроса:**

```json
{
    "title": "My New Campaign",
    "user": 1,
    "subuser_id": 1,
    "geo": "US",
    "description": "My New Campaign description",
    "offer_url": "https://mynewcampaign.com/offer",
    "landing_page": 1,
    "custom_parameters": {"param1": "value1", "param2": "value2"},
    "status": "active",

    "apps": [
        {
            "id": 1,
            "weight": 50
        },
        {
            "id": 2,
            "weight": 20
        }
    ],

    или "tags" вместо "apps":

    "tags": [
        "tag1",
        "tag2"
    ]
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `title` | Строка | Название кампании | Да | 120 |
| `user` | Целое число | ID пользователя, создавшего кампанию | Да | |
| `subuser_id` | Целое число | ID подпользователя | Нет | |
| `geo` | Строка | География кампании | Да | 2 |
| `apps` | Список | Список словарей с ID приложений и их весом в % | Да, если не передан список тегов приложений | |
| `tags` | Список | Список тегов приложений | Да, если не передан список приложений | |
| `description` | Строка | Описание кампании | Нет | 256 |
| `offer_url` | Строка | URL оффера | Нет | 256 |
| `landing_page` | Целое число | ID лендинга | Нет |  |
| `custom_parameters` | Словарь | Словарь пользовательских параметров | Нет | |
| `status` | Строка | Статус кампании (`active` или `inactive`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "Campaign added successfully."
}
```

### Изменение статуса кампании

**URL:** `/campaigns/update_status`

**Метод:** `PATCH`

**Доступ:** `admin`, `user` c `user_id` = `campaign.user_id`

**Тело запроса:**

```json
{
    "id": 1,
    "status": "inactive"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID кампании | Да | |
| `status` | Строка | Статус кампании (`active` или `inactive`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "Campaign status updated successfully."
}
```

### Изменение статуса архивации кампании

**URL:** `/campaigns/send_to_archive`

**Метод:** `PATCH`

**Доступ:** `admin`, `user` c `user_id` = `campaign.user_id`

**Тело запроса:**

```json
{
    "id": 1,
    "archived": true
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID кампании | Да | |
| `archived` | Булево | Статус архивации кампании (`true` или `false`) | Да | |

**Ответ в случае успеха:**

```json
{
    "message": "Campaign archived successfully."
}
```
```json
{
    "message": "Campaign restored from archive successfully."
}
```

### Изменение подпользователя кампании

**URL:** `/campaigns/update_subuser`

**Метод:** `PATCH`

**Доступ:** `admin` с `campaign.user_id` = `user.id`, `user` c `campaign.user_id` = `user.id`

**Тело запроса:**

```json
{
    "id": 1,
    "subuser_id": 1
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID кампании | Да | |
| `subuser_id` | Целое число | ID подпользователя | Нет. Если не передан, то подпользователь будет удалён из кампании. | |

**Ответ в случае успеха:**

```json
{
    "message": "Campaign subuser assigned successfully."
}
```
```
{
    "message": "Campaign subuser unassigned successfully."
}
```

### Изменение информации о кампании (Устаревший метод)

**URL:** `/campaigns/update_info`

**Метод:** `PATCH`

**Доступ:** `admin`, `user` c `user_id` = `campaign.user_id`

**Тело запроса:**

```json
{
    "id": 1,
    "title": "My New Campaign",
    "subuser_id": 1,
    "geo": "US",
    "description": "My New Campaign description",
    "offer_url": "https://mynewcampaign.com/offer",
    "landing_page": 1,
    "custom_parameters": {"param1": "value1", "param2": "value2"},
    "status": "active"
}
```
| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID кампании | Да | |
| `title` | Строка | Название кампании | Нет | 120 |
| `subuser_id` | Целое число | ID подпользователя | Нет | |
| `geo` | Строка | География кампании | Нет | 2 |
| `description` | Строка | Описание кампании | Нет | 256 |
| `offer_url` | Строка | URL оффера | Нет | 256 |
| `landing_page` | Целое число | ID лендинга | Нет |  |
| `custom_parameters` | Словарь | Словарь пользовательских параметров | Нет | |
| `status` | Строка | Статус кампании (`active` или `inactive`) | Нет | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "Campaign info updated successfully."
}
```

### Удаление кампании

**URL:** `/campaigns/delete/<int:campaign_id>`

**Метод:** `DELETE`

**Доступ:** `admin`, `user` c `user_id` = `campaign.user_id`

**Ответ в случае успеха:**

```json
{
    "message": "Campaign deleted successfully."
}
```

### Получение списка всех доменов

**URL:** `/domains`

**Метод:** `GET`

**Доступ:** `admin` (список всех доменов), `user` (список доменов пользователя)

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|page|Целое число|Номер страницы|Нет (default: 1)||
|per_page|Целое число|Количество записей на странице|Нет (default: 50)||
|search_query|Строка|Поиск по `domain` домена|Нет||

**Ответ:**

```json
{
    "domains": [
        {
            "created": "Tue, 17 Oct 2023 00:00:00 GMT",
            "domain": "mydomain.store",
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 1,
            "redirected": false,
            "status": "inactive",
            "user_id": null
        },
        {
            "created": "Tue, 17 Oct 2023 00:00:00 GMT",
            "domain": "mydomaain.store",
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 1,
            "redirected": true,
            "status": "active",
            "user_id": 1
        }
    ]
}
```

### Получение списка доменов пользователя

**URL:** `/users/<int:user_id>/domains`

**Метод:** `GET`

**Доступ:** `admin`, `user` c `user_id` = `domain.user_id`

**Ответ:**

```json
{
    "domains": [
        {
            "created": "Tue, 17 Oct 2023 00:00:00 GMT",
            "domain": "mydomain.store",
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 1,
            "redirected": false,
            "status": "inactive",
            "user_id": 1
        },
        {
            "created": "Tue, 17 Oct 2023 00:00:00 GMT",
            "domain": "mydomaain.store",
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 1,
            "redirected": true,
            "status": "active",
            "user_id": 1
        }
    ]
}
```

### Получение домена по ID

**URL:** `/domains/<int:domain_id>`

**Метод:** `GET`

**Доступ:** `admin`, `user` c `user_id` = `domain.user_id`

**Ответ:**

```json
{
    "domain": {
        "created": "Tue, 17 Oct 2023 00:00:00 GMT",
        "domain": "mydomaain.store",
        "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
        "id": 1,
        "redirected": true,
        "status": "active",
        "users": []
    }
}
```

### Проверка доступности доменов

**URL:** `domains/check_domains`

**Метод:** `POST`

**Доступ:** `admin`, `user`

**Тело запроса:**

```json
{
    "domains": ["mydomain.store", "mydomain2.store"]
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `domains` | Список | Список доменов (допустимые TLD: `.online`, `.store`) | Да | 70 символов/домен |

**Ответ:**

```json
{
    "domains": [
        {
            "available": false,
            "domain": "mydomain.store"
        },
        {
            "available": true,
            "domain": "mydomain2.store"
        }
    ]
}
```

### Регистрация новых доменов

**URL:** `/domains/add`

**Метод:** `POST`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "domains": [
        "mydomain.online", 
        "mydomain2.store", 
        "mydomain3.store"
        ]
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `domains` | Список словарей | Домен (допустимые TLD: `.online`, `.store`) с необязательным списком поддоменов | Да | 50 доменов; 70 символов/домен |

**Ответ:**

```json
{
    {
    "domains": [
        {
            "domain": "mydomain.online",
            "proxied": true,
            "redirected": true,
            "registered": true,
            "success": true,
            "subdomains": [
                "subdomain",
                "subdomain2"
            ]
        },
        {
            "domain": "mydomain2.store",
            "error": "Domain is not available.",
            "success": false
        },
        {
            "domain": "mydomain3.store",
            "error": "Domain is not available.",
            "success": false
        }
    ]
}
}
```

### Изменение статуса домена

**URL:** `/domains/update_status`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "status": "inactive"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID домена | Да | |
| `status` | Строка | Статус домена (`active` или `inactive`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "Domain status updated successfully."
}
```

### Обновление хостов домена (привязка домена к серверу)

**URL:** `/domains/update_dns_hosts`

**Метод:** `POST`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "domain": "mydomain.store"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `domain` | Строка | Домен (допустимые TLD: `.online`, `.store`) | Да | 70 |

**Ответ в случае успеха:**

```json
{
    "message": "Domain hosts updated successfully."
}
```

### Привязка домена к пользователю

**URL:** `/domains/assign_to_user`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "user_id": 2
}
```

**Ответ в случае успеха:**

```json
{
    "message": "Domain assigned successfully."
}
```

### Покупка домена пользователем

**URL:** `/domains/purchase`

**Метод:** `POST`

**Доступ:** `admin`, `user`

**Тело запроса:**

```json
{
    "id": 1
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|id|Целое число|ID домена, если нужно купить определённый|Нет||

**Ответ в случае успеха:**

```json
{
    "message": "Domain purchased successfully."
}
```

### Привязка домена к подпользователю

**URL:** `/domains/update_subuser`

**Метод:** `PATCH`

**Доступ:** `admin` c `user_id` = `domain.user_id`, `user` c `user_id` = `domain.user_id`

**Тело запроса:**

```json
{
    "id": 1,
    "subuser_id": 2
}
```

**Ответ в случае успеха:**

```json
{
    "message": "Domain subuser updated successfully."
}
```

### Удаление домена

**URL:** `/domains/delete/<int:domain_id>`

**Метод:** `DELETE`

**Доступ:** `admin`

**Ответ в случае успеха:**

```json
{
    "message": "Domain deleted successfully."
}
```

### Получение списка всех поддоменов

**URL:** `/subdomains`

**Метод:** `GET`

**Доступ:** `admin` (список всех поддоменов), `user` (список поддоменов пользователя)

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|page|Целое число|Номер страницы|Нет (default: 1)||
|per_page|Целое число|Количество записей на странице|Нет (default: 50)||
|search_query|Строка|Поиск по `subdomain` поддомена|Нет||

**Ответ:**

```json
{
    "subdomains": [
        {
            "domain_id": 1,
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 2,
            "status": "inactive",
            "subdomain": "subdomain.mydomain.store",
            "user_id": null,
            "is_paid": false
        },
        {
            "domain_id": 1,
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 3,
            "status": "active",
            "subdomain": "subdomain2.mydomain.store",
            "user_id": 2,
            "is_paid": true
        }
    ]
}
```

### Получение всех поддоменов домена

**URL:** `/domains/<int:domain_id>/subdomains`

**Метод:** `GET`

**Доступ:** `admin`, `user` c `user_id` = `domain.user_id`

**Ответ:**

```json
{
    "subdomains": [
        {
            "domain_id": 1,
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 2,
            "status": "inactive",
            "subdomain": "subdomain.mydomain.store",
            "user_id": null,
            "is_paid": false
        },
        {
            "domain_id": 1,
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 3,
            "status": "active",
            "subdomain": "subdomain2.mydomain.store",
            "user_id": 2,
            "is_paid": true
        }
    ]
}
```

### Получение всех поддоменов пользователя

**URL:** `/users/<int:user_id>/subdomains`

**Метод:** `GET`

**Доступ:** `admin`, `user` c `user_id` = `user_id`

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|page|Целое число|Номер страницы|Нет (default: 1)||
|per_page|Целое число|Количество записей на странице|Нет (default: 50)||
|search_query|Строка|Поиск по `subdomain` поддомена|Нет||

**Ответ:**

```json
{
    "subdomains": [
        {
            "domain_id": 1,
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 2,
            "status": "inactive",
            "subdomain": "subdomain.mydomain.store",
            "user_id": null,
            "is_paid": false
        },
        {
            "domain_id": 1,
            "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
            "id": 3,
            "status": "active",
            "subdomain": "subdomain2.mydomain.store",
            "user_id": 2,
            "is_paid": true
        }
    ]
}
```

### Получение поддомена по ID

**URL:** `/subdomains/<int:subdomain_id>`

**Метод:** `GET`

**Доступ:** `admin`, `user` c `user_id` = `subdomain.user_id`

**Ответ:**

```json
{
    "subdomain": {
        "domain_id": 1,
        "expires": "Thu, 17 Oct 2024 00:00:00 GMT",
        "id": 3,
        "status": "active",
        "subdomain": "subdomain.mydomaain.store",
        "user_id": 2,
        "is_paid": true
    }
}
```

### Проверка доступности поддомена

**Устаревший метод**

**URL:** `subdomains/check_subdomain`

**Метод:** `POST`

**Тело запроса:**

```json
{
    "domain": "mydomain.store",
    "subdomain": "subdomain"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `domain` | Строка | Домен (допустимые TLD: `.online`, `.store`) | Да | 70 |
| `subdomain` | Строка | Поддомен | Да | 70 |

**Ответ:**

```json
{
    "message": "Subdomain is available."
}
```

### Добавление поддомена

**Устаревший метод**

**URL:** `/subdomains/add`

**Метод:** `POST`

**Тело запроса:**

```json
{
    "domain": "mydomain.store",
    "subdomain": "subdomain",
    "user_id": 3
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `domain` | Строка | Домен (допустимые TLD: `.online`, `.store`) | Да | 70 |
| `subdomain` | Строка | Поддомен | Да | 70 |
| `user_id` | Целое число | ID пользователя, которому принадлежит поддомен | Нет | |

**Ответ в случае успеха:**

```json
{
    "message": "Subdomain added successfully."
}
```

### Изменение статуса поддомена

**URL:** `/subdomains/update_status`

**Метод:** `PATCH`

**Доступ:** `admin`, `user` c `user_id` = `subdomain.user_id`

**Тело запроса:**

```json
{
    "id": 1,
    "status": "inactive"
}
```

**Ответ в случае успеха:**

```json
{
    "message": "Subdomain status updated successfully."
}
```

### Получение списка всех лендингов

**URL:** `/landings`

**Метод:** `GET`

**Доступ:** `admin`, `user`

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|page|Целое число|Номер страницы|Нет (default: 1)||
|per_page|Целое число|Количество записей на странице|Нет (default: 50)||
|search_query|Строка|Поиск по `title`/`tags`/`geo` лендинга|Нет||

**Ответ:**

```json
{
    "landings": [
        {
            "id": 1,
            "title": "My New Landing",
            "description": "My New Landing description",
            "geo": "US",
            "status": "active",
            "tags": [
                "php",
                "test"
            ]
        },
        {
            "id": 2,
            "title": "My New Landing 2",
            "description": "My New Landing 2 description",
            "geo": "PL",
            "status": "inactive",
            "tags": [
                "html"
            ]
        }
    ]
}
```

### Получение лендинга по ID

**URL:** `/landings/<int:landing_id>`

**Метод:** `GET`

**Доступ:** `admin`, `user`

**Ответ:**

```json
{
    "landing": {
        "id": 1,
        "title": "My New Landing",
        "description": "My New Landing description",
        "geo": "US",
        "status": "active",
        "tags": [
            "php",
            "test"
        ]
    }
}
```

### Добавление нового лендинга

**URL:** `/landings/add`

**Метод:** `POST`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "title": "My New Landing",
    "description": "My New Landing description",
    "geo": "US",
    "working_directory": "static/landings/1698058817792564",
    "zip_file": "1698058817792564.zip",
    "status": "active",
    "tags": [
        "php",
        "test"
    ]
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `title` | Строка | Название лендинга | Да | 120 |
| `description` | Строка | Описание лендинга | Нет | 1500 |
| `geo` | Строка | География лендинга | Да | 2 |
| `working_directory` | Строка | Рабочая директория лендинга | Да | 255 |
| `zip_file` | Строка | Файл архива лендинга (`zip` или `7z`) | Да | 255 |
| `status` | Строка | Статус лендинга (`active` или `inactive`) | Да | 20 |
| `tags` | Список строк | Список тегов, связанных с лендингом | Нет | 25 символов/tag |

**Ответ в случае успеха:**

```json
{
    "message": "Landing added successfully."
}
```

### Изменение статуса лендинга

**URL:** `/landings/update_status`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "status": "inactive"
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID лендинга | Да | |
| `status` | Строка | Статус лендинга (`active` или `inactive`) | Да | 20 |

**Ответ в случае успеха:**

```json
{
    "message": "Landing status updated successfully."
}
```

### Обновление лендинга

**URL:** `/landings/update`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "title": "My New Landing 3",
    "description": "My New Landing 3 description",
    "working_directory": "static/landings/1698058817792321",
    "zip_file": "1698058817792321.zip",
    "status": "inactive",
    "tags": [
        "html"
    ]
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `id` | Целое число | ID лендинга | Да | |
| `title` | Строка | Название лендинга | Нет | 120 |
| `description` | Строка | Описание лендинга | Нет | 1500 |
| `working_directory` | Строка | Рабочая директория лендинга | Нет | 255 |
| `zip_file` | Строка | Файл архива лендинга (`zip` или `7z`) | Нет | 255 |
| `status` | Строка | Статус лендинга (`active` или `inactive`) | Нет | 20 |
| `tags` | Список строк | Список тегов, связанных с лендингом | Нет | 25 символов/tag |

**Ответ в случае успеха:**

```json
{
    "message": "Landing updated successfully."
}
```

### Создать ссылку для кампании

**URL:** `/generate_campaign_link`

**Метод:** `POST`

**Доступ:** `admin`, `user`

**Тело запроса:**

```json
{
    "domain_id": 1,
    "campaign_id": 1,
    "additional_parameters": {
        "param1": "value1", 
        "param2": "value2"
        }
}
```

```json
{
    "subdomain_id": 10,
    "campaign_id": 6,
    "additional_parameters": {
        "param1": "value1", 
        "param2": "value2"
        }
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
| `domain_id` | Целое число | ID домена | *Да, если выбран домен* | |
| `subdomain_id` | Целое число | ID поддомена | *Да, если выбран поддомен* | |
| `campaign_id` | Целое число | ID кампании | Да | |
| `additional_parameters` | Словарь | Словарь дополнительных параметров | Нет | |

**Ответ в случае успеха:**

```json
{
    "message": "Campaign link generated successfully.",
    "ready_link": "https://subdomain.mydomain.store/?uchsik=eb1d81ece0abb0e2850ba90949581c1a01dbc2de9ce32f46175600cf110f09e0&param1=value1&param2=value2"
}
```

### Получить ГЕО прайсы

**URL:** `/geo_prices`

**Метод:** `GET`

**Доступ:** `admin`, `user`

**Ответ в случае успеха:**

```json
{
    "geo_prices": [
        {
            "id": 1,
            "geo": "ua",
            "install_price": 0.05,
            "conversion_price": 0.10
        },
        {
            "id": 3,
            "geo": "us",
            "install_price": 0.05,
            "conversion_price": 0.10
        }
    ]
}
```

### Добавить ГЕО прайс

**URL:** `/geo_prices/add`

**Метод:** `POST`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "geo": "ua",
    "install_price": 0.05,
    "conversion_price": 0.10
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
|geo|Строка|Гео|Да|2|
|install_price|Число|Цена за установку|Да||
|conversion_price|Число|Цена за конверсию|Да||

**Ответ в случае успеха:**

```json
{
    "message": "Geo price added successfully."
}
```

### Обновить ГЕО прайс

**URL:** `/geo_prices/update`

**Метод:** `PATCH`

**Доступ:** `admin`

**Тело запроса:**

```json
{
    "id": 1,
    "install_price": 0.05,
    "conversion_price": 0.10
}
```

| Параметр | Тип | Описание | Обязательный | Максимальная длина |
| -------- | --- | -------- | ------------ | ------------------ |
id|Целое число|ID прайса|Да||
|install_price|Число|Цена за установку|Да||
|conversion_price|Число|Цена за конверсию|Да||

**Ответ в случае успеха:**

```json
{
    "message": "Geo price updated successfully."
}
```


## Ошибки

Ответ может содержать следующие ошибки:

- `404 Not Found`: запрашиваемый ресурс не найден.
- `400 Bad Request`: запрос содержит некорректные данные или отсутствуют обязательные параметры.
- `401 Unauthorized`: запрос не содержит авторизационных данных или они некорректны.
- `403 Forbidden`: запрос отклонен из-за отсутствия прав доступа.
- `500 Internal Server Error`: внутренняя ошибка сервера.