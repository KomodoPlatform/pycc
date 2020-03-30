use rustc_hex::{FromHex, ToHex};

use num_bigint::{BigInt, BigUint};
use num_traits::cast::FromPrimitive;
use secp256k1::{PublicKey, Signature};
use sha2::{Digest, Sha256};
use simple_asn1::{to_der, ASN1Block, ASN1Class};
use std::collections::HashSet;

enum Condition {
    Threshold {
        threshold: u16,
        subconditions: Vec<Condition>,
    },
    Preimage {
        preimage: Vec<u8>,
    },
    Secp256k1 {
        pubkey: PublicKey,
        signature: Option<Signature>,
    },
    Eval {
        code: Vec<u8>,
    },
}

use Condition::*;

impl Condition {
    fn type_id(&self) -> u8 {
        match self {
            Preimage { .. } => 0,
            Threshold { .. } => 2,
            Secp256k1 { .. } => 5,
            Eval { .. } => 15,
        }
    }

    fn encode_condition_asn(&self) -> ASN1Block {
        let fingerprint = self.fingerprint();
        let cost = BigInt::from_u64(self.cost()).unwrap().to_signed_bytes_be();
        let mut parts = vec![fingerprint, cost];
        if self.has_subtypes() {
            parts.push(pack_set(self.get_subtypes()));
        }
        asn_choice(self.type_id(), &asn_data(&parts))
    }

    fn encode_condition(&self) -> Vec<u8> {
        encode_asn(&self.encode_condition_asn())
    }

    fn fingerprint(&self) -> Vec<u8> {
        match self {
            Secp256k1 { pubkey, .. } => hash_asn(&asn_sequence(asn_data(&vec![pubkey
                .serialize_compressed()
                .to_vec()]))),
            Eval { code } => hash_asn(&asn_sequence(asn_data(&vec![code.to_vec()]))),
            Preimage { preimage } => sha256(preimage.to_vec()),
            Threshold {
                threshold,
                subconditions,
            } => {
                let mut asns = subconditions
                    .iter()
                    .map(|c| c.encode_condition_asn())
                    .collect();
                x690sort(&mut asns);

                let t = BigInt::from_u16(*threshold).unwrap().to_signed_bytes_be();
                let mut elems = asn_data(&vec![t]);
                elems.push(asn_choice(1, &asns));
                hash_asn(&asn_sequence(elems))
            }
            _ => unimplemented!("fingerprint"),
        }
    }

    fn cost(&self) -> u64 {
        match self {
            Preimage { preimage } => preimage.len() as u64,
            Secp256k1 { .. } => 131072,
            Eval { .. } => 1048576,
            Threshold {
                threshold,
                subconditions,
            } => {
                let mut costs: Vec<u64> = subconditions.iter().map(|c| c.cost()).collect();
                costs.sort();
                costs.reverse();
                let expensive: u64 = costs[..*threshold as usize].iter().sum();
                expensive + 1024 * (subconditions.len() as u64)
            }
        }
    }

    fn has_subtypes(&self) -> bool {
        match self {
            Threshold { .. } => true,
            _ => false,
        }
    }

    fn get_subtypes(&self) -> HashSet<u8> {
        match self {
            Threshold { subconditions, .. } => {
                let mut set = HashSet::new();
                for cond in subconditions {
                    set.insert(cond.type_id());
                    for x in cond.get_subtypes() {
                        set.insert(x);
                    }
                }
                set.remove(&self.type_id());
                set
            }
            _ => HashSet::new(),
        }
    }

    fn encode_fulfillment_asn(&self) -> R {
        match self {
            Preimage { preimage } => Ok(asn_choice(self.type_id(), &asn_data(&vec![preimage.to_vec()]))),
            Secp256k1 {
                pubkey,
                signature: Some(signature),
            } => {
                let body = vec![
                    pubkey.serialize_compressed().to_vec(),
                    signature.serialize().to_vec(),
                ];
                Ok(asn_choice(self.type_id(), &asn_data(&body)))
            }
            Eval { code } => Ok(asn_choice(self.type_id(), &asn_data(&vec![code.to_vec()]))),
            Threshold {
                threshold,
                subconditions,
            } => threshold_fulfillment_asn(*threshold, subconditions),
            _ => return Err("Cannot encode fulfillment".into()),
        }
    }

    fn encode_fulfillment(&self) -> Result<Vec<u8>, String> {
        Ok(encode_asn(&self.encode_fulfillment_asn()?))
    }
}

type R = Result<ASN1Block, String>;

fn threshold_fulfillment_asn(threshold: u16, subconditions: &Vec<Condition>) -> R {
    fn key_cost((c, opt_asn): &(&Condition, R)) -> (u8, u64) {
        match opt_asn {
            Ok(_) => (0, c.cost()),
            _ => (1, 0),
        }
    };
    let mut subs: Vec<(&Condition, R)> = subconditions
        .iter()
        .map(|c| (c, c.encode_fulfillment_asn()))
        .collect();
    subs.sort_by(|a, b| key_cost(a).cmp(&key_cost(b)));

    let tt = threshold as usize;
    println!("\n\n\n\n\n{:?} - {:?}\n", subs.len(), subs[tt - 1].1.is_ok());
    if subs.len() >= tt && subs[tt - 1].1.is_ok() {
        Ok(asn_choice(
            2,
            &vec![
                asn_choice(
                    0,
                    &subs
                        .iter()
                        .take(tt)
                        .map(|t| t.1.as_ref().unwrap().clone())
                        .collect(),
                ),
                asn_choice(
                    1,
                    &subs
                        .iter()
                        .skip(tt)
                        .map(|t| t.0.encode_condition_asn())
                        .collect(),
                ),
            ],
        ))
    } else {
        Err("Threshold is unfulfilled".into())
    }
}

fn x690sort(asns: &mut Vec<ASN1Block>) {
    asns.sort_by(|a, b| {
        let va = encode_asn(a);
        let vb = encode_asn(b);
        va.len().cmp(&vb.len()).then_with(|| va.cmp(&vb))
    })
}

fn sha256(buf: Vec<u8>) -> Vec<u8> {
    let mut hasher = sha2::Sha256::new();
    hasher.input(buf);
    (*hasher.result()).to_vec()
}

fn hash_asn(asn: &ASN1Block) -> Vec<u8> {
    sha256(encode_asn(asn))
}

fn asns_to_vec(asns: &Vec<ASN1Block>) -> Vec<u8> {
    let mut body = Vec::new();
    for child in asns {
        body.append(&mut encode_asn(child));
    }
    body
}

fn asn_choice(type_id: u8, children: &Vec<ASN1Block>) -> ASN1Block {
    ASN1Block::Unknown(
        ASN1Class::ContextSpecific,
        true,
        0,
        BigUint::from_u8(type_id).unwrap(),
        asns_to_vec(children),
    )
}

fn encode_asn(asn: &ASN1Block) -> Vec<u8> {
    to_der(asn).expect("ASN encoding broke")
}

fn asn_data(vecs: &Vec<Vec<u8>>) -> Vec<ASN1Block> {
    vecs.iter()
        .enumerate()
        .map(|(i, v)| {
            ASN1Block::Unknown(
                ASN1Class::ContextSpecific,
                false,
                0,
                BigUint::from_usize(i).unwrap(),
                v.to_vec(),
            )
        })
        .collect()
}

fn asn_sequence(children: Vec<ASN1Block>) -> ASN1Block {
    ASN1Block::Sequence(0, children)
}

fn pack_set(items: HashSet<u8>) -> Vec<u8> {
    // XXX: This will probably break if there are any type IDs > 31
    let mut buf = vec![0, 0, 0, 0];
    let mut max_id = 0;
    for i in items {
        max_id = std::cmp::max(i, max_id);
        buf[i as usize >> 3] |= 1 << (7 - i % 8);
    }
    buf.truncate(1 + (max_id >> 3) as usize);
    buf.insert(0, 7 - max_id % 8);
    buf
}

#[cfg(test)]
mod tests {
    use super::*;

    fn from_hex(s: &str) -> Vec<u8> {
        s.from_hex::<Vec<u8>>().expect("invalid hex")
    }

    #[test]
    fn test_secp256k1() {
        let pubkey: PublicKey = PublicKey::parse_slice(
            &from_hex("02D5D969305535AC29A77079C11D4F0DD40661CF96E04E974A5E8D7E374EE225AA"),
            None,
        )
        .expect("failed parsing public key");

        let signature: Signature = Signature::parse_slice(
            &from_hex("9C2D6FF39F340BBAF65E884BDFFAE7436A7B7568839C5BA117FA6818245FB9DA3CDEC7CFD4D3DF7191BDB22638FD86F3D9A3B8CB257FCF9B54D0931C4D0195D3"
            )).expect("failed parsing signature");

        let cond = Condition::Secp256k1 {
            pubkey,
            signature: Some(signature),
        };

        assert_eq!(
            cond.fingerprint().to_hex::<String>(),
            "9c2850f5147e9903dd317c650ac1d6e80e695280789887f2e3179e5c65c9df3a"
        );
        assert_eq!(cond.cost(), 131072);
        assert_eq!(
            cond.encode_condition().to_hex::<String>(),
            "a52780209c2850f5147e9903dd317c650ac1d6e80e695280789887f2e3179e5c65c9df3a8103020000"
        );
        assert_eq!(
            cond.encode_fulfillment().unwrap().to_hex::<String>(),
            "a565802102d5d969305535ac29a77079c11d4f0dd40661cf96e04e974a5e8d7e374ee225aa81409c2d6ff39f340bbaf65e884bdffae7436a7b7568839c5ba117fa6818245fb9da3cdec7cfd4d3df7191bdb22638fd86f3d9a3b8cb257fcf9b54d0931c4d0195d3"
        );
    }

    #[test]
    fn test_pack_cost() {
        let cost = BigInt::from_u32(1010101010).unwrap();
        let asn = ASN1Block::Unknown(
            ASN1Class::ContextSpecific,
            false,
            0,
            BigUint::from_u8(0).unwrap(),
            cost.to_signed_bytes_be(),
        );
        let encoded = encode_asn(&asn);
        assert_eq!(encoded.to_hex::<String>(), "80043c34eb12");
    }

    #[test]
    fn test_pack_bit_array() {
        assert_eq!(
            pack_set(vec![1, 2, 3].into_iter().collect()).to_hex::<String>(),
            "0470"
        );
        assert_eq!(
            pack_set(vec![1, 2, 3, 4, 5, 6, 7, 8, 9].into_iter().collect()).to_hex::<String>(),
            "067fc0"
        );
        assert_eq!(
            pack_set(vec![15].into_iter().collect()).to_hex::<String>(),
            "000001"
        );
    }

    #[test]
    fn test_threshold() {
        let cond = Threshold {
            threshold: 1,
            subconditions: vec![Preimage { preimage: vec![] }],
        };

        assert_eq!(
            cond.fingerprint().to_hex::<String>(),
            sha256(from_hex("302c800101a127a0258020e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855810100")).to_hex::<String>()
        );
        assert_eq!(cond.cost(), 1024);
        assert_eq!(
            cond.encode_condition().to_hex::<String>(),
            "a22a8020b4b84136df48a71d73f4985c04c6767a778ecb65ba7023b4506823beee7631b98102040082020780"
        );
        assert_eq!(
            cond.encode_fulfillment().unwrap().to_hex::<String>(),
            "a208a004a0028000a100"
        );
    }
}
