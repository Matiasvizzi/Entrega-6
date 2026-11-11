"""Pruebas offline (sin Internet ni LLM): router, reglas de seguridad del supervisor y cómputo.

Uso:  python tests/test_reglas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.supervisor import aplicar_reglas_seguridad
from agents.synthesizer import nodo_validador
from config import MAX_PASOS_SUPERVISOR
from routing import CATEGORIAS, detectar_intenciones, extraer_radio, extraer_ubicacion
from tools.analysis import evaluar_clima, recorrido_vecino_mas_cercano
from tools.geodata import haversine_km

CENTRO = {"lat": -34.6037, "lon": -58.3816, "nombre": "Obelisco"}


def lugar(i: str, lat: float, lon: float, cat: str = "turismo") -> dict:
    return {"id": i, "nombre": f"Lugar {i}", "categoria": cat, "tipo": "museum", "direccion": "",
            "lat": lat, "lon": lon, "distancia_km": 0.5, "descripcion": "", "url_fuente": f"https://osm/{i}"}


def test_router() -> None:
    assert detectar_intenciones("museos cerca del obelisco") == ["turismo"]
    assert detectar_intenciones("parrillas en San Telmo") == ["gastronomia"]
    assert set(detectar_intenciones("museos y parrillas en Recoleta")) == {"turismo", "gastronomia"}
    assert set(detectar_intenciones("un itinerario completo")) == set(CATEGORIAS)
    assert extraer_ubicacion("bares en Palermo") == "palermo"
    assert extraer_radio("museos a menos de 2 km del Obelisco") == 2000
    assert extraer_radio("cafés a 800 metros") == 800


def test_supervisor_no_analiza_sin_datos() -> None:
    estado = {"lugares": {}, "analisis": {}, "contribuciones": []}
    destino, motivo = aplicar_reglas_seguridad("analista", estado, pasos=1)
    assert destino == "investigador" and motivo


def test_supervisor_no_finaliza_sin_trabajo_minimo() -> None:
    estado = {"lugares": {}, "analisis": {}, "contribuciones": []}
    assert aplicar_reglas_seguridad("FINISH", estado, pasos=1)[0] == "investigador"
    con_datos = {"lugares": {"turismo": [lugar("a", -34.6, -58.38)]}, "analisis": {},
                 "contribuciones": [{"agente": "investigador"}]}
    assert aplicar_reglas_seguridad("FINISH", con_datos, pasos=2)[0] == "analista"


def test_supervisor_corta_bucles() -> None:
    # techo de pasos
    estado = {"lugares": {}, "analisis": {}, "contribuciones": []}
    assert aplicar_reglas_seguridad("investigador", estado, pasos=MAX_PASOS_SUPERVISOR)[0] == "FINISH"
    # especialista agotado: no se lo vuelve a llamar
    agotado = {"lugares": {"turismo": [lugar("a", -34.6, -58.38)]}, "analisis": {"ranking": {"turismo": [1]}},
              "contribuciones": [{"agente": "investigador"}, {"agente": "investigador"}, {"agente": "analista"}]}
    destino, motivo = aplicar_reglas_seguridad("investigador", agotado, pasos=3)
    assert destino == "FINISH" and "máximo" in motivo


def test_supervisor_respeta_decision_valida() -> None:
    estado = {"lugares": {"turismo": [lugar("a", -34.6, -58.38)]}, "analisis": {},
              "contribuciones": [{"agente": "investigador"}]}
    assert aplicar_reglas_seguridad("analista", estado, pasos=2) == ("analista", "")


def test_computo() -> None:
    assert haversine_km(-34.6037, -58.3816, -34.6037, -58.3816) == 0
    r = recorrido_vecino_mas_cercano(CENTRO, [lugar("lejos", -34.65, -58.40), lugar("cerca", -34.605, -58.382)])
    assert r["orden_ids"] == ["cerca", "lejos"] and r["total_km"] > 0
    pron = {"precipitation_probability_max": [10, 20], "temperature_2m_max": [24, 25], "temperature_2m_min": [15, 16]}
    assert "aire libre" in evaluar_clima(pron)["veredicto"]
    assert "techados" in evaluar_clima({**pron, "precipitation_probability_max": [80, 20]})["veredicto"]


def test_validador_descarta_ids_inventados() -> None:
    ranking = {"turismo": [lugar("osm:node:1", -34.6, -58.38)]}
    estado = {"categorias": ["turismo"], "ubicacion": "obelisco", "lugares": ranking, "centro": CENTRO,
              "analisis": {"ranking": ranking},
              "respuesta": '{"introduccion": "Hola", "itinerario": [{"id": "osm:node:1", "comentario": "ok"},'
                           ' {"id": "osm:node:FALSO", "comentario": "inventado"}], "consejo_clima": ""}'}
    r = nodo_validador(estado)
    assert r["validacion"]["ids_invalidos_descartados"] == ["osm:node:FALSO"]
    assert "Lugar osm:node:1" in r["respuesta"] and "FALSO" not in r["respuesta"]


if __name__ == "__main__":
    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for p in pruebas:
        p()
        print("✅", p.__name__)
    print(f"\n{len(pruebas)} pruebas aprobadas.")
