"""Demo del orquestador: muestra la delegación supervisor -> especialistas turno a turno.

Uso:
    python main.py                      # consulta de ejemplo (museos + parrillas en Recoleta)
    python main.py "tu consulta"        # consulta propia
    python main.py --grafo              # solo exporta el diagrama del grafo (grafo.mmd / grafo.png)
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage

from config import RECURSION_LIMIT
from graph import construir_grafo

BASE = Path(__file__).resolve().parent
CONSULTA_DEMO = "Armame un plan en Recoleta: museos y parrillas, a menos de 2 km. Quiero saber si conviene salir por el clima."


def exportar_diagrama(grafo) -> None:
    mermaid = grafo.get_graph().draw_mermaid()
    (BASE / "grafo.mmd").write_text(mermaid, encoding="utf-8")
    print(mermaid)
    try:
        (BASE / "grafo.png").write_bytes(grafo.get_graph().draw_mermaid_png())
        print("🖼️  Diagrama guardado en grafo.png")
    except Exception as exc:  # draw_mermaid_png requiere acceso a mermaid.ink
        print(f"(No se pudo generar grafo.png: {type(exc).__name__}. Se conserva grafo.mmd)")


def _mostrar(nodo: str, upd: dict) -> None:
    if nodo == "intake":
        print(f"🧭 INTAKE (reglas): categorías={upd['categorias']} ubicación='{upd['ubicacion']}' radio={upd['radio_m']} m")
    elif nodo == "supervisor":
        d = upd["decisiones"][0]
        print(f"\n🧠 SUPERVISOR — decisión {d['paso']}: {d['razonamiento']}")
        print(f"   → destino: {d['destino']}" + (f"   (LLM propuso '{d['propuesta_llm']}'; override: {d['override']})"
                                                    if d["override"] else ""))
        if d["instruccion"]:
            print(f"   📝 instrucción: {d['instruccion']}")
    elif nodo in ("investigador", "analista"):
        c = upd["contribuciones"][0]
        icono = "🔎" if nodo == "investigador" else "📊"
        print(f"{icono} {nodo.upper()} usó {c['herramientas']}\n   {c['resumen']}")
    elif nodo == "sintetizador":
        print("\n✍️  SINTETIZADOR: redactó el itinerario (solo con ids de la evidencia)")
    elif nodo == "validador":
        print(f"✅ VALIDADOR: {upd['validacion']}")


async def demo(consulta: str) -> None:
    grafo = construir_grafo()
    print(f"🧑 Consulta: {consulta}\n" + "=" * 80)

    traza: list[dict] = []
    estado_final: dict = {}
    async for evento in grafo.astream({"messages": [HumanMessage(content=consulta)]},
                                      config={"recursion_limit": RECURSION_LIMIT}, stream_mode="updates"):
        for nodo, upd in evento.items():
            if not upd:
                continue
            _mostrar(nodo, upd)
            estado_final.update({k: v for k, v in upd.items() if k not in ("messages", "contribuciones", "decisiones")})
            traza.append({"nodo": nodo, **{k: v for k, v in upd.items() if k in ("decisiones", "contribuciones",
                                                                                   "validacion", "categorias")}})

    print("\n" + "=" * 80 + "\n🤖 RESPUESTA FINAL\n" + "=" * 80)
    print(estado_final.get("respuesta", "(sin respuesta)"))

    salida = {"fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "consulta": consulta,
              "flujo": [t["nodo"] for t in traza], "traza": traza, "validacion": estado_final.get("validacion"),
              "respuesta_final": estado_final.get("respuesta")}
    (BASE / "traza_ejecucion.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n💾 Traza guardada en traza_ejecucion.json | flujo:", " → ".join(salida["flujo"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Orquestador multi-agente BA Explore AI")
    ap.add_argument("consulta", nargs="?", default=CONSULTA_DEMO)
    ap.add_argument("--grafo", action="store_true", help="solo exportar el diagrama")
    args = ap.parse_args()
    if args.grafo:
        exportar_diagrama(construir_grafo())
    else:
        asyncio.run(demo(args.consulta))
