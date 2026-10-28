//! Port lưu cấu hình; adapter nền tảng cung cấp storage thật.

pub trait SettingsStore {
    fn get(&self, key: &str) -> Option<String>;
    fn set(&mut self, key: &str, value: &str) -> Result<(), String>;
    fn remove(&mut self, key: &str) -> Result<(), String>;
}
