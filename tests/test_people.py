def test_create_and_list_people(client):
    assert client.get("/people").get_json()["people"] == []
    client.post("/people", json={"name": "Ada", "email": "ada@example.com", "phone": "555-0100"})
    people = client.get("/people").get_json()["people"]
    assert len(people) == 1
    assert people[0]["name"] == "Ada"


def test_create_person_missing_name_400(client):
    assert client.post("/people", json={}).status_code == 400
