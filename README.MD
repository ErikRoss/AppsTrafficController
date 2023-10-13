## Хост

**URL:** `http://38.54.122.209:5000/`

## Эндпоинты

### Получение списка всех пользователей

**URL:** `/users`

**Метод:** `GET`

**Ответ:**

```json
{
    "users": [
        {
            "domains": [],
            "email": "test@test.com",
            "id": 1,
            "password": "testuser",
            "username": "testuser"
        },
        {
            "domains": [],
            "email": "test2@test.com",
            "id": 2,
            "password": "testuser2",
            "username": "testuser2"
        }
    ]
}
```

### Получение списка всех приложений

**URL:** `/apps`

**Метод:** `GET`

**Ответ:**

```json
{
    "apps": [
        {
            "id": 1,
            "title": "My App",
            "url": "https://myapp.com",
            "image": "image1.png",
            "operating_system": "iOS",
            "tags": ["tag1", "tag2"],
            "unique_tag": "myapp",
            "description": "My App description",
            "status": "active"
        },
        {
            "id": 2,
            "title": "Another App",
            "url": "https://anotherapp.com",
            "image": "image2.png",
            "operating_system": "Android",
            "tags": ["tag3", "tag4"],
            "unique_tag": "anotherapp",
            "description": "Another App description",
            "status": "inactive"
        }
    ]
}
```

### Получение приложения по ID

**URL:** `/apps/<int:app_id>`

**Метод:** `GET`

**Ответ:**

```json
{
    "app": {
        "id": 1,
        "title": "My App",
        "url": "https://myapp.com",
        "image": "image1.png",
        "operating_system": "iOS",
        "tags": ["tag1", "tag2"],
        "unique_tag": "myapp",
        "description": "My App description",
        "status": "active"
    }
}
```

### Добавление нового приложения

**URL:** `/apps/add`

**Метод:** `POST`

**Тело запроса:**

```json
{
    "title": "My New App",
    "url": "https://mynewapp.com",
    "image": "image3.png",
    "operating_system": "iOS",
    "tags": ["tag1", "tag2"],
    "unique_tag": "mynewapp",
    "description": "My New App description",
    "status": "active"
}
```

| Параметр | Тип | Описание | Обязательный |
| -------- | --- | -------- | ------------ |
| `title` | Строка | Название приложения | Да |
| `url` | Строка | URL приложения | Да |
| `image` | Строка | Имя файла изображения | Нет |
| `operating_system` | Строка | Операционная система, для которой предназначено приложение | Да |
| `tags` | Список строк | Список тегов, связанных с приложением | Нет |
| `unique_tag` | Строка | Уникальный тег, связанный с приложением | Да |
| `description` | Строка | Описание приложения | Нет |
| `status` | Строка | Статус приложения (`active` или `inactive`) | Да |

**Ответ в случае успеха:**

```json
{
    "message": "App added successfully."
}
```

### Изменение статуса приложения

**URL:** `/apps/update_status`

**Метод:** `PATCH`

**Тело запроса:**

```json
{
    "app_id": 1,
    "status": "inactive"
}
```

| Параметр | Тип | Описание | Обязательный |
| -------- | --- | -------- | ------------ |
| `app_id` | Целое число | ID приложения | Да |
| `status` | Строка | Статус приложения (`active` или `inactive`) | Да |

**Ответ в случае успеха:**

```json
{
    "message": "App status updated successfully."
}
```

### Удаление приложения

**URL:** `/apps/delete/<int:app_id>`

**Метод:** `DELETE`

**Ответ в случае успеха:**

```json
{
    "message": "App deleted successfully."
}
```

### Получение списка всех кампаний

**URL:** `/campaigns`

**Метод:** `GET`

**Ответ:**

```json
{
    "campaigns": [
        {
            "id": 1,
            "title": "My Campaign",
            "user": "John",
            "geo": "US",
            "apps": ["myapp", "anotherapp"],
            "description": "My Campaign description",
            "landing_page": "landing.html",
            "custom_parameters": {"param1": "value1", "param2": "value2"}
        },
        {
            "id": 2,
            "title": "Another Campaign",
            "user": "Jane",
            "geo": "UK",
            "apps": ["myapp"],
            "description": "Another Campaign description",
            "landing_page": "landing.php",
            "custom_parameters": {"param3": "value3", "param4": "value4"}
        }
    ]
}
```

### Получение кампании по ID

**URL:** `/campaigns/<int:campaign_id>`

**Метод:** `GET`

**Ответ:**

```json
{
    "campaign": {
        "id": 1,
        "title": "My Campaign",
        "user": "John",
        "geo": "US",
        "apps": ["myapp", "anotherapp"],
        "description": "My Campaign description",
        "landing_page": "landing.html",
        "custom_parameters": {"param1": "value1", "param2": "value2"}
    }
}
```

### Добавление новой кампании

**URL:** `/campaigns/add`

**Метод:** `POST`

**Тело запроса:**

```json
{
    "title": "My New Campaign",
    "user": 1,
    "geo": "US",
    "apps": ["myapp", "anotherapp"],
    "description": "My New Campaign description",
    "landing_page": "landing2.php",
    "custom_parameters": {"param1": "value1", "param2": "value2"}
}
```

| Параметр | Тип | Описание | Обязательный |
| -------- | --- | -------- | ------------ |
| `title` | Строка | Название кампании | Да |
| `user` | Целое число | ID пользователя, создавшего кампанию | Да |
| `geo` | Строка | География кампании | Да |
| `apps` | Список целых чисел | Список ID приложений, связанных с кампанией | Да |
| `description` | Строка | Описание кампании | Нет |
| `landing_page` | Строка | Файл лендинга | Нет |
| `custom_parameters` | Словарь | Словарь пользовательских параметров | Нет |

**Ответ в случае успеха:**

```json
{
    "message": "Campaign added successfully."
}
```

### Изменение статуса кампании

**URL:** `/campaigns/update_status`

**Метод:** `PATCH`

**Тело запроса:**

```json
{
    "campaign_id": 1,
    "status": "inactive"
}
```

| Параметр | Тип | Описание | Обязательный |
| -------- | --- | -------- | ------------ |
| `campaign_id` | Целое число | ID кампании | Да |
| `status` | Строка | Статус кампании (`active` или `inactive`) | Да |

**Ответ в случае успеха:**

```json
{
    "message": "Campaign status updated successfully."
}
```

### Удаление кампании

**URL:** `/campaigns/delete/<int:campaign_id>`

**Метод:** `DELETE`

**Ответ в случае успеха:**

```json
{
    "message": "Campaign deleted successfully."
}
```

### Получение списка всех доменов

**URL:** `/domains`

**Метод:** `GET`

**Ответ:**

```json
{
    "domains": [
        {
            "id": 1,
            "domain": "mydomain.com",
            "status": "active",
            "creating_date": "2023-01-01 00:00:00",
            "users": [1]
        },
        {
            "id": 2,
            "domain": "anotherdomain.com",
            "status": "inactive",
            "creating_date": "2023-01-02 00:00:00",
            "users": [1, 2]
        }
    ]
}
```

## Ошибки

Ответ может содержать следующие ошибки:

- `404 Not Found`: запрашиваемый ресурс не найден.
- `400 Bad Request`: запрос содержит некорректные данные или отсутствуют обязательные параметры.
- `401 Unauthorized`: запрос не содержит авторизационных данных или они некорректны.
- `403 Forbidden`: запрос отклонен из-за отсутствия прав доступа.
- `500 Internal Server Error`: внутренняя ошибка сервера.