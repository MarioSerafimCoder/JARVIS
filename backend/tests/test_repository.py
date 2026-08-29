from app.services.repository import repository


def test_conversation_history_persists():
    conversation = repository.create_conversation("Teste")
    repository.add_message(conversation["id"], "user", "Olá")
    repository.add_message(conversation["id"], "assistant", "Olá. Como posso ajudar?", {"memories": []})
    messages = repository.rows("SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at", (conversation["id"],))
    assert [message["role"] for message in messages] == ["user", "assistant"]


def test_activity_records_real_action():
    repository.audit("test_tool", {"value": 1}, {"ok": True}, "success")
    item = repository.row("SELECT tool, status FROM activity_log")
    assert item == {"tool": "test_tool", "status": "success"}

