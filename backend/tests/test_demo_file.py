from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_demo_file_returns_200():
    r = client.get("/api/proteins/demo/file")
    assert r.status_code == 200


def test_demo_file_content_type():
    r = client.get("/api/proteins/demo/file")
    ct = r.headers["content-type"]
    assert "pdb" in ct or "octet" in ct


def test_demo_file_has_content():
    r = client.get("/api/proteins/demo/file")
    assert len(r.content) > 1000  # 1CRN.pdb is ~49 KB
