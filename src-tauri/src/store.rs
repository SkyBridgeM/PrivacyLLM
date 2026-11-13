use crate::core::{CustomRule, DictionaryEntry, Result, TYPES};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs,
    io::Write,
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Settings {
    pub entity_defaults: BTreeMap<String, bool>,
}
impl Default for Settings {
    fn default() -> Self {
        Self {
            entity_defaults: TYPES
                .iter()
                .map(|kind| {
                    (
                        kind.to_string(),
                        !matches!(*kind, "SECURITY_CODE" | "AMOUNT" | "DATE"),
                    )
                })
                .collect(),
        }
    }
}
impl Settings {
    pub fn validate(&self) -> Result<()> {
        for key in self.entity_defaults.keys() {
            crate::core::validate_type(key)?;
        }
        Ok(())
    }
}
pub struct Store {
    pub dir: PathBuf,
}
impl Store {
    pub fn new(dir: PathBuf) -> Result<Self> {
        fs::create_dir_all(&dir).map_err(|e| format!("无法创建配置目录：{e}"))?;
        Ok(Self { dir })
    }
    fn load<T: DeserializeOwned>(&self, name: &str) -> Result<T> {
        let raw = fs::read(self.dir.join(name)).map_err(|e| format!("无法读取 {name}：{e}"))?;
        serde_json::from_slice(&raw).map_err(|e| format!("{name} 格式无效：{e}"))
    }
    pub fn save<T: Serialize>(&self, name: &str, value: &T) -> Result<()> {
        let path = self.dir.join(name);
        let mut file = tempfile::NamedTempFile::new_in(&self.dir).map_err(|e| e.to_string())?;
        serde_json::to_writer_pretty(&mut file, value).map_err(|e| e.to_string())?;
        file.write_all(b"\n").map_err(|e| e.to_string())?;
        file.as_file().sync_all().map_err(|e| e.to_string())?;
        if path.exists() {
            fs::copy(&path, path.with_extension("json.bak")).map_err(|e| e.to_string())?;
        }
        file.persist(path).map_err(|e| e.to_string())?;
        Ok(())
    }
    pub fn dictionary(&self) -> Result<Vec<DictionaryEntry>> {
        let entries: Vec<DictionaryEntry> = if self.dir.join("dictionary.json").exists() {
            self.load("dictionary.json")?
        } else {
            Vec::new()
        };
        for entry in &entries {
            entry.validate()?;
        }
        Ok(entries)
    }
    pub fn rules(&self) -> Result<Vec<CustomRule>> {
        let entries: Vec<CustomRule> = if self.dir.join("custom_regex_rules.json").exists() {
            self.load("custom_regex_rules.json")?
        } else {
            Vec::new()
        };
        let mut names = std::collections::BTreeSet::new();
        for entry in &entries {
            entry.compile()?;
            if !names.insert(&entry.name) {
                return Err("规则名称不得重复".into());
            }
        }
        Ok(entries)
    }
    pub fn settings(&self) -> Result<Settings> {
        let mut defaults = Settings::default();
        if self.dir.join("settings.json").exists() {
            let settings: Settings = self.load("settings.json")?;
            settings.validate()?;
            defaults.entity_defaults.extend(settings.entity_defaults);
        }
        Ok(defaults)
    }
    /// Explicit import only: never silently replace user preferences.
    pub fn import_directory(&self, source: &Path) -> Result<()> {
        if !source.join("dictionary.json").is_file() || !source.join("settings.json").is_file() {
            return Err("请选择包含 dictionary.json 和 settings.json 的配置目录".into());
        }
        let source = Store { dir: source.into() };
        let dictionary = source.dictionary()?;
        let rules = source.rules()?;
        let settings = source.settings()?;
        self.save("dictionary.json", &dictionary)?;
        self.save("custom_regex_rules.json", &rules)?;
        self.save("settings.json", &settings)
    }
}
