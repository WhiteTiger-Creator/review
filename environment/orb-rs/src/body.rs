use crate::wisp::arm_g;

pub const GRAV: f64 = 0.5;
pub const IMPULSE: f64 = -8.0;
pub const GRACE_MAX: i32 = 4;

#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct Sample {
    pub x: f64,
    pub y: f64,
    pub vx: f64,
    pub vy: f64,
    pub on: i32,
    pub grace: i32,
    pub stash: i32,
    pub hops: i32,
    pub apex: f64,
}

impl Sample {
    pub fn fresh(x: f64, y: f64) -> Self {
        Self {
            x,
            y,
            vx: 0.0,
            vy: 0.0,
            on: 1,
            grace: GRACE_MAX,
            stash: 0,
            hops: 0,
            apex: y,
        }
    }
}

pub fn drift(s: &mut Sample) {
    s.vy += GRAV;
    s.x += s.vx;
    s.y += s.vy;
    if s.y < s.apex {
        s.apex = s.y;
    }
}

pub fn arm_only(s: &mut Sample) {
    let on = s.on != 0;
    s.grace = arm_g(on, s.grace, GRACE_MAX);
}

pub fn kick(s: &mut Sample) {
    s.vy = IMPULSE;
    s.on = 0;
    s.grace = 0;
    s.hops += 1;
}
