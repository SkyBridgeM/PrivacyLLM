use chrono::{Local, NaiveDate};
use fancy_regex::RegexBuilder;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::LazyLock,
};
use uuid::Uuid;

pub type Result<T> = std::result::Result<T, String>;
pub const TYPES: &[&str] = &[
    "PERSON",
    "ORGANIZATION",
    "PROJECT",
    "DEPARTMENT",
    "LOCATION",
    "PHONE",
    "ID_CARD",
    "BANK_CARD",
    "EMAIL",
    "CREDIT_CODE",
    "SECURITY_CODE",
    "AMOUNT",
    "DATE",
    "IP_ADDRESS",
    "BUSINESS_SECRET",
    "CUSTOM",
];
fn yes() -> bool {
    true
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entity {
    pub id: String,
    pub text: String,
    pub entity_type: String,
    pub start: usize,
    pub end: usize,
    pub confidence: f64,
    pub source: String,
    #[serde(default = "yes")]
    pub selected: bool,
    #[serde(default)]
    pub replacement: Option<String>,
    #[serde(default)]
    pub reason: Option<String>,
    #[serde(default)]
    pub conflict: bool,
}
impl Entity {
    pub fn new(source: &str, start: usize, end: usize, kind: &str, origin: &str) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            text: source[start..end].into(),
            entity_type: kind.into(),
            start: source[..start].chars().count(),
            end: source[..end].chars().count(),
            confidence: 1.,
            source: origin.into(),
            selected: true,
            replacement: None,
            reason: None,
            conflict: false,
        }
    }
    pub fn validate(&self) -> Result<()> {
        validate_type(&self.entity_type)?;
        if self.end <= self.start
            || self.end - self.start != self.text.chars().count()
            || !self.confidence.is_finite()
            || !(0.0..=1.0).contains(&self.confidence)
        {
            return Err("实体位置、文字长度或置信度无效".into());
        }
        Ok(())
    }
}
pub fn validate_type(kind: &str) -> Result<()> {
    if TYPES.contains(&kind) {
        Ok(())
    } else {
        Err(format!("未知实体类型：{kind}"))
    }
}
pub fn check_text(text: &str, limit: usize) -> Result<()> {
    if text.chars().count() > limit {
        Err(format!("文本超过 {limit} 字符，请分段处理"))
    } else {
        Ok(())
    }
}
pub fn char_slice(text: &str, start: usize, end: usize) -> Option<&str> {
    if start > end {
        return None;
    }
    let positions: Vec<_> = text
        .char_indices()
        .map(|(i, _)| i)
        .chain(std::iter::once(text.len()))
        .collect();
    Some(&text[*positions.get(start)?..*positions.get(end)?])
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DictionaryEntry {
    pub value: String,
    pub entity_type: String,
    #[serde(default = "yes")]
    pub enabled: bool,
    #[serde(default = "yes")]
    pub selected: bool,
}
impl DictionaryEntry {
    pub fn validate(&self) -> Result<()> {
        validate_type(&self.entity_type)?;
        if self.value.trim().is_empty() || self.value.chars().count() > 500 {
            return Err("词典条目须为 1–500 字符".into());
        }
        Ok(())
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CustomRule {
    pub name: String,
    pub pattern: String,
    #[serde(default = "custom_type")]
    pub entity_type: String,
    #[serde(default = "yes")]
    pub enabled: bool,
    #[serde(default = "yes")]
    pub selected: bool,
    #[serde(default)]
    pub test_samples: Vec<String>,
}
fn custom_type() -> String {
    "CUSTOM".into()
}
impl CustomRule {
    pub fn compile(&self) -> Result<fancy_regex::Regex> {
        validate_type(&self.entity_type)?;
        if !Regex::new(r"^[A-Za-z0-9_-]{1,64}$")
            .unwrap()
            .is_match(&self.name)
            || self.pattern.is_empty()
            || self.pattern.chars().count() > 1000
            || self.test_samples.len() > 20
            || self.test_samples.iter().any(|s| s.chars().count() > 2000)
        {
            return Err("自定义规则名称、表达式或测试样例无效".into());
        }
        let re =
            compile_pattern(&self.pattern).map_err(|e| format!("规则 {} 无效：{e}", self.name))?;
        if re.is_match("").map_err(|_| "规则执行超出资源限制")? {
            return Err(format!("规则 {} 不得匹配空字符串", self.name));
        }
        Ok(re)
    }
}
fn compile_pattern(pattern: &str) -> Result<fancy_regex::Regex> {
    RegexBuilder::new(pattern)
        .backtrack_limit(100_000)
        .delegate_size_limit(2 * 1024 * 1024)
        .build()
        .map_err(|e| e.to_string())
}
#[derive(Deserialize)]
struct Rule {
    entity_type: String,
    pattern: String,
    selected: bool,
    confidence: f64,
    validator: Option<String>,
}
static RULES: LazyLock<Vec<(Rule, fancy_regex::Regex)>> = LazyLock::new(|| {
    serde_json::from_str::<Vec<Rule>>(include_str!("rules.json"))
        .unwrap()
        .into_iter()
        .map(|r| {
            let regex = compile_pattern(&r.pattern).expect("validated builtin rule");
            (r, regex)
        })
        .collect()
});
fn valid_value(value: &str, validator: Option<&str>) -> bool {
    match validator {
        Some("_valid_mainland_id") => {
            let b = value.as_bytes();
            if b.len() != 18 || !b[..17].iter().all(u8::is_ascii_digit) {
                return false;
            }
            let date = value[6..10]
                .parse::<i32>()
                .ok()
                .zip(value[10..12].parse::<u32>().ok())
                .zip(value[12..14].parse::<u32>().ok())
                .and_then(|((y, m), d)| NaiveDate::from_ymd_opt(y, m, d));
            let weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2];
            let sum: usize = b[..17]
                .iter()
                .zip(weights)
                .map(|(d, w)| usize::from(*d - b'0') * w)
                .sum();
            date.is_some() && b[17].to_ascii_uppercase() == b"10X98765432"[sum % 11]
        }
        Some("_valid_luhn") => {
            if !value.bytes().all(|b| b.is_ascii_digit()) {
                return false;
            }
            let sum: u32 = value
                .bytes()
                .rev()
                .enumerate()
                .map(|(i, b)| {
                    let d = u32::from(b - b'0');
                    if i % 2 == 1 {
                        let v = d * 2;
                        if v > 9 {
                            v - 9
                        } else {
                            v
                        }
                    } else {
                        d
                    }
                })
                .sum();
            sum.is_multiple_of(10)
        }
        Some("_valid_credit_code") => {
            let charset = b"0123456789ABCDEFGHJKLMNPQRTUWXY";
            let weights = [
                1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28,
            ];
            let b = value.as_bytes();
            if b.len() != 18 || !b[..17].iter().any(u8::is_ascii_alphabetic) {
                return false;
            }
            let digits: Option<Vec<usize>> = b
                .iter()
                .map(|c| charset.iter().position(|v| v == c))
                .collect();
            digits
                .map(|d| {
                    d[17]
                        == (31
                            - d[..17]
                                .iter()
                                .zip(weights)
                                .map(|(n, w)| n * w)
                                .sum::<usize>()
                                % 31)
                            % 31
                })
                .unwrap_or(false)
        }
        Some("_valid_ip") => value.parse::<std::net::Ipv4Addr>().is_ok(),
        Some("_valid_date") => {
            let n: Vec<_> = value
                .split(|c: char| !c.is_ascii_digit())
                .filter(|s| !s.is_empty())
                .collect();
            n.len() == 3
                && n[0]
                    .parse()
                    .ok()
                    .zip(n[1].parse().ok())
                    .zip(n[2].parse().ok())
                    .and_then(|((y, m), d)| NaiveDate::from_ymd_opt(y, m, d))
                    .is_some()
        }
        _ => true,
    }
}
fn overlap(a: &Entity, b: &Entity) -> bool {
    a.start < b.end && b.start < a.end
}
fn structured_priority(kind: &str) -> usize {
    match kind {
        "ID_CARD" => 100,
        "CREDIT_CODE" => 95,
        "BANK_CARD" => 90,
        "PHONE" => 85,
        "EMAIL" => 80,
        "IP_ADDRESS" => 75,
        "SECURITY_CODE" => 60,
        "AMOUNT" => 50,
        "DATE" => 40,
        _ => 0,
    }
}
pub fn recognize(
    text: &str,
    dictionary: &[DictionaryEntry],
    custom: &[CustomRule],
) -> Result<Vec<Entity>> {
    check_text(text, 50_000)?;
    let mut structured = Vec::new();
    for (rule, re) in RULES.iter() {
        for item in re.find_iter(text) {
            let m = item.map_err(|_| "内置规则执行超出资源限制")?;
            if valid_value(m.as_str(), rule.validator.as_deref()) {
                let mut e = Entity::new(text, m.start(), m.end(), &rule.entity_type, "regex");
                e.selected = rule.selected;
                e.confidence = rule.confidence;
                structured.push(e);
            }
        }
    }
    structured.sort_by_key(|e| {
        (
            std::cmp::Reverse(structured_priority(&e.entity_type)),
            std::cmp::Reverse(e.end - e.start),
            e.start,
        )
    });
    let mut all: Vec<Entity> = Vec::new();
    for e in structured {
        if !all.iter().any(|a| overlap(a, &e)) {
            all.push(e);
        }
    }
    for d in dictionary {
        d.validate()?;
        if !d.enabled {
            continue;
        }
        for (start, _) in text.match_indices(&d.value) {
            let mut e = Entity::new(
                text,
                start,
                start + d.value.len(),
                &d.entity_type,
                "dictionary",
            );
            e.selected = d.selected;
            all.push(e);
        }
    }
    for rule in custom {
        let re = rule.compile()?;
        if !rule.enabled {
            continue;
        }
        for item in re.find_iter(text) {
            let m = item.map_err(|_| format!("规则 {} 执行超出资源限制", rule.name))?;
            if m.start() == m.end() {
                return Err(format!("规则 {} 不得产生空匹配", rule.name));
            }
            let mut e = Entity::new(
                text,
                m.start(),
                m.end(),
                &rule.entity_type,
                &format!("custom_regex:{}", rule.name),
            );
            e.selected = rule.selected;
            all.push(e);
        }
    }
    if all.len() > 20_000 {
        return Err("候选项过多，请缩小词典或将文本分段处理".into());
    }
    Ok(merge(all))
}
fn priority(e: &Entity) -> usize {
    e.source
        .split('+')
        .map(|s| match s.split(':').next().unwrap_or("") {
            "manual" => 400,
            "dictionary" => 300,
            "custom_regex" => 250,
            "regex" => 200,
            "semantic" | "qwen" => 100,
            _ => 0,
        })
        .max()
        .unwrap_or(0)
}
pub fn merge(entities: Vec<Entity>) -> Vec<Entity> {
    let mut exact: BTreeMap<(usize, usize, String), Vec<Entity>> = BTreeMap::new();
    for e in entities {
        exact
            .entry((e.start, e.end, e.entity_type.clone()))
            .or_default()
            .push(e);
    }
    let mut result: Vec<Entity> = exact
        .into_values()
        .map(|items| {
            let mut e = items.iter().max_by_key(|e| priority(e)).unwrap().clone();
            e.confidence = items.iter().map(|e| e.confidence).fold(0., f64::max);
            e.selected = items.iter().any(|e| e.selected);
            e.source = items
                .iter()
                .map(|e| e.source.as_str())
                .collect::<BTreeSet<_>>()
                .into_iter()
                .collect::<Vec<_>>()
                .join("+");
            e
        })
        .collect();
    for i in 0..result.len() {
        for j in i + 1..result.len() {
            if result[j].start >= result[i].end {
                break;
            }
            if !overlap(&result[i], &result[j]) {
                continue;
            }
            if result[i].entity_type != result[j].entity_type {
                result[i].conflict = true;
                result[j].conflict = true;
                result[i].selected = false;
                result[j].selected = false;
            } else {
                let loser = if (priority(&result[i]), result[i].end - result[i].start)
                    >= (priority(&result[j]), result[j].end - result[j].start)
                {
                    j
                } else {
                    i
                };
                result[loser].selected = false;
            }
        }
    }
    result
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MappingEntry {
    pub placeholder: String,
    pub original: String,
    pub entity_type: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MappingDocument {
    pub version: u32,
    pub created_at: String,
    pub document_id: String,
    pub mappings: Vec<MappingEntry>,
}
static TOKENS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\[[A-Z][A-Z_]*_\d{3,}\]").unwrap());
fn prefix(kind: &str) -> &str {
    match kind {
        "ORGANIZATION" => "ORG",
        "ID_CARD" => "ID",
        "BANK_CARD" => "BANK",
        "CREDIT_CODE" => "CREDIT",
        "SECURITY_CODE" => "SECURITY",
        "IP_ADDRESS" => "IP",
        _ => kind,
    }
}
#[derive(Serialize)]
pub struct Anonymized {
    pub text: String,
    pub entities: Vec<Entity>,
    pub mapping: MappingDocument,
}
pub fn anonymize(text: &str, entities: Vec<Entity>) -> Result<Anonymized> {
    check_text(text, 50_000)?;
    for e in &entities {
        e.validate()?;
    }
    let mut selected: Vec<_> = entities.into_iter().filter(|e| e.selected).collect();
    selected.sort_by_key(|e| (e.start, e.end));
    let positions: Vec<_> = text
        .char_indices()
        .map(|(i, _)| i)
        .chain(std::iter::once(text.len()))
        .collect();
    for (i, e) in selected.iter().enumerate() {
        let value = positions
            .get(e.start)
            .zip(positions.get(e.end))
            .and_then(|(&start, &end)| text.get(start..end));
        if value != Some(e.text.as_str()) {
            return Err("候选项与当前原文不匹配，请重新识别".into());
        }
        if i > 0 && selected[i - 1].end > e.start {
            return Err("所选实体存在重叠，请先复核冲突".into());
        }
    }
    let mut occupied: BTreeSet<String> =
        TOKENS.find_iter(text).map(|m| m.as_str().into()).collect();
    let mut by_value: BTreeMap<(String, String), String> = BTreeMap::new();
    let mut counters: BTreeMap<String, usize> = BTreeMap::new();
    let mut mappings = Vec::new();
    for e in &mut selected {
        let key = (e.entity_type.clone(), e.text.clone());
        let placeholder = if let Some(p) = by_value.get(&key) {
            p.clone()
        } else {
            let p = loop {
                let count = counters.entry(prefix(&e.entity_type).into()).or_default();
                *count += 1;
                let candidate = format!("[{}_{:03}]", prefix(&e.entity_type), count);
                if !occupied.contains(&candidate) {
                    break candidate;
                }
            };
            occupied.insert(p.clone());
            by_value.insert(key, p.clone());
            mappings.push(MappingEntry {
                placeholder: p.clone(),
                original: e.text.clone(),
                entity_type: e.entity_type.clone(),
            });
            p
        };
        e.replacement = Some(placeholder);
    }
    let mut output = String::with_capacity(text.len());
    let mut cursor = 0;
    for e in &selected {
        output.push_str(&text[cursor..positions[e.start]]);
        output.push_str(e.replacement.as_deref().unwrap());
        cursor = positions[e.end];
    }
    output.push_str(&text[cursor..]);
    Ok(Anonymized {
        text: output,
        entities: selected,
        mapping: MappingDocument {
            version: 1,
            created_at: Local::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
            document_id: Uuid::new_v4().to_string(),
            mappings,
        },
    })
}
#[derive(Serialize)]
pub struct Restored {
    pub text: String,
    pub replaced: Vec<String>,
    pub unused_mappings: Vec<String>,
    pub unknown_placeholders: Vec<String>,
}
impl MappingDocument {
    pub fn validate(&self) -> Result<()> {
        if self.version != 1 {
            return Err("不支持的映射版本".into());
        }
        let mut seen = BTreeSet::new();
        for e in &self.mappings {
            validate_type(&e.entity_type)?;
            if !seen.insert(&e.placeholder)
                || TOKENS
                    .find(&e.placeholder)
                    .is_none_or(|m| m.as_str() != e.placeholder)
            {
                return Err("映射占位符重复或格式无效".into());
            }
        }
        Ok(())
    }
}
pub fn restore(text: &str, mapping: &MappingDocument) -> Result<Restored> {
    check_text(text, 100_000)?;
    mapping.validate()?;
    let lookup: BTreeMap<_, _> = mapping
        .mappings
        .iter()
        .map(|m| (m.placeholder.as_str(), m.original.as_str()))
        .collect();
    let mut seen = BTreeSet::new();
    let mut unknown = BTreeSet::new();
    let output = TOKENS
        .replace_all(text, |caps: &regex::Captures| {
            let token = caps.get(0).unwrap().as_str();
            if let Some(original) = lookup.get(token) {
                seen.insert(token.to_string());
                (*original).to_string()
            } else {
                unknown.insert(token.to_string());
                token.to_string()
            }
        })
        .into_owned();
    let unused = lookup
        .keys()
        .filter(|k| !seen.contains(**k))
        .map(|k| k.to_string())
        .collect();
    Ok(Restored {
        text: output,
        replaced: seen.into_iter().collect(),
        unused_mappings: unused,
        unknown_placeholders: unknown.into_iter().collect(),
    })
}
