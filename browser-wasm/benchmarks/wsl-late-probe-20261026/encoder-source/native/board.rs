//! ビットボード。bit = row * 8 + col（a1 = 0, h1 = 7, a8 = 56）。

pub const FILE_A: u64 = 0x0101_0101_0101_0101;
pub const FILE_H: u64 = 0x8080_8080_8080_8080;
pub const DIRS: [i32; 8] = [1, -1, 8, -8, 9, 7, -7, -9];

pub const CENTER: u64 = (1 << 27) | (1 << 28) | (1 << 35) | (1 << 36);
pub const INIT_BLACK: u64 = (1 << 28) | (1 << 35); // e4, d5
pub const INIT_WHITE: u64 = (1 << 27) | (1 << 36); // d4, e5

/// 盤外への回り込みを除いて 1 マスずらす。
#[inline(always)]
pub fn shift(b: u64, d: i32) -> u64 {
    match d {
        1 => (b << 1) & !FILE_A,
        -1 => (b >> 1) & !FILE_H,
        8 => b << 8,
        -8 => b >> 8,
        9 => (b << 9) & !FILE_A,
        7 => (b << 7) & !FILE_H,
        -7 => (b >> 7) & !FILE_A,
        -9 => (b >> 9) & !FILE_H,
        _ => unreachable!(),
    }
}

#[inline]
pub fn legal_moves(p: u64, o: u64) -> u64 {
    let empty = !(p | o);
    let mut moves = 0;
    for &d in &DIRS {
        let mut x = shift(p, d) & o;
        for _ in 0..5 {
            x |= shift(x, d) & o;
        }
        moves |= shift(x, d) & empty;
    }
    moves
}

#[inline]
pub fn flips(p: u64, o: u64, sq: u32) -> u64 {
    let m = 1u64 << sq;
    let mut f = 0;
    for &d in &DIRS {
        let mut line = 0;
        let mut x = shift(m, d);
        while x & o != 0 {
            line |= x;
            x = shift(x, d);
        }
        if x & p != 0 {
            f |= line;
        }
    }
    f
}

/// side: 0 = 黒, 1 = 白。着手後の (black, white) を返す。
#[inline]
pub fn play(black: u64, white: u64, side: u8, sq: u32) -> (u64, u64) {
    let (p, o) = if side == 0 { (black, white) } else { (white, black) };
    let f = flips(p, o, sq);
    let np = p | f | (1u64 << sq);
    let no = o & !f;
    if side == 0 {
        (np, no)
    } else {
        (no, np)
    }
}

pub fn sq_name(sq: u8) -> String {
    format!("{}{}", (b'a' + sq % 8) as char, sq / 8 + 1)
}

/// 8 行（1 行目 = a1..h1）。黒 X/x/B/b/*/●、白 O/o/W/w/○、空 -/./_。空白は無視。
pub fn parse(text: &str) -> Result<(u64, u64), String> {
    let mut black = 0u64;
    let mut white = 0u64;
    let mut i = 0u32;
    for ch in text.chars() {
        if ch.is_whitespace() {
            continue;
        }
        if i >= 64 {
            return Err("64 マスを超える入力です".into());
        }
        match ch {
            'X' | 'x' | 'B' | 'b' | '*' | '●' => black |= 1 << i,
            'O' | 'o' | 'W' | 'w' | '○' => white |= 1 << i,
            '-' | '.' | '_' => {}
            _ => return Err(format!("不明な文字 '{ch}'")),
        }
        i += 1;
    }
    if i != 64 {
        return Err(format!("マス数が {i} です（64 必要）"));
    }
    Ok((black, white))
}

pub fn format_board(black: u64, white: u64) -> String {
    let mut s = String::new();
    for row in 0..8 {
        for col in 0..8 {
            let m = 1u64 << (row * 8 + col);
            s.push(if black & m != 0 {
                'X'
            } else if white & m != 0 {
                'O'
            } else {
                '-'
            });
        }
        s.push('\n');
    }
    s
}
