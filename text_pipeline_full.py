# text_pipeline_full.py
import asyncio
import re
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

# sentence-transformers for embeddings
from sentence_transformers import SentenceTransformer

# Import Supabase client
import importlib.util
import sys

# Load the policy module with space in filename
spec = importlib.util.spec_from_file_location("policy", "policy (1).py")
policy_module = importlib.util.module_from_spec(spec)
sys.modules["policy"] = policy_module
spec.loader.exec_module(policy_module)
supabase = policy_module.supabase

# Try to import LanceDB; if not available, fallback to in-memory index
try:
    import lancedb
    import pyarrow as pa
    LANCEDB_AVAILABLE = True
except Exception:
    LANCEDB_AVAILABLE = False
    pa = None  # type: ignore

# -------------------------
# Config / constants
# -------------------------
LOG = logging.getLogger("text_pipeline")
logging.basicConfig(level=logging.INFO)

KEYWORDS = {
    "pii": ["ssn", "social security", "passport", "aadhar", "email", "pan"],
    "ip": ["ip", "ipv4", "ipv6"],
    "salary": ["salary", "ctc", "pay", "compensation", "income"],
}

# Regex for money/number detection (simple heuristics)
MONEY_REGEX = re.compile(
    r"(\b\d{1,3}(?:,?\d{2,3})*(?:\.\d+)?\s*(?:lpa|lakhs|lakh|lak|k|kpa|₹|rs|rs\.|usd|dollars|eur|€)\b)|(\b\d+(\.\d+)?\s*(?:k|m|bn)\b)",
    re.I,
)
IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+")

SEMANTIC_MATCH_THRESHOLD = 0.78  # tune this in prod - increased to reduce false positives
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 5
WORKER_COUNT = 2

# -------------------------
# App + Model
# -------------------------
app = FastAPI(title="Text Chunk Processing Pipeline (Immediate hits + Async semantic)")

# Embedding model. This will download first run (sentence-transformers)
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(EMBEDDING_MODEL_NAME)

# -------------------------
# Policy index (LanceDB or in-memory fallback)
# -------------------------
POLICIES = [
    {"policy_id": "p_salary", "text": "Do not share details about salary or CTC."},
    {"policy_id": "p_pii", "text": "Do not share personal identifiers such as SSN, passport, Aadhar."},
    {"policy_id": "p_ip", "text": "IP addresses are sensitive network artifacts."},
    {"policy_id": "Revenue", "text": "Do not share details about revenue or financial information."},
]

if LANCEDB_AVAILABLE:
    LOG.info("LanceDB available: using LanceDB for policy index")
    # Create / open a local lancedb folder (adjust path as needed)
    db = lancedb.connect("./lancedb_policies")
    # create_table will reuse if exists depending on version; handle gracefully
    try:
        # Use a proper PyArrow schema; vector length need not be enforced here
        schema = pa.schema([
            pa.field("policy_id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("embedding", pa.list_(pa.float32())),
        ])
        policy_table = db.create_table("policies", schema=schema)
    except Exception:
        policy_table = db.open_table("policies")
    # Populate if empty
    try:
        row_count = policy_table.count_rows()
    except Exception:
        try:
            row_count = len(policy_table)  # type: ignore
        except Exception:
            row_count = 0
    if row_count == 0:
        LOG.info("Populating LanceDB policy table...")
        insert_batch = []
        for p in POLICIES:
            emb = model.encode(p["text"]).tolist()
            insert_batch.append({"policy_id": p["policy_id"], "text": p["text"], "embedding": emb})
        try:
            policy_table.add(insert_batch)
        except Exception:
            # Fallback to older API name if present
            policy_table.insert(insert_batch)  # type: ignore[attr-defined]
        # create an index on embeddings (API may differ between lancedb versions)
        try:
            policy_table.create_index("embedding", metric="cosine")
        except Exception:
            LOG.info("Could not create LanceDB index (API difference).")
else:
    LOG.info("LanceDB not available: using in-memory policy index fallback.")
    # Precompute embeddings in memory
    for p in POLICIES:
        p["embedding"] = model.encode(p["text"]).tolist()

# -------------------------
# In-memory storage / queue for demo
# -------------------------
processing_queue: asyncio.Queue = asyncio.Queue()
# storage for chunk records; in prod this should be Postgres/Redis/etc.
CHUNKS: Dict[str, dict] = {}

# -------------------------
# Request payloads
# -------------------------
class Chunk(BaseModel):
    text: str
    source: Optional[str] = None
    metadata: Optional[dict] = None

class IncidentCreateRequest(BaseModel):
    id: UUID
    resource_id: UUID
    rule_id: UUID
    channel: Optional[str] = None
    entity_value: Optional[str] = None
    action: Optional[str] = None
    justification: Optional[str] = None
    confidence: int = None

class IncidentUpdateRequest(BaseModel):
    id: UUID
    rule_id: UUID
    resource_id: UUID
    channel: Optional[str] = None
    entity_value: Optional[str] = None
    action: Optional[str] = None
    justification: Optional[str] = None
    confidence: int = None

# -------------------------
# Utility functions: normalization, matching
# -------------------------
def normalize_text(s: str) -> str:
    return " ".join(s.strip().split()).lower()

def keyword_match(text: str) -> Optional[dict]:
    t = normalize_text(text)
    hits = []
    for cat, keys in KEYWORDS.items():
        for k in keys:
            if re.search(rf"\b{re.escape(k)}\b", t):
                hits.append(cat)
                break
    return {"categories": hits} if hits else None

def regex_match(text: str) -> Optional[dict]:
    # IP
    m_ip = IP_REGEX.search(text)
    if m_ip:
        return {"type": "ip", "match": m_ip.group()}
    # Email
    m_email = EMAIL_REGEX.search(text)
    if m_email:
        return {"type": "email", "match": m_email.group()}
    # Salary / Money: only treat as match if salary keyword present AND money pattern found
    t = normalize_text(text)
    if any(k in t for k in KEYWORDS["salary"]) and MONEY_REGEX.search(text):
        m_money = MONEY_REGEX.search(text)
        return {"type": "salary_value", "match": m_money.group()}
    return None

def grammar_heuristic_salary(text: str) -> bool:
    # crude heuristic: salary keyword + numeric token nearby
    words = text.split()
    t = normalize_text(text)
    if not any(k in t for k in KEYWORDS["salary"]):
        return False
    if MONEY_REGEX.search(text):
        return True
    # fallback: look for digits near keyword
    for i, w in enumerate(words):
        if w.lower() in KEYWORDS["salary"]:
            window = words[max(0, i-3): i+4]
            if any(re.search(r"\d", tok) for tok in window):
                return True
    return False

# -------------------------
# Embedding & semantic search helpers
# -------------------------
def embed_text(text: str) -> List[float]:
    return model.encode(text).tolist()

def cosine_similarity(a: List[float], b: List[float]) -> float:
    # small utility if LanceDB not used. compute cosine similarity
    import math
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na*nb)

def semantic_search_against_policies(embedding: List[float], top_k: int = 2) -> List[dict]:
    hits = []
    if LANCEDB_AVAILABLE:
        # Prefer new API style; fallback if it fails
        try:
            results = policy_table.search(embedding).limit(top_k).to_list()
            for r in results:
                if isinstance(r, dict):
                    # LanceDB returns distance, convert to similarity
                    distance = float(r.get("score", r.get("_distance", 2.0)))
                    similarity = max(0.0, 1.0 - (distance / 2.0))  # Convert cosine distance to similarity
                    pid = r.get("policy_id")
                    ptext = r.get("text")
                    if similarity >= SEMANTIC_MATCH_THRESHOLD:
                        hits.append({"policy_id": pid, "policy_text": ptext, "score": similarity})
        except Exception:
            try:
                # Older style example path
                results = policy_table.search(embedding, limit=top_k)
                for r in results:
                    distance = float(r.get("score", 2.0)) if isinstance(r, dict) else 2.0
                    similarity = max(0.0, 1.0 - (distance / 2.0))  # Convert distance to similarity
                    row = r.get("row", r) if isinstance(r, dict) else r
                    pid = row.get("policy_id") if isinstance(row, dict) else getattr(row, "policy_id", None)
                    ptext = row.get("text") if isinstance(row, dict) else getattr(row, "text", None)
                    if similarity >= SEMANTIC_MATCH_THRESHOLD:
                        hits.append({"policy_id": pid, "policy_text": ptext, "score": similarity})
            except Exception:
                # Final fallback: compute in-memory
                for p in POLICIES:
                    p_emb = model.encode(p["text"]).tolist()
                    similarity = cosine_similarity(embedding, p_emb)
                    if similarity >= SEMANTIC_MATCH_THRESHOLD:
                        hits.append({"policy_id": p["policy_id"], "policy_text": p["text"], "score": similarity})
        # Sort and trim
        hits.sort(key=lambda x: x["score"], reverse=True)
        hits = hits[:top_k]
    else:
        # simple in-memory linear scan
        for p in POLICIES:
            similarity = cosine_similarity(embedding, p["embedding"])
            if similarity >= SEMANTIC_MATCH_THRESHOLD:
                hits.append({"policy_id": p["policy_id"], "policy_text": p["text"], "score": similarity})
        hits.sort(key=lambda x: x["score"], reverse=True)
        hits = hits[:top_k]
    return hits

# -------------------------
# Decision logic
# -------------------------
def decide_policy_violation(chunk_record: dict, keyword_info: Optional[dict], regex_info: Optional[dict], semantic_hits: List[dict]):
    # Priority: deterministic regex hits (PII/IP/salary numeric) -> semantic -> clean
    if regex_info:
        if regex_info["type"] == "salary_value":
            # use additional grammar heuristic to avoid false positives like "salary is good"
            if grammar_heuristic_salary(chunk_record["text"]):
                return {"violation": True, "reason": "salary_value_regex", "evidence": regex_info}
            else:
                return {"violation": False, "reason": "salary_regex_not_confirmed_by_heuristic"}
        # Other sensitive regex hits are immediate violations
        return {"violation": True, "reason": regex_info["type"], "evidence": regex_info}
    # No regex hit but keywords present: use semantic analysis (but this branch is usually async)
    if semantic_hits:
        return {"violation": True, "reason": "semantic_policy_match", "evidence": semantic_hits}
    # No matches
    return {"violation": False, "reason": "no_match"}

# -------------------------
# Background worker(s)
# -------------------------
async def worker_loop(worker_id: int):
    LOG.info(f"Worker {worker_id} started")
    while True:
        item = await processing_queue.get()
        try:
            await process_chunk_async(item)
        except Exception as e:
            LOG.exception("Worker error: %s", e)
        finally:
            processing_queue.task_done()

async def process_chunk_async(item: dict):
    chunk_id = item["chunk_id"]
    record = CHUNKS.get(chunk_id)
    if not record:
        LOG.warning("Record not found for chunk_id %s", chunk_id)
        return
    text = record["text"]
    retries = item.get("retries", 0)

    # First-level synchronous checks already done on ingest.
    # Here we perform deferred retry behavior, then embedding search.
    # If keyword/regex were found earlier, we would have returned immediately at ingest.
    # Re-run lightweight checks to be safe
    kw = keyword_match(text)
    rx = regex_match(text)
    if kw or rx:
        decision = decide_policy_violation(record, kw, rx, [])
        record["checked_at"] = datetime.utcnow()
        record["decision"] = decision
        record["checked_by"] = f"worker-{uuid.uuid4().hex[:6]}"
        LOG.info("Deferred quick match for %s -> %s", chunk_id, decision)
        return

    # Retry if not exceeded
    if retries < MAX_RETRIES:
        # schedule re-try with delay (non-blocking)
        await asyncio.sleep(RETRY_DELAY_SECONDS)
        await processing_queue.put({"chunk_id": chunk_id, "retries": retries + 1})
        LOG.debug("Retrying chunk %s (retry #%s)", chunk_id, retries+1)
        return

    # Embedding-based semantic search
    embedding = embed_text(text)
    semantic_hits = semantic_search_against_policies(embedding, top_k=5)
    decision = decide_policy_violation(record, kw, rx, semantic_hits)
    record["embedding"] = embedding  # store embedding in memory for demo
    record["checked_at"] = datetime.utcnow()
    record["decision"] = decision
    record["checked_by"] = "semantic-worker"
    LOG.info("Semantic check for %s -> %s", chunk_id, decision)

# -------------------------
# Startup: spawn workers via lifespan
# -------------------------
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    for i in range(WORKER_COUNT):
        asyncio.create_task(worker_loop(i))
    yield

app.router.lifespan_context = app_lifespan

# -------------------------
# Endpoints
# -------------------------
@app.post("/ingest")
async def ingest_chunk(payload: Chunk):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty text")

    chunk_id = str(uuid.uuid4())
    record = {
        "id": chunk_id,
        "text": text,
        "source": payload.source,
        "metadata": payload.metadata or {},
        "created_at": datetime.utcnow(),
        "decision": None,
        "checked_at": None,
    }
    CHUNKS[chunk_id] = record

    # Immediate synchronous checks (fast path)
    kw = keyword_match(text)
    rx = regex_match(text)
    if rx:
        # Immediate deterministic hit -> return immediately
        decision = decide_policy_violation(record, kw, rx, [])
        record["decision"] = decision
        record["checked_at"] = datetime.utcnow()
        record["checked_by"] = "sync-check"
        return {"chunk_id": chunk_id, "status": "hit", "decision": decision}

    # If keyword match exists (but no deterministic regex), perform semantic search synchronously
    if kw:
        # Perform semantic search immediately
        embedding = embed_text(text)
        semantic_hits = semantic_search_against_policies(embedding, top_k=5)
        decision = decide_policy_violation(record, kw, rx, semantic_hits)
        record["decision"] = decision
        record["checked_at"] = datetime.utcnow()
        record["checked_by"] = "sync-semantic"
        record["embedding"] = embedding  # store embedding for demo
        return {"chunk_id": chunk_id, "status": "completed", "decision": decision, "note": "keyword found; semantic check completed synchronously"}

    # No quick matches -> perform semantic search synchronously
    embedding = embed_text(text)
    semantic_hits = semantic_search_against_policies(embedding, top_k=5)
    decision = decide_policy_violation(record, kw, rx, semantic_hits)
    record["decision"] = decision
    record["checked_at"] = datetime.utcnow()
    record["checked_by"] = "sync-semantic"
    record["embedding"] = embedding  # store embedding for demo
    return {"chunk_id": chunk_id, "status": "completed", "decision": decision, "note": "no immediate hit; semantic check completed synchronously"}

@app.get("/status/{chunk_id}")
def get_status(chunk_id: str):
    rec = CHUNKS.get(chunk_id)
    if not rec:
        raise HTTPException(status_code=404, detail="not found")
    return rec

@app.get("/health")
def health():
    return {"status": "ok", "queued": processing_queue.qsize()}

# -------------------------
# Example helper endpoint: add a policy (runtime)
# -------------------------
@app.post("/policy/add")
def add_policy(policy_id: str, text: str):
    # Danger: in-memory only in this demo. For production insert into LanceDB table.
    if LANCEDB_AVAILABLE:
        emb = model.encode(text).tolist()
        try:
            policy_table.add([{ "policy_id": policy_id, "text": text, "embedding": emb }])
        except Exception:
            policy_table.insert([{ "policy_id": policy_id, "text": text, "embedding": emb }])  # type: ignore[attr-defined]
        try:
            policy_table.create_index("embedding", metric="cosine")
        except Exception:
            pass
        return {"status": "ok", "method": "lancedb"}
    else:
        emb = model.encode(text).tolist()
        POLICIES.append({"policy_id": policy_id, "text": text, "embedding": emb})
        return {"status": "ok", "method": "in-memory"}

# -------------------------
# Incident endpoints
# -------------------------
@app.post("/incident")
async def create_incident(payload: IncidentCreateRequest):
    """Create a new incident in the Supabase incident table"""
    try:
        # Generate a new UUID for the incident
        # incident_id = str(uuid.uuid4())
        
        # Prepare the data for insertion
        incident_data = {
            "id": str(payload.id),
            "rule_id": str(payload.rule_id),
            "resource_id": str(payload.resource_id),
            "channel": payload.channel,
            "entity_value": payload.entity_value,
            "action": payload.action,
            "confidence": payload.confidence,
            "justification": payload.justification,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Insert into Supabase
        result = supabase.table("incident").insert(incident_data).execute()
        
        if result.data:
            return {"status": "success", "incident_id": str(payload.id), "data": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create incident")
            
    except Exception as e:
        LOG.error(f"Error creating incident: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.put("/incident")
async def update_incident(payload: IncidentUpdateRequest):
    """Update an existing incident in the Supabase incident table"""
    try:
        # Prepare the data for update
        update_data = {
            "id": str(payload.id),
            "resource_id": str(payload.resource_id),
            "rule_id": str(payload.rule_id),
            "channel": payload.channel,
            "entity_value": payload.entity_value,
            "action": payload.action,
            "confidence": payload.confidence,
            "justification": payload.justification
        }
        
        # Update in Supabase
        result = supabase.table("incident").update(update_data).eq("id", str(payload.id)).execute()
        
        if result.data:
            return {"status": "success", "incident_id": str(payload.id), "data": result.data[0]}
        else:
            raise HTTPException(status_code=404, detail="Incident not found or no changes made")
            
    except Exception as e:
        LOG.error(f"Error updating incident: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# -------------------------
# Run instructions (comment)
# -------------------------
# Run with:
#   uvicorn text_pipeline_full:app --reload --port 8000
#
# Example usage:
#   POST /ingest  { "text": "My salary is 14lpa", "source": "slack" } -> immediate "hit"
#   POST /ingest  { "text": "I like my salary, though", "source": "email" } -> queued (no immediate regex match)
#   GET /status/<chunk_id> -> returns decision, checked_at, etc.
#
# Production improvements:
#  - Persistent chunk store (Postgres), durable queue (Redis/Kafka/SQS), workers autoscaled
#  - Rate limiting, auth, TLS, logging to central store, observability (Prometheus/Grafana)
#  - Human-in-loop review UI for borderline semantic hits
