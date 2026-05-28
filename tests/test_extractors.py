from memory.extractors import detect_sentiment_label, extract_cliente_nome


def test_extract_cliente_marco():
    text = "Salve, sono Marco. Il server non risponde."
    assert extract_cliente_nome(text) == "Marco"


def test_extract_cliente_societa():
    text = "Buongiorno, siamo la società Verdi & Partners."
    assert extract_cliente_nome(text) is not None
    assert "Verdi" in extract_cliente_nome(text)


def test_detect_sentiment_angry():
    angry = "SONO DELUSO! INACCETTABILE! Chiamo l'avvocato!"
    assert detect_sentiment_label(angry) == "ARRABBIATO"


def test_detect_sentiment_neutral():
    calm = "Buongiorno, vorrei informazioni sul corso."
    assert detect_sentiment_label(calm) == "NEUTRO"
