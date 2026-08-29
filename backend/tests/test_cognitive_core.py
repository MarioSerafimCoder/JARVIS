from app.core.cognitive_graph import DeterministicRelationshipProvider, cognitive_graph_service, stable_position
from app.core.cognitive_state import CognitiveState, cognitive_state_service
from app.core.database import database, utc_now


def memory(item_id: str, content: str, category: str = "project") -> dict:
    now = utc_now()
    return {"id":item_id,"content":content,"category":category,"importance":3,"source_type":"manual","source_reference":None,"created_at":now,"updated_at":now,"last_used_at":None}


def test_layout_is_stable_between_sessions():
    assert stable_position("abc", "projects") == stable_position("abc", "projects")
    assert stable_position("abc", "projects") != stable_position("abc", "people")


def test_relationships_are_justified_and_limited():
    items = [memory(f"m{index}", f"Projeto Jarvis arquitetura local módulo {index}") for index in range(8)]
    edges = DeterministicRelationshipProvider().relationships(items, max_connections=3)
    degree: dict[str,int] = {}
    assert edges
    for edge in edges:
        assert edge["evidence"]["shared_terms"]
        degree[edge["source"]] = degree.get(edge["source"],0)+1
        degree[edge["target"]] = degree.get(edge["target"],0)+1
    assert max(degree.values()) <= 3


def test_unrelated_memories_do_not_create_decorative_edges():
    items = [memory("a","girassol amarelo", "fact"), memory("b","compilador rust", "project")]
    assert DeterministicRelationshipProvider().relationships(items) == []


def test_graph_contains_only_real_entities(isolated_data):
    now=utc_now()
    with database() as connection:
        connection.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?)",("m1","Jarvis usa memória local","fact",4,"manual",None,now,now,None))
        connection.execute("INSERT INTO memories_fts VALUES (?,?,?)",("m1","Jarvis usa memória local","fact"))
        connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",("t1","Validar núcleo","","inbox","high",now,now,None,None,None,"manual",None))
    graph=cognitive_graph_service.build([])
    assert {node["id"] for node in graph["nodes"]} == {"core:jarvis","memory:m1","task:t1"}
    assert graph["stats"]["memories"] == 1 and graph["stats"]["tasks"] == 1


def test_state_service_emits_real_state_event():
    cursor=cognitive_state_service.snapshot()["last_event_id"]
    cognitive_state_service.set_state(CognitiveState.SEARCHING_MEMORY, reason="test")
    events=cognitive_state_service.events_since(cursor)
    assert events[-1]["type"] == "STATE_CHANGED"
    assert events[-1]["payload"]["state"] == "SEARCHING_MEMORY"


def test_cooccurrence_grows_only_from_real_context(isolated_data):
    now=utc_now()
    with database() as connection:
        for item_id,content in (("m1","Projeto Jarvis local"),("m2","Arquitetura Jarvis local")):
            connection.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?)",(item_id,content,"project",3,"manual",None,now,now,None))
    cognitive_graph_service.record_cooccurrence(["m1","m2"])
    cognitive_graph_service.record_cooccurrence(["m1","m2"])
    with database() as connection:
        row=connection.execute("SELECT * FROM memory_relationships WHERE relationship_type='cooccurrence'").fetchone()
    assert row and row["weight"] == 0.36
    assert '"occurrences": 2' in row["evidence_json"]
