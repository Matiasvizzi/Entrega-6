"""Grafo principal: intake -> supervisor <-> {investigador, analista} -> sintetizador -> validador.

    START -> intake -> supervisor --+--> investigador --+
                          ^         |                   |
                          +---------+--> analista ------+   (cada especialista vuelve al supervisor)
                          |
                          +--(FINISH)--> sintetizador -> validador -> END
"""
import re
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from agents.analyst_agent import nodo_analista
from agents.research_agent import nodo_investigador
from agents.supervisor import nodo_supervisor
from agents.synthesizer import nodo_sintetizador, nodo_validador
from config import RECURSION_LIMIT
from routing import CATEGORIAS, detectar_intenciones, extraer_radio, extraer_ubicacion
from state import OrquestadorState


def nodo_intake(state: OrquestadorState) -> dict[str, Any]:
    """Router por reglas (sin LLM): fija categorías, ubicación y radio de la consulta."""
    pregunta = state["messages"][-1].content
    categorias = detectar_intenciones(pregunta) or ["turismo"]  # respaldo explícito
    return {"categorias": categorias, "ubicacion": extraer_ubicacion(pregunta), "radio_m": extraer_radio(pregunta),
            "pasos": 0, "task_completed": False, "lugares": {}, "contexto_wiki": [], "clima": {},
            "analisis": {}, "centro": {}}


def construir_grafo():
    g = StateGraph(OrquestadorState)
    g.add_node("intake", nodo_intake)
    g.add_node("supervisor", nodo_supervisor)  # devuelve Command(goto=...): sus aristas salen del Literal
    g.add_node("investigador", nodo_investigador)
    g.add_node("analista", nodo_analista)
    g.add_node("sintetizador", nodo_sintetizador)
    g.add_node("validador", nodo_validador)

    g.add_edge(START, "intake")
    g.add_edge("intake", "supervisor")
    g.add_edge("investigador", "supervisor")   # el especialista siempre devuelve el control al supervisor
    g.add_edge("analista", "supervisor")
    g.add_edge("sintetizador", "validador")
    g.add_edge("validador", END)
    return g.compile()


async def consultar(pregunta: str, grafo=None) -> dict[str, Any]:
    grafo = grafo or construir_grafo()
    return await grafo.ainvoke({"messages": [HumanMessage(content=pregunta)]},
                               config={"recursion_limit": RECURSION_LIMIT})
