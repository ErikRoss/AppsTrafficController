## Хост

**URL:** `http://38.54.122.209:5000/`

## Эндпоинты

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

**URL:** `/add_app`

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

**Ответ в случае успеха:**

```json
{
    "message": "App added successfully."
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
            "landing_page": "https://mycampaign.com",
            "custom_parameters": {"param1": "value1", "param2": "value2"}
        },
        {
            "id": 2,
            "title": "Another Campaign",
            "user": "Jane",
            "geo": "UK",
            "apps": ["myapp"],
            "description": "Another Campaign description",
            "landing_page": "https://anothercampaign.com",
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
        "landing_page": "https://mycampaign.com",
        "custom_parameters": {"param1": "value1", "param2": "value2"}
    }
}
```

### Добавление новой кампании

**URL:** `/add_campaign`

**Метод:** `POST`

**Тело запроса:**

```json
{
    "title": "My New Campaign",
    "user": "John",
    "geo": "US",
    "apps": ["myapp", "anotherapp"],
    "description": "My New Campaign description",
    "landing_page": "https://mynewcampaign.com",
    "custom_parameters": {"param1": "value1", "param2": "value2"}
}
```

**Ответ в случае успеха:**

```json
{
    "message": "Campaign added successfully."
}
```