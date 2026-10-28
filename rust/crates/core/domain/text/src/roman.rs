//! Số La Mã viết hoa, tương đương `frontend/roman.py`.

fn value(ch: char) -> Option<i32> {
    Some(match ch {
        'I' => 1,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        'C' => 100,
        'D' => 500,
        'M' => 1000,
        _ => return None,
    })
}

fn to_roman(mut number: i32) -> String {
    const TABLE: &[(i32, &str)] = &[
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ];
    let mut output = String::new();
    for (value, symbol) in TABLE {
        while number >= *value {
            output.push_str(symbol);
            number -= *value;
        }
    }
    output
}

pub fn roman_to_int(token: &str) -> Option<i32> {
    if token != token.to_uppercase() || !token.is_ascii() {
        return None;
    }
    let length = token.chars().count();
    if !(2..=15).contains(&length) {
        return None;
    }
    let mut total = 0;
    let mut previous = 0;
    for ch in token.chars().rev() {
        let current = value(ch)?;
        if current < previous {
            total -= current;
        } else {
            total += current;
            previous = current;
        }
    }
    if (1..=3999).contains(&total) && to_roman(total) == token {
        Some(total)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_roman() {
        assert_eq!(roman_to_int("VI"), Some(6));
        assert_eq!(roman_to_int("vi"), None);
        assert_eq!(roman_to_int("VX"), None);
        assert_eq!(roman_to_int("IIII"), None);
        assert_eq!(roman_to_int("MCMXCIV"), Some(1994));
    }
}
