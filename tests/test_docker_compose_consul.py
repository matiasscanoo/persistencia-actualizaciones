from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"


def test_compose_conecta_actualizaciones_a_consul_sin_exponer_el_token():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "CONSUL_HTTP_ADDR: http://consul:8500" in text
    assert "CONSUL_HTTP_TOKEN_FILE: /run/secrets/consul_microservices_token" in text
    assert "name: redutn" in text
    assert "consul_microservices_token:" in text


def test_compose_usa_la_mongodb_y_el_redis_compartidos_de_la_infraestructura():
    # Una sola MongoDB y un solo Redis para las dos persistencias (../dockers):
    # lo que escribe actualizaciones lo tiene que poder leer consultas.
    text = COMPOSE.read_text(encoding="utf-8")
    assert "MONGO_URI: mongodb://mongodb:27017" in text
    assert "REDIS_URL: redis://redis:6379/0" in text
    assert "image: mongo" not in text
    assert "image: redis" not in text
