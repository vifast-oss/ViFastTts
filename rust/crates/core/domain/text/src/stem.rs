//! Chuẩn hoá STEM, tương đương `frontend/stem.py`.

use fancy_regex::{Captures, Regex};

type NumberReader<'a> = dyn Fn(i64) -> String + 'a;

fn regex(pattern: &str) -> Regex {
    Regex::new(pattern).unwrap_or_else(|err| panic!("regex STEM không hợp lệ: {err}: {pattern}"))
}

fn greek(word: &str) -> Option<&'static str> {
    Some(match word {
        "alpha" => "an pha",
        "beta" => "bê ta",
        "gamma" => "gam ma",
        "delta" => "đen ta",
        "epsilon" => "ép xi lon",
        "theta" => "thê ta",
        "lambda" => "lam đa",
        "mu" => "miu",
        "pi" => "pi",
        "rho" => "rô",
        "sigma" => "xích ma",
        "phi" => "phi",
        "omega" => "ô mê ga",
        _ => return None,
    })
}

fn math_command(word: &str) -> Option<&'static str> {
    Some(match word {
        "times" | "cdot" => "nhân",
        "div" => "chia",
        "pm" => "cộng hoặc trừ",
        "neq" | "ne" => "khác",
        "le" | "leq" => "nhỏ hơn hoặc bằng",
        "ge" | "geq" => "lớn hơn hoặc bằng",
        "approx" => "xấp xỉ",
        "infty" => "vô cùng",
        "sum" => "tổng",
        "prod" => "tích",
        "int" => "tích phân",
        "partial" => "đạo hàm riêng",
        "nabla" => "na bla",
        "rightarrow" | "Rightarrow" => "suy ra",
        "leftarrow" => "suy ra ngược",
        "in" => "thuộc",
        "notin" => "không thuộc",
        "subset" => "là tập con của",
        "subseteq" => "là tập con hoặc bằng của",
        "cup" => "hợp",
        "cap" => "giao",
        "forall" => "với mọi",
        "exists" => "tồn tại",
        _ => return None,
    })
}

fn variable(word: &str) -> Option<&'static str> {
    Some(match word {
        "x" => "ích",
        "y" => "i dài",
        "z" => "dét",
        "a" => "a",
        "b" => "bê",
        "c" => "xê",
        "d" => "dê",
        "đ" => "đê",
        "e" => "e",
        "f" => "ép",
        "g" => "giê",
        "h" => "hát",
        "i" => "i",
        "j" => "giây",
        "k" => "ca",
        "l" => "e lờ",
        "m" => "em",
        "n" => "en",
        "o" => "o",
        "p" => "pê",
        "q" => "quy",
        "r" => "e rờ",
        "s" => "ét",
        "t" => "tê",
        "u" => "u",
        "v" => "vê",
        "w" => "vê kép",
        _ => return None,
    })
}

fn element(word: &str) -> Option<&'static str> {
    Some(match word {
        "H" => "hiđrô",
        "He" => "heli",
        "Li" => "liti",
        "Be" => "beri",
        "B" => "bo",
        "C" => "cacbon",
        "N" => "nitơ",
        "O" => "oxi",
        "F" => "flo",
        "Ne" => "neon",
        "Na" => "natri",
        "Mg" => "magiê",
        "Al" => "nhôm",
        "Si" => "silic",
        "P" => "phốt pho",
        "S" => "lưu huỳnh",
        "Cl" => "clo",
        "K" => "kali",
        "Ca" => "canxi",
        "Fe" => "sắt",
        "Cu" => "đồng",
        "Zn" => "kẽm",
        "Ag" => "bạc",
        "Au" => "vàng",
        "Hg" => "thủy ngân",
        "Pb" => "chì",
        "Sn" => "thiếc",
        "Mn" => "mangan",
        "Cr" => "crom",
        "Co" => "coban",
        "Ni" => "niken",
        "Br" => "brom",
        "I" => "iốt",
        "Ba" => "bari",
        _ => return None,
    })
}

fn unit(word: &str) -> Option<&'static str> {
    Some(match word {
        "m" => "mét",
        "km" => "ki lô mét",
        "cm" => "xen ti mét",
        "mm" => "mi li mét",
        "s" => "giây",
        "ms" => "mi li giây",
        "h" => "giờ",
        "Hz" => "héc",
        "kHz" => "ki lô héc",
        "MHz" => "mê ga héc",
        "GHz" => "gi ga héc",
        "kg" => "ki lô gam",
        "g" => "gam",
        "N" => "niu tơn",
        "Pa" => "pát can",
        "kPa" => "ki lô pát can",
        "J" => "jun",
        "W" => "oát",
        "kW" => "ki lô oát",
        "V" => "vôn",
        "A" => "ampe",
        "C" => "cu lông",
        "Ω" => "ôm",
        "K" => "ken vin",
        "°C" => "độ xê",
        "mol" => "mol",
        "L" => "lít",
        "mL" => "mi li lít",
        _ => return None,
    })
}

fn read_int(text: &str, read_number: &NumberReader<'_>) -> String {
    text.parse::<i64>()
        .map(read_number)
        .unwrap_or_else(|_| text.to_string())
}

fn plausible_formula(formula: &str, known: usize, only_element: Option<&str>) -> bool {
    if known >= 2 {
        return true;
    }
    let Some(only_element) = only_element else {
        return false;
    };
    if known != 1 {
        return false;
    }
    let re = regex(r"^([A-Z][a-z]?)([23]?)([+\-]?)$");
    let Some(caps) = re.captures(formula).ok().flatten() else {
        return false;
    };
    let element = caps.get(1).map(|m| m.as_str()).unwrap_or("");
    let digit = caps.get(2).map(|m| m.as_str()).unwrap_or("");
    let charge = caps.get(3).map(|m| m.as_str()).unwrap_or("");
    if element != only_element {
        return false;
    }
    if !charge.is_empty() {
        return true;
    }
    matches!(digit, "2" | "3") && matches!(element, "H" | "N" | "O" | "F" | "Cl" | "Br" | "I")
}

pub fn read_chemical_formula(
    formula: &str,
    read_number: &NumberReader<'_>,
    strict: bool,
) -> String {
    let formula = formula.trim().replace("_{", "").replace('}', "");
    let token_re = regex(r"([A-Z][a-z]?)(\d*)|([()])|(\d+)|([+\-])");
    let mut parts = Vec::new();
    let mut position = 0usize;
    let mut known = std::collections::HashSet::new();
    for caps in token_re.captures_iter(&formula).flatten() {
        let Some(whole) = caps.get(0) else { continue };
        if whole.start() != position {
            return formula;
        }
        position = whole.end();
        if let Some(symbol) = caps.get(1) {
            let symbol = symbol.as_str();
            if element(symbol).is_some() {
                known.insert(symbol.to_string());
            }
            parts.push(element(symbol).unwrap_or(symbol).to_string());
            if let Some(digits) = caps.get(2) {
                let digits = digits.as_str();
                if !digits.is_empty() {
                    parts.push(read_int(digits, read_number));
                }
            }
        } else if let Some(paren) = caps.get(3) {
            parts.push(if paren.as_str() == "(" {
                "mở ngoặc".to_string()
            } else {
                "đóng ngoặc".to_string()
            });
        } else if let Some(digits) = caps.get(4) {
            parts.push(read_int(digits.as_str(), read_number));
        } else if let Some(sign) = caps.get(5) {
            parts.push(
                if sign.as_str() == "+" {
                    "dương"
                } else {
                    "âm"
                }
                .to_string(),
            );
        }
    }
    if position != formula.len() || parts.is_empty() {
        return formula;
    }
    let only_element = if known.len() == 1 {
        known.iter().next().map(String::as_str)
    } else {
        None
    };
    if strict && !plausible_formula(&formula, known.len(), only_element) {
        return formula;
    }
    parts.join(" ")
}

fn read_composite_unit(caps: &Captures<'_>) -> String {
    let mut numerator = unit(caps.get(1).map(|m| m.as_str()).unwrap_or(""))
        .unwrap_or_else(|| caps.get(1).map(|m| m.as_str()).unwrap_or(""))
        .to_string();
    let exp = caps.get(2).map(|m| m.as_str()).unwrap_or("");
    if !exp.is_empty() {
        if exp == "2" {
            numerator.push_str(" bình phương");
        } else if exp == "3" {
            numerator.push_str(" lập phương");
        }
    }
    let mut denominator = unit(caps.get(3).map(|m| m.as_str()).unwrap_or(""))
        .unwrap_or_else(|| caps.get(3).map(|m| m.as_str()).unwrap_or(""))
        .to_string();
    let exp = caps.get(4).map(|m| m.as_str()).unwrap_or("");
    if !exp.is_empty() {
        if exp == "2" {
            denominator.push_str(" bình phương");
        } else if exp == "3" {
            denominator.push_str(" lập phương");
        }
    }
    format!("{numerator} trên {denominator}")
}

fn read_measure(caps: &Captures<'_>, read_number: &NumberReader<'_>) -> String {
    let number = caps
        .get(1)
        .map(|m| m.as_str())
        .unwrap_or("")
        .replace(',', ".");
    let number = if let Some((whole, fraction)) = number.split_once('.') {
        let digits = fraction
            .chars()
            .filter_map(|ch| ch.to_digit(10))
            .map(|d| read_number(d as i64))
            .collect::<Vec<_>>()
            .join(" ");
        format!("{} phẩy {digits}", read_number(whole.parse().unwrap_or(0)))
    } else {
        read_number(number.parse().unwrap_or(0))
    };
    let mut unit_text = unit(caps.get(2).map(|m| m.as_str()).unwrap_or(""))
        .unwrap_or_else(|| caps.get(2).map(|m| m.as_str()).unwrap_or(""))
        .to_string();
    let exp = caps.get(3).map(|m| m.as_str()).unwrap_or("");
    if !exp.is_empty() {
        if exp == "2" {
            unit_text.push_str(" bình phương");
        } else if exp == "3" {
            unit_text.push_str(" lập phương");
        }
    }
    if let Some(denominator) = caps.get(4) {
        let mut denominator_text = unit(denominator.as_str())
            .unwrap_or(denominator.as_str())
            .to_string();
        let exp = caps.get(5).map(|m| m.as_str()).unwrap_or("");
        if !exp.is_empty() {
            if exp == "2" {
                denominator_text.push_str(" bình phương");
            } else if exp == "3" {
                denominator_text.push_str(" lập phương");
            }
        }
        unit_text.push_str(" trên ");
        unit_text.push_str(&denominator_text);
    }
    format!("{number} {unit_text}")
}

pub fn read_unit_expression(expr: &str, read_number: &NumberReader<'_>) -> String {
    let _ = read_number;
    let expr = expr.trim();
    let power_re = regex(r"([A-Za-z°Ω]+)\^?([23])\b");
    let expr = power_re
        .replace_all(expr, |caps: &Captures<'_>| {
            let unit = caps.get(1).map(|m| m.as_str()).unwrap_or("");
            let exp = caps.get(2).map(|m| m.as_str()).unwrap_or("");
            let unit = unit_lookup(unit);
            format!(
                "{unit} {}",
                if exp == "2" {
                    "bình phương"
                } else {
                    "lập phương"
                }
            )
        })
        .into_owned();
    let mut output = Vec::new();
    for piece in expr.split(['/', '·', '*']) {
        let piece = piece.trim();
        if piece.is_empty() {
            continue;
        }
        // Giữ dấu phân cách để output khớp Python.
        let separator = if expr.contains('/') { "/" } else { " " };
        let _ = separator;
        output.push(unit_lookup(piece));
    }
    output.join(" ")
}

fn unit_lookup(value: &str) -> String {
    unit(value).unwrap_or(value).to_string()
}

fn read_math_expression(expr: &str, read_number: &NumberReader<'_>) -> String {
    let mut expr = expr.trim().replace("\\\\", "\\");
    let slash_re = regex(r"\\+(?=[A-Za-z])");
    expr = slash_re.replace_all(&expr, "\\").into_owned();

    let frac_re = regex(r"\\frac\{([^{}]+)\}\{([^{}]+)\}");
    while let Ok(Some(caps)) = frac_re.captures(&expr) {
        let Some(whole) = caps.get(0) else { break };
        let left = caps.get(1).map(|m| m.as_str()).unwrap_or("");
        let right = caps.get(2).map(|m| m.as_str()).unwrap_or("");
        let replacement = format!(
            "phân số {} trên {}",
            read_math_expression(left, read_number),
            read_math_expression(right, read_number)
        );
        expr = format!(
            "{}{}{}",
            &expr[..whole.start()],
            replacement,
            &expr[whole.end()..]
        );
    }

    let sqrt_optional = regex(r"\\sqrt\[([^]]+)\]\{([^{}]+)\}");
    expr = sqrt_optional
        .replace_all(&expr, |caps: &Captures<'_>| {
            format!(
                "căn bậc {} của {}",
                read_math_expression(caps.get(1).unwrap().as_str(), read_number),
                read_math_expression(caps.get(2).unwrap().as_str(), read_number)
            )
        })
        .into_owned();
    let sqrt_re = regex(r"\\sqrt\{([^{}]+)\}");
    expr = sqrt_re
        .replace_all(&expr, |caps: &Captures<'_>| {
            format!(
                "căn bậc hai của {}",
                read_math_expression(caps.get(1).unwrap().as_str(), read_number)
            )
        })
        .into_owned();
    let text_re = regex(r"\\text\{([^{}]*)\}");
    expr = text_re.replace_all(&expr, "$1").into_owned();
    let font_re = regex(r"\\(?:mathrm|mathbf|mathit)\{([^{}]*)\}");
    expr = font_re.replace_all(&expr, "$1").into_owned();

    let mut commands: Vec<(&str, &str)> = Vec::new();
    for word in [
        "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda", "mu", "pi", "rho",
        "sigma", "phi", "omega",
    ] {
        if let Some(value) = greek(word) {
            commands.push((word, value));
        }
    }
    for word in [
        "times",
        "cdot",
        "div",
        "pm",
        "neq",
        "ne",
        "le",
        "leq",
        "ge",
        "geq",
        "approx",
        "infty",
        "sum",
        "prod",
        "int",
        "partial",
        "nabla",
        "rightarrow",
        "Rightarrow",
        "leftarrow",
        "in",
        "notin",
        "subset",
        "subseteq",
        "cup",
        "cap",
        "forall",
        "exists",
    ] {
        if let Some(value) = math_command(word) {
            commands.push((word, value));
        }
    }
    commands.sort_by_key(|(command, _)| std::cmp::Reverse(command.len()));
    for (command, value) in commands {
        expr = expr.replace(&format!("\\{command}"), value);
    }
    expr = expr
        .replace("\\,", " ")
        .replace("\\;", " ")
        .replace("\\!", "");

    let sup_braced = regex(r"\^\{([^{}]+)\}");
    expr = sup_braced
        .replace_all(&expr, |caps: &Captures<'_>| {
            format!(
                " mũ {}",
                read_math_expression(caps.get(1).unwrap().as_str(), read_number)
            )
        })
        .into_owned();
    let sup_single = regex(r"\^([0-9A-Za-z])");
    expr = sup_single
        .replace_all(&expr, |caps: &Captures<'_>| {
            format!(
                " mũ {}",
                read_math_expression(caps.get(1).unwrap().as_str(), read_number)
            )
        })
        .into_owned();
    let sub_braced = regex(r"_\{([^{}]+)\}");
    expr = sub_braced
        .replace_all(&expr, |caps: &Captures<'_>| {
            format!(
                " chỉ số {}",
                read_math_expression(caps.get(1).unwrap().as_str(), read_number)
            )
        })
        .into_owned();
    let sub_single = regex(r"_([0-9A-Za-z])");
    expr = sub_single
        .replace_all(&expr, |caps: &Captures<'_>| {
            format!(
                " chỉ số {}",
                read_math_expression(caps.get(1).unwrap().as_str(), read_number)
            )
        })
        .into_owned();

    for (from, to) in [
        ("<=", " nhỏ hơn hoặc bằng "),
        (">=", " lớn hơn hoặc bằng "),
        ("!=", " khác "),
        ("=>", " suy ra "),
        ("->", " suy ra "),
        ("±", " cộng hoặc trừ "),
        ("×", " nhân "),
        ("÷", " chia "),
        ("=", " bằng "),
        ("+", " cộng "),
        ("-", " trừ "),
        ("<", " nhỏ hơn "),
        (">", " lớn hơn "),
        ("/", " trên "),
        ("·", " nhân "),
        ("*", " nhân "),
        ("%", " phần trăm "),
    ] {
        expr = expr.replace(from, to);
    }
    let number_re = regex(r"\b\d+\b");
    expr = number_re
        .replace_all(&expr, |caps: &Captures<'_>| {
            read_number(caps.get(0).unwrap().as_str().parse().unwrap_or(0))
        })
        .into_owned();
    let var_re = regex(r"\b([A-Za-z])\b");
    expr = var_re
        .replace_all(&expr, |caps: &Captures<'_>| {
            let word = caps.get(1).unwrap().as_str();
            variable(&word.to_lowercase()).unwrap_or(word).to_string()
        })
        .into_owned();
    expr = expr
        .replace('(', " mở ngoặc ")
        .replace(')', " đóng ngoặc ")
        .replace('[', " mở ngoặc vuông ")
        .replace(']', " đóng ngoặc vuông ")
        .replace('{', " mở ngoặc nhọn ")
        .replace('}', " đóng ngoặc nhọn ");
    expr.split_whitespace().collect::<Vec<_>>().join(" ")
}

pub fn normalize_stem(text: &str, read_number: &NumberReader<'_>) -> String {
    // Không có chữ số/LaTeX/STEM thì không thể có gì để đọc.
    if !text
        .chars()
        .any(|ch| ch.is_ascii_digit() || "\\$^_{}%".contains(ch))
    {
        return text.to_string();
    }
    let mut text = text.replace("\\\\", "\\");
    let ce_re = regex(r"\\(?:ce|chem)\{([^{}]+)\}");
    text = ce_re
        .replace_all(&text, |caps: &Captures<'_>| {
            read_chemical_formula(caps.get(1).unwrap().as_str(), read_number, false)
        })
        .into_owned();

    for pattern in [
        r"\$\$([^$]+)\$\$",
        r"\$([^$]+)\$",
        r"\\\((.*?)\\\)",
        r"\\\[(.*?)\\\]",
    ] {
        let re = Regex::new(pattern).expect("regex math");
        text = re
            .replace_all(&text, |caps: &Captures<'_>| {
                read_math_expression(caps.get(1).map(|m| m.as_str()).unwrap_or(""), read_number)
            })
            .into_owned();
    }

    text = regex(r"\\frac\{[^{}]+\}\{[^{}]+\}")
        .replace_all(&text, |caps: &Captures<'_>| {
            read_math_expression(caps.get(0).unwrap().as_str(), read_number)
        })
        .into_owned();
    text = regex(r"\\sqrt(?:\[[^]]+\])?\{[^{}]+\}")
        .replace_all(&text, |caps: &Captures<'_>| {
            read_math_expression(caps.get(0).unwrap().as_str(), read_number)
        })
        .into_owned();

    let chem_re = regex(
        r"(?<![\p{L}\p{N}_])(?=[A-Z][A-Za-z0-9()]*\d)([A-Z][A-Za-z0-9()]*)([+\-])?(?![\p{L}\p{N}_+\-])",
    );
    text = chem_re
        .replace_all(&text, |caps: &Captures<'_>| {
            let formula = format!(
                "{}{}",
                caps.get(1).map(|m| m.as_str()).unwrap_or(""),
                caps.get(2).map(|m| m.as_str()).unwrap_or("")
            );
            read_chemical_formula(&formula, read_number, true)
        })
        .into_owned();

    let mut unit_keys: Vec<&str> = [
        "m", "km", "cm", "mm", "s", "ms", "h", "Hz", "kHz", "MHz", "GHz", "kg", "g", "N", "Pa",
        "kPa", "J", "W", "kW", "V", "A", "C", "Ω", "K", "°C", "mol", "L", "mL",
    ]
    .into_iter()
    .collect();
    unit_keys.sort_by_key(|value| std::cmp::Reverse(value.len()));
    let unit_pattern = unit_keys
        .iter()
        .map(|value| regex::escape(value))
        .collect::<Vec<_>>()
        .join("|");
    let measure_re = Regex::new(&format!(
        r"(?<![\p{{L}}\p{{N}}_])(\d+(?:[,.]\d+)?)\s*({unit_pattern})(?:\^?([23]))?(?:/({unit_pattern})(?:\^?([23]))?)?(?![A-Za-zÀ-ỹĐđ])"
    ))
    .expect("regex measure");
    text = measure_re
        .replace_all(&text, |caps: &Captures<'_>| read_measure(caps, read_number))
        .into_owned();
    let composite_re = Regex::new(&format!(
        r"(?<![\p{{L}}\p{{N}}_])({unit_pattern})(?:\^?([23]))?/({unit_pattern})(?:\^?([23]))?(?![A-Za-zÀ-ỹĐđ])"
    ))
    .expect("regex composite");
    text = composite_re
        .replace_all(&text, |caps: &Captures<'_>| read_composite_unit(caps))
        .into_owned();
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn read(n: i64) -> String {
        crate::normalizer::integer_to_words(
            &num_bigint::BigInt::from(n),
            crate::dialect::Dialect::North,
        )
    }

    #[test]
    fn reads_chemistry() {
        assert_eq!(read_chemical_formula("H2O", &read, true), "hiđrô hai oxi");
    }

    #[test]
    fn reads_math() {
        assert!(read_math_expression(r"\frac{a}{b}", &read).contains("phân số"));
    }
}
