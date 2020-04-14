use rustc_hex::{FromHex, ToHex};

use serde_json::Value;
use std::fs::File;
use std::io::BufReader;

use secp256k1::{PublicKey, Signature};

use cryptoconditions::condition::*;
use cryptoconditions::decoding::*;

macro_rules! test_vectors {
    ($path:expr, $name: ident, $cond: expr) => {
        #[test]
        fn $name() {
            println!("tests/vectors/{}", $path);
            let file = File::open(format!("tests/vectors/{}", $path)).unwrap();
            let data = serde_json::from_reader(BufReader::new(file)).unwrap();
            let cond = $cond(&data);

            assert_eq!(
                cond.encode_condition().to_hex::<String>(),
                data["conditionBinary"]
                    .as_str()
                    .unwrap()
                    .to_ascii_lowercase()
            );
            assert_eq!(
                cond.encode_fulfillment().unwrap().to_hex::<String>(),
                data["fulfillment"]
                    .as_str()
                    .unwrap()
                    .to_ascii_lowercase()
            );

            assert_eq!(
                cond.encode_condition(), cond.to_anon().encode_condition());

            assert_eq!(
                Ok(cond), decode_fulfillment(&from_hex(data["fulfillment"].as_str().unwrap())));
        }
    };
}

fn from_hex(s: &str) -> Vec<u8> {
    s.from_hex().unwrap()
}

test_vectors!(
    "0000_test-minimal-preimage.json",
    test_0000_minimal_preimage,
    cond_0000
);
fn cond_0000(_val: &Value) -> Condition {
    Preimage { preimage: vec![] }
}
test_vectors!(
    "0002_test-minimal-threshold.json",
    test_0002_minimal_threshold,
    cond_0002
);
fn cond_0002(_val: &Value) -> Condition {
    Threshold {
        threshold: 1,
        subconditions: vec![Preimage { preimage: vec![] }],
    }
}
test_vectors!(
    "1000_test-minimal-eval.json",
    test_1000_minimal_eval,
    cond_1000
);
fn cond_1000(_val: &Value) -> Condition {
    Eval { code: "5445535401".from_hex().unwrap() }
}
test_vectors!(
    "1001_test-minimal-secp256k1.json",
    test_1001_minimal_secp256k1,
    cond_1001
);
fn cond_1001(val: &Value) -> Condition {
    Secp256k1 {
        pubkey: PublicKey::parse_slice(&from_hex(val["json"]["publicKey"].as_str().unwrap()), None)
            .unwrap(),
        signature: Some(
            Signature::parse_slice(&from_hex(val["json"]["signature"].as_str().unwrap())).unwrap(),
        ),
    }
}

#[test]
fn test_multi_threshold() {
    let cond = Threshold {
        threshold: 2,
        subconditions: vec![
            Preimage { preimage: vec![] },
            Eval { code: vec![] }
        ] };
    let ffill = cond.encode_fulfillment().unwrap();
    assert_eq!(cond, decode_fulfillment(&ffill).unwrap());
}
