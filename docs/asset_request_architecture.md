# Asset Request Flow and Architecture

## Purpose
This document explains how the AI Service Desk handles asset-related user requests, especially the `new laptop` flow. It covers:

- frontend/UI call path
- backend orchestration
- asset intent detection
- asset slot collection
- service request submission to Freshservice

It also includes sample code snippets from the current implementation.

---

## 1. High-level architecture

1. User sends a message through the UI.
2. The UI calls the backend chat API: `POST /api/v1/chat`.
3. Backend stores the message in session memory and then invokes the workflow orchestrator.
4. The orchestration engine runs the LangGraph-based workflow.
5. The `ClarificationAgent` decides if the request is asset-related or needs generic clarification.
6. If asset-related, the `AssetServiceRequestHandler` is invoked.
7. The asset handler collects required fields and submits a Freshservice SR when all slots are complete.

### Architecture components

- `backend/api/routes.py`
- `backend/workflows/orchestrator.py`
- `backend/workflows/clarification_agent.py`
- `backend/workflows/knowledge_engine.py`
- `backend/workflows/asset_service_request_handler.py`
- `backend/workflows/knowledge_base.json`
- `backend/workflows/state.py`

---

## 2. UI call path

The frontend uses the chat endpoint defined in `backend/api/routes.py`.

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatMessageRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not request.session_id:
        db_session = ChatSession()
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        session_id = str(db_session.id)
    else:
        db_session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()

    from workflows.orchestrator import process_service_desk_query
    result = await process_service_desk_query(session_id, request.message)

    return ChatResponse(
        message=result["response"],
        session_id=session_id,
        sources=result["sources"],
        confidence=result["confidence"],
        needs_ticket=result["needs_ticket"],
        routing_history=result.get("routing_history", []),
        sop_steps=result.get("sop_steps", []),
        intent=result.get("intent")
    )
```

This endpoint is the UI entrypoint for both single-turn and multi-turn chat.

---

## 3. Orchestration flow

The main orchestration lives in `backend/workflows/orchestrator.py`.

```python
async def process_service_desk_query(session_id: str, query: str) -> Dict[str, Any]:
    memory_service.save_message(session_id=session_id, role="user", content=query)
    history = memory_service.load_conversation_history(session_id)
    cached_state = memory_service.get_workflow_state(session_id)

    initial_state: ServiceDeskState = {
        "session_id": session_id,
        "query": query,
        "messages": history,
        "skill": cached_state.get("skill"),
        "issue_type": cached_state.get("issue_type"),
        "clarification_answers": cached_state.get("clarification_answers", {}),
        "routing_history": cached_state.get("routing_history", []),
        ...
    }

    final_output = await langgraph_app.graph.ainvoke(initial_state)
```

Key points:

- The query is stored first in history.
- Session state is loaded and reused for multi-turn conversations.
- The compiled LangGraph workflow executes from `ClarificationAgent` onward.

---

## 4. Asset detection logic

The trigger for asset flows is in `backend/workflows/knowledge_engine.py`.

### Important behavior

- The system matches user queries against a knowledge base of skills and issue types.
- Asset intent is only strongly matched when the query contains asset-specific phrases.
- Generic words like `asset` alone are given low weight to prevent false positives.

### Sample asset trigger logic

```python
if issue_key == "asset_allocation_surrender":
    asset_trigger_terms = [
        "asset allocation",
        "surrender",
        "asset request",
        "laptop request",
        "desktop request",
        "tablet request",
        "tab request",
        "new laptop",
        "need laptop",
        "need new laptop",
        "request new laptop",
        "laptop allocation",
        "desktop allocation",
        "new desktop",
        "self-certification",
        "self certification",
        "certification",
        "certify",
        "transfer",
        "promotion",
        "temporary",
        "project",
        "team",
        "joinee",
        "joiner",
        "new joinee"
    ]
    if any(term in query_lower for term in asset_trigger_terms):
        issue_score += 0.6
    elif "asset" in query_lower:
        issue_score += 0.1
```

This is the core change that causes `I need new Laptop please guide me what to do` to route correctly to the asset workflow.

---

## 5. Clarification and asset workflow

Once the query matches `asset_allocation_surrender`, the `ClarificationAgent` intercepts and delegates to the asset-specific handler.

### ClarificationAgent asset interception

```python
if issue_type == "asset_allocation_surrender":
    from workflows.asset_service_request_handler import AssetServiceRequestHandler
    handler = AssetServiceRequestHandler()
    extracted_answers = await handler.extract_asset_details_from_history(messages, clarification_answers)
    clarification_answers.update(extracted_answers)
    next_field = handler.get_next_unanswered_field(clarification_answers)
```

If `next_field` exists, the assistant asks that question.

### First asset prompt question

If the SR type is unknown, the first question is:

```python
"What type of Asset Request would you like to raise? Please select one of the following:\n\n" + \
    "\n".join([f"• *{k}*" for k in ASSET_SR_CATEGORIES.keys()])
```

That returns the list:

- Laptop Request for New Joinee
- Laptop Request in cases of Transfer / Promotion
- Request for allocation of Temporary / Project / Team laptop/Desktop
- Request for replacement of Desktop/Laptop/Tab
- Surrender of Laptop
- Off-Role Joinee Laptop
- Self-Certification of Asset

---

## 6. Asset slot filling

The `AssetServiceRequestHandler` defines required custom fields for each SR type.

Example for `Laptop Request for New Joinee`:

```python
"Laptop Request for New Joinee": [
    {"name": "date_of_joining", "label": "Date of Joining", "type": "custom_date", "question": "What is the new joinee's Date of Joining (YYYY-MM-DD)?"},
    {"name": "name_of_new_joinee", "label": "Name of New Joinee", "type": "custom_text", "question": "What is the full Name of the New Joinee?"},
    {"name": "location_name", "label": "Location Name", "type": "custom_text", "question": "What is the Location Name for delivery?"},
    {"name": "new_joinee_designation", "label": "New Joinee Designation", "type": "custom_text", "question": "What is the New Joinee's Designation?"}
]
```

The handler uses the latest user message and last assistant question to slot-fill values automatically when it can.

---

## 7. Freshservice submission

When all fields are complete, the handler submits the request via Freshservice API.

```python
payload = {
    "quantity": 1,
    "requested_for": requester_email,
    "email": requester_email,
    "custom_fields": custom_fields_payload
}
response = await loop.run_in_executor(
    None,
    lambda: requests.post(url, headers=headers, json=payload, timeout=30.0)
)
```

The payload includes:

- `sr_name`
- `untitled` description
- all collected custom fields specific to the chosen SR type

---

## 8. Sample end-to-end flow

### User message
`I need new Laptop please guide me what to do`

### Expected system behavior
1. `KnowledgeEngine` detects the query as `asset_allocation_surrender`.
2. `ClarificationAgent` routes to `AssetServiceRequestHandler`.
3. The assistant asks:

   `What type of Asset Request would you like to raise? Please select one of the following:`

4. User replies with a selected asset type.
5. System asks follow-up slot questions until all fields are gathered.
6. System submits the Freshservice SR and returns a ticket confirmation.

---

## 9. What changed for this fix

The key code update was in `backend/workflows/knowledge_engine.py`:

- Added new laptop-specific asset trigger phrases such as:
  - `new laptop`
  - `need new laptop`
  - `request new laptop`
  - `laptop allocation`
  - `desktop allocation`
- Kept generic `asset` fallback low to avoid unrelated queries matching asset flows.

This makes the system less likely to misclassify generic support questions as asset requests.

---

## 10. Recommended manager summary

This service uses a conversational AI workflow with deterministic routing and slot filling.

- The UI talks to a FastAPI backend.
- The backend uses stored session memory for multi-turn chats.
- Asset requests are detected by keyword matching plus explicit service request categories.
- Asset-specific questions are asked only when the query is clearly about hardware or laptop provisioning.
- Once complete, the request is placed automatically in Freshservice.

If you want, I can also add a one-page slide version or a diagram in a separate file.
