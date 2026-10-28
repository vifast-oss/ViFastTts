//! Phương ngữ đọc số, tương đương `frontend/dialect.py`.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Dialect {
    North,
    Central,
    South,
}

impl Dialect {
    pub fn from_name(value: &str) -> Result<Self, String> {
        match value {
            "north" => Ok(Dialect::North),
            "central" => Ok(Dialect::Central),
            "south" => Ok(Dialect::South),
            _ => Err("dialect phải là north, central hoặc south".to_string()),
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct ReadingProfile {
    pub thousand: &'static str,
    pub zero_tens: &'static str,
    pub four_after_tens: &'static str,
}

pub fn get_profile(dialect: Dialect) -> ReadingProfile {
    match dialect {
        Dialect::North => ReadingProfile {
            thousand: "nghìn",
            zero_tens: "linh",
            four_after_tens: "tư",
        },
        Dialect::Central => ReadingProfile {
            thousand: "ngàn",
            zero_tens: "lẻ",
            four_after_tens: "tư",
        },
        Dialect::South => ReadingProfile {
            thousand: "ngàn",
            zero_tens: "lẻ",
            four_after_tens: "bốn",
        },
    }
}
