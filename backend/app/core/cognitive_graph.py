from __future__ import annotations

import hashlib
import json
import math
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.core.cognitive_state import CognitiveEventType, cognitive_state_service
from app.core.database import database, utc_now
from app.core.retrieval import normalize_query
from app.services.repository import repository
from app.services.embeddings import cosine_similarity


CATEGORY_CLUSTERS = {
    "project": "projects", "person": "people", "preference": "preferences", "routine": "routine",
    "fact": "facts", "instruction": "instructions", "decision": "decisions", "other": "other",
}

CLUSTER_CENTERS = {
    "projects": (-8.0, 3.0, -1.0), "people": (-5.0, -4.5, 2.0), "preferences": (1.5, -6.0, -1.5),
    "routine": (7.0, -4.0, 1.0), "facts": (8.0, 2.5, -2.0), "instructions": (4.0, 6.0, 1.5),
    "decisions": (-3.0, 7.0, -1.0), "other": (0.0, 2.0, 5.0), "knowledge": (0.0, 0.0, -11.0),
    "operations": (0.0, -11.0, 0.0), "tools": (0.0, 0.0, 14.0), "core": (0.0, 0.0, 0.0),
}


def stable_position(identifier: str, cluster: str, spread: float = 3.2) -> dict[str, float]:
    digest = hashlib.sha256(f"{cluster}:{identifier}".encode()).digest()
    angle = int.from_bytes(digest[:4], "big") / 2**32 * math.tau
    elevation = (int.from_bytes(digest[4:8], "big") / 2**32 - 0.5) * spread
    radius = spread * (0.45 + int.from_bytes(digest[8:12], "big") / 2**32 * 0.55)
    cx, cy, cz = CLUSTER_CENTERS[cluster]
    return {"x": round(cx + math.cos(angle) * radius, 4), "y": round(cy + elevation, 4), "z": round(cz + math.sin(angle) * radius, 4)}


class GraphRelationshipProvider(ABC):
    name = "base"

    @abstractmethod
    def relationships(self, memories: list[dict[str, Any]], max_connections: int = 4) -> list[dict[str, Any]]: ...


class DeterministicRelationshipProvider(GraphRelationshipProvider):
    name = "deterministic"

    def relationships(self, memories: list[dict[str, Any]], max_connections: int = 4) -> list[dict[str, Any]]:
        by_id = {item["id"]: item for item in memories}
        tokens = {item["id"]: set(normalize_query(item["content"], 24)) for item in memories}
        inverted: dict[str, list[str]] = defaultdict(list)
        for item_id, words in tokens.items():
            for word in words:
                inverted[word].append(item_id)
        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        for word, item_ids in inverted.items():
            if len(item_ids) > 80:
                continue
            ordered = sorted(item_ids)
            for index, source_id in enumerate(ordered):
                for target_id in ordered[index + 1:]:
                    key = (source_id, target_id)
                    candidates.setdefault(key, {"shared": set()})["shared"].add(word)
        for source in memories:
            reference = source.get("source_reference")
            if not reference:
                continue
            for target in memories:
                if source["id"] < target["id"] and target.get("source_reference") == reference:
                    candidates.setdefault((source["id"], target["id"]), {"shared": set()})["same_source"] = True
        scored: list[dict[str, Any]] = []
        for (source_id, target_id), evidence in candidates.items():
            source, target = by_id[source_id], by_id[target_id]
            shared = evidence.get("shared", set())
            union = tokens[source_id] | tokens[target_id]
            overlap = len(shared) / max(1, len(union))
            same_category = source["category"] == target["category"]
            same_source = bool(evidence.get("same_source"))
            weight = overlap * 0.7 + (0.18 if same_category else 0) + (0.3 if same_source else 0)
            if weight < 0.28:
                continue
            relationship_type = "same_source" if same_source else "semantic_overlap"
            scored.append({
                "source": f"memory:{source_id}", "target": f"memory:{target_id}", "type": relationship_type,
                "weight": round(min(weight, 1.0), 4),
                "evidence": {"shared_terms": sorted(shared), "same_category": same_category, "same_source": same_source},
            })
        degree: dict[str, int] = defaultdict(int)
        selected: list[dict[str, Any]] = []
        for edge in sorted(scored, key=lambda item: (-item["weight"], item["source"], item["target"])):
            if degree[edge["source"]] >= max_connections or degree[edge["target"]] >= max_connections:
                continue
            degree[edge["source"]] += 1; degree[edge["target"]] += 1; selected.append(edge)
        return selected


class EmbeddingRelationshipProvider(GraphRelationshipProvider):
    name = "local_embedding_with_deterministic_fallback"

    def relationships(self, memories: list[dict[str, Any]], max_connections: int = 4) -> list[dict[str, Any]]:
        vectors = {row["memory_id"]: (json.loads(row["vector_json"]), row["model"]) for row in repository.rows("SELECT memory_id,vector_json,model FROM memory_embeddings")}
        scored: list[dict[str, Any]] = []
        for index, source in enumerate(memories):
            if source["id"] not in vectors:
                continue
            for target in memories[index + 1:]:
                if target["id"] not in vectors:
                    continue
                similarity = cosine_similarity(vectors[source["id"]][0], vectors[target["id"]][0])
                if similarity < .72:
                    continue
                scored.append({"source": f"memory:{source['id']}", "target": f"memory:{target['id']}", "type": "semantic_embedding", "weight": round(similarity, 4), "evidence": {"similarity": round(similarity, 4), "model": vectors[source["id"]][1], "reason": "similaridade semântica medida localmente"}})
        if not scored:
            return DeterministicRelationshipProvider().relationships(memories, max_connections)
        degree: dict[str, int] = defaultdict(int); selected = []
        for edge in sorted(scored, key=lambda item: -item["weight"]):
            if degree[edge["source"]] >= max_connections or degree[edge["target"]] >= max_connections:
                continue
            degree[edge["source"]] += 1; degree[edge["target"]] += 1; selected.append(edge)
        return selected


class CognitiveGraphService:
    def __init__(self, relationship_provider: GraphRelationshipProvider | None = None) -> None:
        self.relationship_provider = relationship_provider or EmbeddingRelationshipProvider()

    @staticmethod
    def _freshness(item: dict[str, Any]) -> float:
        value = item.get("last_used_at") or item.get("updated_at") or item.get("created_at")
        try:
            age_days = max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(value)).total_seconds() / 86400)
        except Exception:
            age_days = 365.0
        return round(max(0.2, 1 / (1 + age_days / 45)), 4)

    def build(self, tool_catalog: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        memories = repository.rows("SELECT * FROM memories WHERE status='active' ORDER BY id")
        documents = repository.rows("SELECT id,original_name,type,status,chunk_count,created_at FROM documents ORDER BY id")
        tasks = repository.rows("SELECT id,title,description,status,priority,due_at,project,created_at,updated_at FROM tasks WHERE status NOT IN ('done','cancelled') ORDER BY id")
        nodes: list[dict[str, Any]] = [{"id":"core:jarvis","kind":"core","cluster":"core","label":"JARVIS","position":{"x":0.0,"y":0.0,"z":0.0},"size":2.2,"intensity":1.0,"metadata":{"role":"cognitive_core"}}]
        for item in memories:
            cluster = CATEGORY_CLUSTERS.get(item["category"], "other")
            nodes.append({"id":f"memory:{item['id']}","entity_id":item["id"],"kind":"memory","cluster":cluster,"label":item["content"][:90],"position":stable_position(item["id"],cluster),"size":0.38+item["importance"]*0.09,"intensity":self._freshness(item),"metadata":item})
        for item in documents:
            nodes.append({"id":f"document:{item['id']}","entity_id":item["id"],"kind":"document","cluster":"knowledge","label":item["original_name"],"position":stable_position(item["id"],"knowledge",4.5),"size":0.62,"intensity":1.0 if item["status"]=="ready" else 0.45,"metadata":item})
        for item in tasks:
            size = {"normal":0.48,"high":0.62,"critical":0.78,"low":0.4}.get(item["priority"],0.48)
            nodes.append({"id":f"task:{item['id']}","entity_id":item["id"],"kind":"task","cluster":"operations","label":item["title"],"position":stable_position(item["id"],"operations",4.2),"size":size,"intensity":self._freshness(item),"metadata":item})
        for tool in sorted(tool_catalog or [], key=lambda item:item["name"]):
            nodes.append({"id":f"tool:{tool['name']}","entity_id":tool["name"],"kind":"tool","cluster":"tools","label":tool["name"],"position":stable_position(tool["name"],"tools",5.5),"size":0.34,"intensity":0.65,"metadata":tool})
        computed = self.relationship_provider.relationships(memories)
        stored = repository.rows("SELECT r.* FROM memory_relationships r JOIN memories s ON s.id=r.source_memory_id JOIN memories t ON t.id=r.target_memory_id WHERE s.status='active' AND t.status='active' ORDER BY r.weight DESC,r.source_memory_id,r.target_memory_id")
        candidates = [{**edge, "connection_class": "memory_relationship"} for edge in computed] + [{"source":f"memory:{item['source_memory_id']}","target":f"memory:{item['target_memory_id']}","type":item["relationship_type"],"weight":item["weight"],"evidence":json.loads(item["evidence_json"]),"connection_class":"memory_relationship"} for item in stored]
        degree: dict[str,int] = defaultdict(int); seen: set[tuple[str,str,str]] = set(); edges: list[dict[str,Any]] = []
        for edge in sorted(candidates,key=lambda item:(-item["weight"],item["source"],item["target"],item["type"])):
            key=(edge["source"],edge["target"],edge["type"])
            if key in seen or degree[edge["source"]]>=4 or degree[edge["target"]]>=4: continue
            seen.add(key);degree[edge["source"]]+=1;degree[edge["target"]]+=1;edges.append(edge)
        for node in nodes:
            if node["kind"] in {"document","task","tool"}:
                connection_class = "tool_connection" if node["kind"] == "tool" else "structural_connection"
                edges.append({"source":"core:jarvis","target":node["id"],"type":f"structural_{node['kind']}","weight":0.18 if node["kind"] == "tool" else 0.28,"connection_class":connection_class,"evidence":{"reason":f"{node['kind']} pertence ao subsistema local do Jarvis"}})
        snapshot = cognitive_state_service.snapshot()
        counts = defaultdict(int)
        for node in nodes: counts[node["kind"]] += 1
        memory_relationships = sum(1 for edge in edges if edge.get("connection_class") == "memory_relationship")
        structural_connections = sum(1 for edge in edges if edge.get("connection_class") == "structural_connection")
        tool_connections = sum(1 for edge in edges if edge.get("connection_class") == "tool_connection")
        return {"nodes":nodes,"edges":edges,"clusters":[{"id":name,"center":{"x":center[0],"y":center[1],"z":center[2]},"count":sum(1 for node in nodes if node["cluster"]==name)} for name,center in CLUSTER_CENTERS.items()],"state":snapshot,"stats":{"nodes":len(nodes),"edges":len(edges),"memories":counts["memory"],"documents":counts["document"],"tasks":counts["task"],"tools":counts["tool"],"memory_relationships":memory_relationships,"structural_connections":structural_connections,"tool_connections":tool_connections,"relationship_provider":self.relationship_provider.name}}

    def memory_created(self, memory_id: str) -> None:
        memory = repository.row("SELECT * FROM memories WHERE id=?", (memory_id,))
        if not memory: return
        relationships = self.relationship_provider.relationships(repository.rows("SELECT * FROM memories WHERE status='active' ORDER BY id"))
        relevant = [edge for edge in relationships if edge["source"]==f"memory:{memory_id}" or edge["target"]==f"memory:{memory_id}"]
        with database() as connection:
            for edge in relevant:
                source=edge["source"].split(":",1)[1]; target=edge["target"].split(":",1)[1]; now=utc_now()
                connection.execute("INSERT OR REPLACE INTO memory_relationships VALUES (?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),source,target,edge["type"],edge["weight"],json.dumps(edge["evidence"],ensure_ascii=False),now,now))
        cognitive_state_service.emit(CognitiveEventType.MEMORY_CREATED,{"node_id":f"memory:{memory_id}","relationship_count":len(relevant)})
        cognitive_state_service.emit(CognitiveEventType.GRAPH_CHANGED,{"reason":"memory_created","entity_id":memory_id})

    def record_cooccurrence(self, memory_ids: list[str], max_connections: int = 4) -> None:
        ids = sorted(set(memory_ids))[:6]
        if len(ids) < 2: return
        with database() as connection:
            rows=connection.execute("SELECT source_memory_id,target_memory_id,relationship_type,weight,evidence_json FROM memory_relationships").fetchall()
            degree:dict[str,int]=defaultdict(int);existing:dict[tuple[str,str,str],Any]={}
            for row in rows:
                degree[row[0]]+=1;degree[row[1]]+=1;existing[(row[0],row[1],row[2])]=row
            for index,source in enumerate(ids):
                for target in ids[index+1:]:
                    key=(source,target,"cooccurrence")
                    if key in existing:
                        row=existing[key];evidence=json.loads(row[4]);occurrences=int(evidence.get("occurrences",1))+1
                        connection.execute("UPDATE memory_relationships SET weight=?,evidence_json=?,updated_at=? WHERE source_memory_id=? AND target_memory_id=? AND relationship_type='cooccurrence'",(min(0.85,float(row[3])+.04),json.dumps({"reason":"selecionadas juntas em contexto real","occurrences":occurrences},ensure_ascii=False),utc_now(),source,target))
                    elif degree[source]<max_connections and degree[target]<max_connections:
                        now=utc_now();connection.execute("INSERT INTO memory_relationships VALUES (?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),source,target,"cooccurrence",0.32,json.dumps({"reason":"selecionadas juntas em contexto real","occurrences":1},ensure_ascii=False),now,now));degree[source]+=1;degree[target]+=1
        self.graph_changed("memory_cooccurrence")

    @staticmethod
    def graph_changed(reason: str, entity_id: str | None = None) -> None:
        cognitive_state_service.emit(CognitiveEventType.GRAPH_CHANGED,{"reason":reason,"entity_id":entity_id})


cognitive_graph_service = CognitiveGraphService()
