def test_list_tasks_pagination(client, task, tasks_url):
    response = client.post(tasks_url, json={"title": "Learn database"})
    assert response.status_code == 201
    second = response.json()

    response = client.get(tasks_url)
    assert response.status_code == 200
    assert response.json() == {"items": [task, second], "total": 2, "offset": 0, "limit": 20}

    response = client.get(tasks_url, params={"offset": 1, "limit": 1})
    assert response.status_code == 200
    assert response.json() == {"items": [second], "total": 2, "offset": 1, "limit": 1}


def test_pagination_rejects_limit_above_maximum(client, tasks_url):
    assert client.get(tasks_url, params={"limit": 101}).status_code == 422
