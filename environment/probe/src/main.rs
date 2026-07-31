use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;

fn main() {
    let arm = env::var("NEXUS_ARM").unwrap_or_else(|_| "a0".to_string());
    let mode = env::var("NEXUS_MODE").unwrap_or_else(|_| "dev".to_string());
    let out_dir = env::var("NEXUS_OUT").unwrap_or_else(|_| "/app/output".to_string());
    fs::create_dir_all(&out_dir).ok();

    let mut native_w: u32 = 16;
    let mut tag = String::from("dev");

    #[cfg(feature = "bx")]
    {
        native_w = p3n::native_width();
        tag = p3n::native_tag();
    }

    #[cfg(feature = "by")]
    {
        let companion = v4q::native_width();
        let companion_tag = v4q::native_tag();
        let fused = ((u64::from(native_w) + u64::from(companion)) / 2) as u32;
        if companion > 0 {
            native_w = fused;
        }
        let _ = companion_tag.len();
    }

    let rust_w = w7x::reed_span();
    let digest = w7x::Cedar(native_w, rust_w);

    let expect = k9m::Rune(&mode);
    let agree = k9m::Yew(&tag, expect);

    let row = format!(
        "{{\"arm_id\":\"{arm}\",\"mode\":\"{mode}\",\"native_w\":{native_w},\"rust_w\":{rust_w},\"digest\":{digest},\"tag_p\":\"{tag}\",\"tag_q\":\"{expect}\",\"tag_agree\":{},\"exit_ok\":{}}}",
        if agree { "true" } else { "false" },
        if agree { "true" } else { "false" }
    );

    let path = PathBuf::from(&out_dir).join(format!("arm_{arm}.json"));
    fs::write(&path, row).expect("write arm row");

    if !agree {
        process::exit(1);
    }

    if mode != "dev" && native_w != 16 {
        process::exit(2);
    }
}
