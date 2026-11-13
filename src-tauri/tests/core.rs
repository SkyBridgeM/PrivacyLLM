use privacyllm::{
    core::*,
    store::{Settings, Store},
};
use serde_json::{json, Value};
fn manual(text: &str, kind: &str, start: usize, end: usize) -> Entity {
    Entity {
        id: uuid::Uuid::new_v4().to_string(),
        text: text.into(),
        entity_type: kind.into(),
        start,
        end,
        confidence: 1.,
        source: "manual".into(),
        selected: true,
        replacement: None,
        reason: None,
        conflict: false,
    }
}
fn normalize(e: &Entity) -> Value {
    json!({"text":e.text,"entity_type":e.entity_type,"start":e.start,"end":e.end,"confidence":e.confidence,"source":e.source,"selected":e.selected,"conflict":e.conflict})
}
#[test]
fn matches_python_baseline_for_recognition_redaction_and_mapping() {
    let fixture: Value =
        serde_json::from_str(include_str!("fixtures/python_baseline.json")).unwrap();
    let dictionary: Vec<DictionaryEntry> =
        serde_json::from_value(fixture["dictionary"].clone()).unwrap();
    let rules: Vec<CustomRule> = serde_json::from_value(fixture["rules"].clone()).unwrap();
    for case in fixture["cases"].as_array().unwrap() {
        let text = case["text"].as_str().unwrap();
        let entities = recognize(text, &dictionary, &rules).unwrap();
        let mut actual: Vec<_> = entities.iter().map(normalize).collect();
        let mut expected: Vec<_> = case["entities"].as_array().unwrap().clone();
        actual.sort_by_key(Value::to_string);
        expected.sort_by_key(Value::to_string);
        assert_eq!(actual, expected, "recognition differs for {text}");
        let result = anonymize(text, entities).unwrap();
        assert_eq!(
            result.text,
            case["redacted"].as_str().unwrap(),
            "redaction differs for {text}"
        );
        assert_eq!(
            serde_json::to_value(&result.mapping.mappings).unwrap(),
            case["mappings"]
        );
        assert_eq!(restore(&result.text, &result.mapping).unwrap().text, text);
    }
}
#[test]
fn unicode_round_trip_and_same_value_placeholder() {
    let text = "😀𠮷e\u{301}张伟联系张伟";
    let result = anonymize(
        text,
        vec![
            manual("张伟", "PERSON", 4, 6),
            manual("张伟", "PERSON", 8, 10),
        ],
    )
    .unwrap();
    assert_eq!(result.text, "😀𠮷e\u{301}[PERSON_001]联系[PERSON_001]");
    assert_eq!(result.mapping.mappings.len(), 1);
    assert_eq!(restore(&result.text, &result.mapping).unwrap().text, text);
}
#[test]
fn rejects_overlapping_or_stale_ranges() {
    assert!(anonymize(
        "重庆城投集团",
        vec![
            manual("重庆城投集团", "ORGANIZATION", 0, 6),
            manual("城投集团", "ORGANIZATION", 2, 6)
        ]
    )
    .is_err());
    assert!(anonymize("张伟", vec![manual("李伟", "PERSON", 0, 2)]).is_err());
    assert!(anonymize("张伟", vec![manual("张伟", "PERSON", 0, 3)]).is_err());
}
#[test]
fn validates_mapping_versions_duplicates_and_unknown_tokens() {
    let mapping = MappingDocument {
        version: 1,
        created_at: "2026-11-13T00:00:00+08:00".into(),
        document_id: "legacy".into(),
        mappings: vec![
            MappingEntry {
                placeholder: "[PERSON_001]".into(),
                original: "张伟[PHONE_001]".into(),
                entity_type: "PERSON".into(),
            },
            MappingEntry {
                placeholder: "[PHONE_001]".into(),
                original: "13812345678".into(),
                entity_type: "PHONE".into(),
            },
        ],
    };
    let restored = restore("[PERSON_001]和[EMAIL_001]", &mapping).unwrap();
    assert_eq!(restored.text, "张伟[PHONE_001]和[EMAIL_001]");
    assert_eq!(restored.unknown_placeholders, vec!["[EMAIL_001]"]);
    assert_eq!(restored.unused_mappings, vec!["[PHONE_001]"]);
    let mut invalid = mapping.clone();
    invalid.version = 2;
    assert!(restore("", &invalid).is_err());
    invalid = mapping.clone();
    invalid.mappings.push(mapping.mappings[0].clone());
    assert!(restore("", &invalid).is_err());
}
#[test]
fn conflicting_types_require_review() {
    let entities = merge(vec![
        manual("渝西专项", "PROJECT", 0, 4),
        manual("专项", "CUSTOM", 2, 4),
    ]);
    assert!(entities.iter().all(|e| e.conflict && !e.selected));
}
#[test]
fn custom_rules_validate_and_bound_backtracking() {
    let rule = |pattern: &str| CustomRule {
        name: "test".into(),
        pattern: pattern.into(),
        entity_type: "CUSTOM".into(),
        enabled: true,
        selected: true,
        test_samples: vec![],
    };
    assert!(rule("[").compile().is_err());
    assert!(rule(r"\d*").compile().is_err());
    let slow = rule(r"(a+)+(?=b)");
    let text = "a".repeat(10_000);
    assert!(recognize(&text, &[], &[slow]).is_err());
    assert_eq!(
        recognize("项目YX-2026-001", &[], &[rule(r"(?<=项目)YX-\d{4}-\d{3}")]).unwrap()[0].text,
        "YX-2026-001"
    );
}
#[test]
fn config_saves_atomically_and_preserves_backup() {
    let dir = tempfile::tempdir().unwrap();
    let store = Store::new(dir.path().into()).unwrap();
    let defaults = store.settings().unwrap();
    assert!(!defaults.entity_defaults["AMOUNT"]);
    store.save("settings.json", &defaults).unwrap();
    let mut changed = defaults.clone();
    changed.entity_defaults.insert("AMOUNT".into(), true);
    store.save("settings.json", &changed).unwrap();
    assert!(store.settings().unwrap().entity_defaults["AMOUNT"]);
    let backup: Settings =
        serde_json::from_slice(&std::fs::read(dir.path().join("settings.json.bak")).unwrap())
            .unwrap();
    assert!(!backup.entity_defaults["AMOUNT"]);
    std::fs::write(dir.path().join("dictionary.json"), "invalid").unwrap();
    assert!(store.dictionary().is_err());
}
#[test]
fn imports_legacy_configs_without_modifying_source() {
    let source = tempfile::tempdir().unwrap();
    let destination = tempfile::tempdir().unwrap();
    std::fs::write(
        source.path().join("dictionary.json"),
        r#"[{"value":"北辰计划","entity_type":"PROJECT","enabled":true,"selected":true}]"#,
    )
    .unwrap();
    std::fs::write(
        source.path().join("settings.json"),
        r#"{"entity_defaults":{"AMOUNT":true}}"#,
    )
    .unwrap();
    let store = Store::new(destination.path().into()).unwrap();
    store.import_directory(source.path()).unwrap();
    assert_eq!(store.dictionary().unwrap()[0].value, "北辰计划");
    assert!(store.settings().unwrap().entity_defaults["AMOUNT"]);
    assert!(!source.path().join("settings.json.bak").exists());
}
#[test]
fn limits_input_and_rejects_invalid_entity_metadata() {
    assert!(recognize(&"字".repeat(50_001), &[], &[]).is_err());
    let mut e = manual("张伟", "PERSON", 0, 2);
    e.confidence = f64::NAN;
    assert!(e.validate().is_err());
    e.confidence = 1.;
    e.entity_type = "UNKNOWN".into();
    assert!(e.validate().is_err());
}
