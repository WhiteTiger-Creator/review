pub struct Version {
    pub core: (u64, u64, u64),
    pub pre: Vec<String>,
    pub raw: String,
}

pub fn parse(s: &str) -> Version {
    let (core_s, pre) = match s.split_once('-') {
        Some((c, p)) => (c, p.split('.').map(|x| x.to_string()).collect()),
        None => (s, Vec::new()),
    };
    let mut it = core_s.split('.');
    let a = it.next().unwrap_or("0").parse().unwrap_or(0);
    let b = it.next().unwrap_or("0").parse().unwrap_or(0);
    let c = it.next().unwrap_or("0").parse().unwrap_or(0);
    Version {
        core: (a, b, c),
        pre,
        raw: s.to_string(),
    }
}
