pub fn line(sid: &str, qid: &str, result: &str) -> String {
    let mut s = String::with_capacity(sid.len() + qid.len() + result.len() + 2);
    s.push_str(sid);
    s.push('|');
    s.push_str(qid);
    s.push('|');
    s.push_str(result);
    s
}
