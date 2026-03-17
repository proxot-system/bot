use csscolorparser;
use std::env;
fn main() {
    env::args().skip(1).for_each(|arg| {
        let parsed = csscolorparser::parse(&arg);
        if let Err(err) = parsed {
            eprintln!("Error: {}", err);
            return;
        }
        println!("{:?}", parsed.unwrap().to_rgba8());
    });
}
