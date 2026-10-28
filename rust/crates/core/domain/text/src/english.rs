//! Bảng fallback tiếng Anh/viết tắt, dữ liệu sinh từ Python.

use std::collections::HashMap;
use std::sync::OnceLock;

fn load_map(source: &str) -> HashMap<String, String> {
    serde_json::from_str(source).expect("bảng JSON frontend không hợp lệ")
}

pub fn acronyms() -> &'static HashMap<String, String> {
    static CACHE: OnceLock<HashMap<String, String>> = OnceLock::new();
    CACHE.get_or_init(|| load_map(include_str!("../resources/acronyms.json")))
}

pub fn english() -> &'static HashMap<String, String> {
    static CACHE: OnceLock<HashMap<String, String>> = OnceLock::new();
    CACHE.get_or_init(|| load_map(include_str!("../resources/english.json")))
}

pub fn products() -> &'static HashMap<String, String> {
    static CACHE: OnceLock<HashMap<String, String>> = OnceLock::new();
    CACHE.get_or_init(|| load_map(include_str!("../resources/products.json")))
}

pub fn lookup_exact_acronym(token: &str) -> Option<String> {
    acronyms().get(token).cloned()
}

pub fn lookup_product_name(token: &str) -> Option<String> {
    products().get(token).cloned()
}

pub fn lookup_case_insensitive_english(token: &str) -> Option<String> {
    english().get(&token.to_lowercase()).cloned()
}
