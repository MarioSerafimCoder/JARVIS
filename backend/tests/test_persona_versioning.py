from app.core import persona


def test_existing_custom_persona_is_preserved_until_explicit_update(tmp_path, monkeypatch):
    default = tmp_path / "default.md"
    current = tmp_path / "data" / "persona.md"
    meta = tmp_path / "data" / "persona.meta.json"
    default.write_text("Nova persona padrão com conteúdo suficientemente completo para o teste.", encoding="utf-8")
    current.parent.mkdir(parents=True)
    current.write_text("Minha persona personalizada existente não pode ser perdida silenciosamente.", encoding="utf-8")
    monkeypatch.setattr(persona, "DEFAULT_PERSONA_PATH", default)
    monkeypatch.setattr(persona, "PERSONA_PATH", current)
    monkeypatch.setattr(persona, "PERSONA_META_PATH", meta)
    persona.ensure_persona()
    assert persona.load_persona().startswith("Minha persona personalizada")
    assert persona.persona_status()["update_available"] is True
    persona.update_to_default()
    assert persona.load_persona().startswith("Nova persona padrão")
