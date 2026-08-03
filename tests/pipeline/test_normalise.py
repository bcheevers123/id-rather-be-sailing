from pipeline.normalise import make_slug, normalise_provider, extract_contact_parts


def test_make_slug_basic():
    assert make_slug("Maritime Skills Academy (Dover)") == "maritime-skills-academy-dover"


def test_make_slug_strips_punctuation():
    assert make_slug("UHI North West & Hebrides") == "uhi-north-west-hebrides"


def test_make_slug_deduplicates_with_counter():
    slug1 = make_slug("Seascope Maritime Training")
    slug2 = make_slug("Seascope Maritime Training", existing={"seascope-maritime-training"})
    assert slug2 == "seascope-maritime-training-2"


def test_extract_contact_parts_full():
    raw = "Tel: 01234 567890\nEmail: test@example.com\nhttps://example.com/"
    parts = extract_contact_parts(raw)
    assert parts["telephone"] == "01234 567890"
    assert parts["email"] == "test@example.com"
    assert parts["website"] == "https://example.com/"


def test_extract_contact_parts_missing():
    parts = extract_contact_parts("Not open to public")
    assert parts["telephone"] is None
    assert parts["email"] is None
    assert parts["website"] is None
