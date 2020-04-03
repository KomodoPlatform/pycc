use num_bigint::{BigInt, BigUint};
use num_traits::cast::FromPrimitive;
use secp256k1::{PublicKey, Signature};
use simple_asn1::{to_der, ASN1Block, ASN1Class};
use std::collections::HashSet;

pub use Condition::*;

#[derive(PartialEq, Debug)]
pub enum Condition {
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
    Anon {
        type_id: u8,
        fingerprint: Vec<u8>,
        cost: u64,
        subtypes: HashSet<u8>,
    },
}

const PREIMAGE_TYPE_ID: u8 = 0;
const THRESHOLD_TYPE_ID: u8 = 2;
const SECP256K1_TYPE_ID: u8 = 5;
const EVAL_TYPE_ID: u8 = 15;

impl Condition {
    pub fn type_id(&self) -> u8 {
        match self {
            Preimage { .. } => PREIMAGE_TYPE_ID,
            Threshold { .. } => THRESHOLD_TYPE_ID,
            Secp256k1 { .. } => SECP256K1_TYPE_ID,
            Eval { .. } => EVAL_TYPE_ID,
            Anon { type_id, .. } => *type_id,
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

    pub fn encode_condition(&self) -> Vec<u8> {
        encode_asn(&self.encode_condition_asn())
    }

    pub fn fingerprint(&self) -> Vec<u8> {
        match self {
            Secp256k1 { pubkey, .. } => {
                let data = asn_data(&vec![pubkey.serialize_compressed().to_vec()]);
                hash_asn(&ASN1Block::Sequence(0, data))
            }
            Eval { code } => sha256(code.to_vec()),
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
                hash_asn(&ASN1Block::Sequence(0, elems))
            }
            Anon { fingerprint, .. } => fingerprint.clone(),
        }
    }

    pub fn cost(&self) -> u64 {
        match self {
            Preimage { preimage } => preimage.len() as u64,
            Secp256k1 { .. } => 131072,
            Eval { .. } => 1048576,
            Anon { cost, .. } => *cost,
            Threshold {
                threshold,
                subconditions,
            } => {
                let mut costs: Vec<u64> = subconditions.iter().map(|c| c.cost()).collect();
                costs.sort();
                costs.reverse();
                let expensive: u64 = costs.iter().take(*threshold as usize).sum();
                expensive + 1024 * subconditions.len() as u64
            }
        }
    }

    fn has_subtypes(&self) -> bool {
        return type_id_has_subtypes(self.type_id());
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
            Preimage { preimage } => Ok(asn_choice(
                self.type_id(),
                &asn_data(&vec![preimage.to_vec()]),
            )),
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

    pub fn encode_fulfillment(&self) -> Result<Vec<u8>, String> {
        Ok(encode_asn(&self.encode_fulfillment_asn()?))
    }
}

pub fn type_id_has_subtypes(tid: u8) -> bool {
    tid == 2
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

pub mod internal {
    use super::*;
    use sha2::Digest;
    pub fn sha256(buf: Vec<u8>) -> Vec<u8> {
        let mut hasher = sha2::Sha256::new();
        hasher.input(buf);
        (*hasher.result()).to_vec()
    }

    pub fn encode_asn(asn: &ASN1Block) -> Vec<u8> {
        to_der(asn).expect("ASN encoding broke")
    }

    pub fn pack_set(items: HashSet<u8>) -> Vec<u8> {
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

    pub fn unpack_set(buf_: Vec<u8>) -> HashSet<u8> {
        let mut set = HashSet::new();
        let buf: Vec<&u8> = buf_.iter().skip(1).collect();

        // TODO: omg check

        for i in 0..(buf.len() * 8) {
            if buf[i >> 3] & (1 << (7 - i % 8)) != 0 {
                set.insert(i as u8);
            }
        }
        set
    }

    pub fn asn_data(vecs: &Vec<Vec<u8>>) -> Vec<ASN1Block> {
        let mut out = Vec::new();
        for (i, v) in vecs.iter().enumerate() {
            out.push(asn_unknown(false, i, v.to_vec()));
        }
        out
    }

    pub fn asn_unknown(construct: bool, tag: usize, vec: Vec<u8>) -> ASN1Block {
        ASN1Block::Unknown(
            ASN1Class::ContextSpecific,
            construct,
            0,
            BigUint::from_usize(tag).unwrap(),
            vec,
        )
    }

    pub fn asn_choice(type_id: u8, children: &Vec<ASN1Block>) -> ASN1Block {
        asn_unknown(true, type_id as usize, asns_to_vec(children))
    }

    pub fn asn_sequence(children: Vec<ASN1Block>) -> ASN1Block {
        ASN1Block::Sequence(0, children)
    }

    pub fn hash_asn(asn: &ASN1Block) -> Vec<u8> {
        sha256(encode_asn(asn))
    }

    fn asns_to_vec(asns: &Vec<ASN1Block>) -> Vec<u8> {
        let mut body = Vec::new();
        for child in asns {
            body.append(&mut encode_asn(child));
        }
        body
    }
}

use internal::*;

#[cfg(test)]
mod tests {
    use super::*;
    use rustc_hex::{FromHex, ToHex};

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
            internal::pack_set(vec![1, 2, 3].into_iter().collect()).to_hex::<String>(),
            "0470"
        );
        assert_eq!(
            internal::pack_set(vec![1, 2, 3, 4, 5, 6, 7, 8, 9].into_iter().collect())
                .to_hex::<String>(),
            "067fc0"
        );
        assert_eq!(
            internal::pack_set(vec![15].into_iter().collect()).to_hex::<String>(),
            "000001"
        );
    }
}
