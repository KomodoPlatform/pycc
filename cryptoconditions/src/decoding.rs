use num_bigint::BigInt;
use num_traits::cast::ToPrimitive;
use secp256k1::{PublicKey, Signature};
use simple_asn1::{from_der, ASN1Block, ASN1Class};
use std::collections::HashSet;

use crate::Condition::*;
use crate::*;

#[derive(PartialEq, Debug)]
pub struct ConditionDecodeError(pub String);

type R<T> = Result<T, ConditionDecodeError>;

pub fn decode_fulfillment(buf: &[u8]) -> R<Condition> {
    let mut p = Parser::from_buf(buf)?;
    let o = parse_fulfillment(&mut p);
    let () = p.end()?;
    o
}

pub fn decode_condition(buf: &[u8]) -> R<Condition> {
    parse_condition(&mut Parser::from_buf(buf)?)
}

fn condition_type_from_id(id: u8) -> Result<ConditionType, ConditionDecodeError> {
    Ok(match id {
        0 => PreimageType,
        2 => ThresholdType,
        5 => Secp256k1Type,
        15 => EvalType,
        _ => Err(ConditionDecodeError(format!("Unknown condition type id: {:?}", id)))?
    })
}

struct Parser(Vec<ASN1Block>);

impl Parser {
    fn new(asns: Vec<ASN1Block>) -> Self {
        Parser(asns)
    }
    fn from_buf(data: &[u8]) -> R<Parser> {
        if data.is_empty() {
            Ok(Parser(Vec::new()))
        } else {
            match from_der(data) {
                Ok(asns) => Ok(Self::new(asns)),
                Err(_) => {
                    Err(err("Invalid ASN data1"))
                }
            }
        }
    }
    fn container(&mut self, type_id: u8) -> R<Parser> {
        let (tid, buf) = self.lpop()?;
        if tid == type_id {
            Self::from_buf(&buf)
        } else {
            Err(err("Unexpected identifier in ASN"))
        }
    }
    fn many<F, T>(&mut self, f: F) -> R<Vec<T>>
    where
        F: Fn(&mut Parser) -> R<T>,
    {
        let mut out = Vec::new();
        while !self.0.is_empty() {
            out.push(f(self)?);
        }
        Ok(out)
    }
    fn lpop(&mut self) -> R<(u8, Vec<u8>)> {
        if self.0.is_empty() {
            return Err(err("Expected element"));
        }
        let asn = self.0.remove(0);
        match asn {
            ASN1Block::Unknown(ASN1Class::ContextSpecific, _, _, type_id, buf) => {
                Ok((type_id.to_u8().ok_or(err("Invalid type id"))?, buf))
            },
            //ASN1Block::Explicit(ASN1Class::ContextSpecific, _, type_id, box_) => {
            //    let unbox = *box_;
            //    if let ASN1Block::Unknown(ASN1Class::ContextSpecific, false, _, _, buf) = unbox {
            //        let buf_ = to_der(&internal::asn_unknown(false, 0, buf.to_vec())).unwrap();
            //        // TODO: safe to_der for decoding
            //        Ok((type_id.to_u8().ok_or(err("Invalid type id"))?, buf_))
            //    } else if let ASN1Block::Explicit(ASN1Class::ContextSpecific, _, type_id_2, box_) = unbox {
            //        unimplemented!("")
            //        
            //    } else {
            //        println!("{:?}", unbox);
            //        Err(err("unexpected structure1"))
            //    }
            //}
            _ => Err(err("unexpected structure2")),
        }
    }
    fn any(&mut self) -> R<(u8, Parser)> {
        let (tid, buf) = self.lpop()?;
        Ok((tid, Self::from_buf(&buf)?))
    }
    fn buf(&mut self, type_id: u8) -> R<Vec<u8>> {
        let (t, buf) = self.lpop()?;
        match t == type_id {
            true => Ok(buf),
            _ => Err(ConditionDecodeError(format!(
                "Wrong type id, expected: {:?} but got: {:?}",
                type_id, t
            ))),
        }
    }
    fn end(&self) -> R<()> {
        match self.0.is_empty() {
            true => Ok(()),
            _ => Err(err("ASN has leftover elements\n")),
        }
    }
}

fn parse_fulfillment(parser: &mut Parser) -> R<Condition> {
    let (tid, mut p) = parser.any()?;
    //let () = parser.end()?;
    let o = match tid {
        0 => parse_preimage(&mut p),
        2 => parse_threshold(&mut p),
        5 => parse_secp256k1(&mut p),
        15 => parse_eval(&mut p),
        _ => Err(err("Inavalid Condition ASN")),
    }?;
    let () = p.end()?;
    Ok(o)
}

fn parse_condition(top_parser: &mut Parser) -> R<Condition> {
    let (type_id, mut parser) = top_parser.any()?;
    let cond_type = condition_type_from_id(type_id)?;
    let () = top_parser.end()?;
    let fingerprint = parser.buf(0)?;
    let cost = BigInt::from_signed_bytes_be(&parser.buf(1)?)
        .to_u64()
        .ok_or(err("Can't decode cost"))?;
    let subtypes = match cond_type.has_subtypes() {
        true => internal::unpack_set(parser.buf(2)?),
        _ => HashSet::new(),
    };
    let () = parser.end()?;
    Ok(Anon {
        cond_type,
        fingerprint,
        cost,
        subtypes,
    })
}

fn parse_preimage(parser: &mut Parser) -> R<Condition> {
    Ok(Preimage {
        preimage: parser.buf(0)?,
    })
}

fn parse_secp256k1(parser: &mut Parser) -> R<Condition> {
    match (
        PublicKey::parse_slice(&parser.buf(0)?, None),
        Signature::parse_slice(&parser.buf(1)?),
    ) {
        (Ok(pubkey), Ok(sig)) => Ok(Secp256k1 {
            pubkey,
            signature: Some(sig),
        }),
        _ => Err(err("Bad ASN1 secp256k1")),
    }
}

fn parse_threshold(parser: &mut Parser) -> R<Condition> {
    let mut ffills = parser.container(0)?.many(parse_fulfillment)?;
    let mut conds = parser.container(1)?.many(parse_condition)?;
    let () = parser.end()?;
    let t = ffills.len() as u16;
    ffills.append(&mut conds);
    Ok(Threshold {
        threshold: t,
        subconditions: ffills,
    })
}

fn parse_eval(parser: &mut Parser) -> R<Condition> {
    let code = parser.buf(0)?;
    let () = parser.end()?;
    Ok(Eval { code })
}

fn err(s: &str) -> ConditionDecodeError {
    ConditionDecodeError(s.into())
}
