from app.core.entities import EntityType
from app.recognizers.regex_recognizer import RegexRecognizer


def by_type(text: str) -> dict[EntityType, list[str]]:
    found: dict[EntityType, list[str]] = {}
    for entity in RegexRecognizer().analyze(text):
        found.setdefault(entity.entity_type, []).append(entity.text)
    return found


def test_recognizes_common_structured_entities() -> None:
    text = (
        "电话13812345678，邮箱alice@example.com，"
        "身份证11010519491231002X，IP为192.168.1.1。"
    )
    found = by_type(text)
    assert found[EntityType.PHONE] == ["13812345678"]
    assert found[EntityType.EMAIL] == ["alice@example.com"]
    assert found[EntityType.ID_CARD] == ["11010519491231002X"]
    assert found[EntityType.IP_ADDRESS] == ["192.168.1.1"]


def test_rejects_invalid_id_ip_and_date() -> None:
    text = "身份证11010519491331002X，IP 999.1.1.1，日期2026-02-30。"
    assert RegexRecognizer().analyze(text) == []


def test_amount_and_date_are_not_selected_by_default() -> None:
    entities = RegexRecognizer().analyze("金额人民币 12.50万元，日期2026年7月30日。")
    assert {(item.entity_type, item.selected) for item in entities} == {
        (EntityType.AMOUNT, False),
        (EntityType.DATE, False),
    }


def test_bank_card_requires_luhn() -> None:
    found = by_type("卡号4111111111111111，无效卡4111111111111112。")
    assert found[EntityType.BANK_CARD] == ["4111111111111111"]


def test_offsets_are_python_character_offsets_with_emoji() -> None:
    text = "😀联系13812345678"
    entity = RegexRecognizer().analyze(text)[0]
    assert entity.start == 3
    assert text[entity.start : entity.end] == entity.text

