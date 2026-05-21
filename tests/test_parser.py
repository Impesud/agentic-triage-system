import pytest

from parsing.parser import parse_llm_output


def test_parse_llm_output_valid():
    raw = (
        '{"analisi_problema":"1. Problema: conferma bonifico. '
        '2. Contesto: pagamento effettuato. '
        '3. Categoria: BILLING. 4. Priorità: MEDIUM.",'
        '"categoria":"BILLING","priorita":"MEDIUM",'
        '"riassunto_breve":"Conferma bonifico",'
        '"messaggio_originale":"Ho effettuato un bonifico"}'
    )
    result = parse_llm_output(raw)
    assert result.categoria == "BILLING"
    assert result.analisi_problema


def test_parse_llm_output_strips_markdown_fence():
    raw = (
        '```json\n{"analisi_problema":"1. P. 2. C. 3. Cat IT. 4. Pri LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"test ok",'
        '"messaggio_originale":"help"}\n```'
    )
    assert parse_llm_output(raw).categoria == "IT"


def test_parse_llm_output_missing_json_raises():
    with pytest.raises(ValueError, match="Nessun JSON"):
        parse_llm_output("risposta senza oggetto json")
