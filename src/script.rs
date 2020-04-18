
use cryptoconditions as cc;
use pyo3::{exceptions, prelude::*, types::{PyBytes, PyDict}, wrap_pyfunction};

use rustc_hex::{FromHex, ToHex};
use ss::{Script, Builder};
use primitives::hash as hash;

use crate::keys::*;
use crate::exceptions::*;


#[pyclass]
#[derive(PartialEq, Debug)]
pub struct ScriptPubKey {
    script: Script
}


#[pymethods]
impl ScriptPubKey {
    #[new]
    pub fn new(s: &[u8]) -> Self {
        Self { script: Script::from(s.to_vec()) }
    }

    pub fn get_opret_data(&self, py: Python) -> Option<PyObject> {
        if self.script.is_null_data_script() {
            let bytes = PyBytes::new(py, self.script.get_instruction(1).ok()?.data?);
            return Some(bytes.into())
        }
        None
    }

    pub fn parse_p2pkh(&self, py: Python) -> PyResult<PyObject> {
        if self.script.is_pay_to_public_key_hash() {
            let hash_data = self.script.take(3, 20).unwrap();
            let addr = to_kmd_address(hash::H160::from(hash_data));
            let d = PyDict::new(py);
            d.set_item("address", addr.to_string())?;
            Ok(d.into())
        } else {
            Err(UnexpectedScriptPubkey::py_err(format!("{:?}", self.script.script_type())))
        }
    }

    pub fn parse_condition(&self) -> PyResult<PyCondition> {
        let u = UnexpectedScriptPubkey::py_err;
        match self.script.get_instruction(0).map_err(|_| u("Could not get condition from script pubkey"))? {
            ss::Instruction { data: Some(conddata), step, .. } 
                if self.script.len() == (step + 1) && self.script[step] == 0xcc => {
                    Ok(PyCondition { cond: cc::decode_condition(conddata).map_err(|_| u("Invalid condition pubkey"))? })
            },
            _ => Err(u("Invalid condition script pubkey"))
        }
    }

    #[staticmethod]
    pub fn from_address(addr: &str) -> PyResult<Self> {
        Ok(Self::from(&parse_address(addr)?))
    }

    #[staticmethod]
    pub fn from_pubkey(pubkey_hex: &str) -> PyResult<Self> {
        let pubkey_bin = pubkey_hex.from_hex::<Vec<u8>>().map_err(|_|
            exceptions::ValueError::py_err("Invalid pubkey hex"))?;
        let pubkey = kk::Public::from_slice(&pubkey_bin).map_err(|_|
            exceptions::ValueError::py_err("Invalid pubkey"))?;
        Ok(Self::from(&pubkey))
    }

    #[staticmethod]
    pub fn from_condition(cond: PyCondition) -> Self {
        Self::from(&cond)
    }

    #[staticmethod]
    pub fn from_opret_data(data: &[u8]) -> Self {
        Self { script: Builder::default().push_opcode(ss::Opcode::OP_RETURN).push_data(data).into_script() }
    }
}

impl ScriptPubKey {
    pub fn into_vec(&self) -> Vec<u8> {
        self.script.to_vec()
    }
}

impl From<&kk::Address> for ScriptPubKey {
    fn from(addr: &keys::Address) -> Self {
        Self { script: Builder::build_p2pkh(&addr.hash) }
    }
}

impl From<&PyCondition> for ScriptPubKey {
    fn from(cond: &PyCondition) -> Self {
        let mut data = Builder::default().push_data(&cond.cond.encode_condition()).into_bytes();
        data.push(0xcc);
        Self { script: Script::new(data) }
    }
}

impl From<&kk::Public> for ScriptPubKey {
    fn from(pk: &kk::Public) -> Self {
        Self { script: Builder::default().push_bytes(&**pk).push_opcode(ss::Opcode::OP_CHECKSIG).into_script() }
    }
}


use ScriptSigInner::*;

#[derive(PartialEq, Clone, Debug)]
pub enum ScriptSigInner {
    AddressSig {
        address: kk::Address,
        signature: Option<(kk::Public, kk::Signature)>
    },
    PubkeySig {
        pubkey: kk::Public,
        signature: Option<kk::Signature>
    },
    ConditionSig {
        condition: PyCondition
    },
    SigBytes {
        script: ss::Script
    }
}

#[pyclass]
#[derive(PartialEq, Clone, Debug)]
pub struct ScriptSig {
    inner: ScriptSigInner
}

#[pymethods]
impl ScriptSig {
    #[new]
    pub fn new(s: Vec<u8>) -> Self {
        Self { inner: SigBytes { script: ss::Script::from(s) } }
    }

    pub fn to_py(&self, py: Python) -> PyResult<PyObject> {
        let d = PyDict::new(py);

        match &self.inner {
            AddressSig { address, signature } => {
                d.set_item("address", address.to_string());;
                if let Some((public, sig)) = signature {
                    d.set_item("pubkey", public.to_string())?;
                    d.set_item("signature", sig.to_string())?;
                };
                Ok(d.into())
            },
            PubkeySig { pubkey, signature } => {
                d.set_item("pubkey", pubkey.to_string())?;
                if let Some(sig) = signature {
                    d.set_item("signature", sig.to_string())?;
                }
                Ok(d.into())
            },
            ConditionSig { condition } => {
                d.set_item("condition", condition.to_py(py)?)?;
                Ok(d.into())
            },
            SigBytes { script } => {
                Ok(PyBytes::new(py, &script).into())
            }
        }
    }

    pub fn parse_p2pkh(&self, py: Python) -> PyResult<PyObject> {
        let u = UnexpectedScriptSig::py_err;
        match &self.inner {
            SigBytes { script } => {
                match script.get_instruction(0).map_err(|_| u("Could not get sig from script sig"))? {
                    ss::Instruction { data: Some(sigdata), step, .. } => {
                        let step0 = step;
                        let sig = kk::Signature::from(&sigdata[..sigdata.len()-1]);
                        match script.get_instruction(step).map_err(|_| u("Could not get pk from script sig"))? {
                            ss::Instruction { data: Some(pkdata), step, .. } => {
                                if step0 + step != (&script).len() {
                                    return Err(u("Invalid p2pkh script"));
                                }
                                let pubkey = kk::Public::from_slice(pkdata).map_err(|_| u("Invalid pubkey"))?;
                                let address = to_kmd_address(pubkey.address_hash());
                                Ok(ScriptSig { inner: AddressSig { address, signature: Some((pubkey, sig)) } }.to_py(py)?)
                            },
                            _ => Err(u("Could not get pk from script sig"))
                        }
                    },
                    _ => Err(u("Could not get sig from script sig"))
                }
            },
            AddressSig { address, signature: Some((pk, sig)) } => Ok(self.to_py(py)?),
            _ => Err(u("Expected signed script"))
        }
    }

    pub fn parse_condition(&self) -> PyResult<PyCondition> {
        let u = UnexpectedScriptSig::py_err;
        match &self.inner {
            SigBytes { script } => {
                match script.get_instruction(0).map_err(|_| u("Could not get cc from script sig"))? {
                    ss::Instruction { data: Some(ffill), step, .. } => {
                        if step != (&script).len() {
                            return Err(u("Invalid cc script"));
                        }
                        PyCondition::decode_fulfillment_bin(&ffill[..ffill.len()-1])
                    },
                    _ => Err(u("Could not get cc from script sig"))
                }
            },
            ConditionSig { condition } => Ok(condition.clone()),
            _ => Err(u("Expected signed script"))
        }
    }

    #[staticmethod]
    pub fn from_address(address: &str) -> PyResult<Self> {
        Ok(Self { inner: AddressSig { address: parse_address(address)?, signature: None } })
    }

    #[staticmethod]
    pub fn from_pubkey(pubkey_hex: &str) -> PyResult<Self> {
        let pubkey_bin = pubkey_hex.from_hex::<Vec<u8>>().map_err(|_|
            exceptions::ValueError::py_err("Invalid pubkey hex"))?;
        let pubkey = kk::Public::from_slice(&pubkey_bin).map_err(|_|
            exceptions::ValueError::py_err("Invalid pubkey"))?;
        Ok(Self { inner: PubkeySig { pubkey, signature: None } })
    }

    #[staticmethod]
    pub fn from_condition(condition: PyCondition) -> Self {
        Self { inner: ConditionSig { condition } }
    }
}

impl ScriptSig {
    pub fn as_signed(&self) -> Option<Script> {
        let append_hash_type = |l:&[u8]| {
            let mut v = l.to_vec();
            v.push(1);
            v
        };
        match &self.inner {
            AddressSig { signature: Some((public, sig)), .. } => {
                Some(Builder::default().push_data(&append_hash_type(&**sig)).push_data(&**public).into_script())
            }
            PubkeySig { signature: Some(sig), .. } => {
                Some(Builder::default().push_data(&append_hash_type(&**sig)).into_script())
            },
            ConditionSig { condition } => {
                match condition.cond.encode_fulfillment() {
                    Ok(ffill) => Some(Builder::default().push_data(&append_hash_type(&ffill)).into_script()),
                    _ => None
                }
            },
            SigBytes { script } => Some(Script::from(script.clone())),
            _ => None
        }
    }

    pub fn to_pubkey_script(&self) -> PyResult<Script> {
        match &self.inner {
            AddressSig { address, .. } => Ok(ScriptPubKey::from(address).script),
            PubkeySig { pubkey, .. } => Ok(ScriptPubKey::from(pubkey).script),
            ConditionSig { condition } => Ok(ScriptPubKey::from(condition).script),
            SigBytes { .. } => Err(exceptions::ValueError::py_err("Cannot convert SigBytes to pubkey"))
        }
    }

    pub fn sign(&mut self, sighash: &hash::H256, private: &kk::Private) -> Result<(), kk::Error> {
        match &mut self.inner {
            AddressSig { address, ref mut signature } => {
                let public = kk::KeyPair::from_private(private.clone())?.public().clone();
                if public.address_hash() == address.hash {
                    *signature = Some((public, private.sign(sighash)?));
                }
            },
            PubkeySig { pubkey, ref mut signature } => {
                if pubkey == kk::KeyPair::from_private(private.clone())?.public() {
                    *signature = Some(private.sign(sighash)?);
                }
            },
            ConditionSig { condition } => {
                let secret = secp256k1::SecretKey::parse_slice(&*private.secret)?;
                let message = secp256k1::Message::parse_slice(&**sighash)?;
                condition.cond.sign_secp256k1(&secret, &message)?;
            }
            _ => ()
        };
        Ok(())
    }
}

impl From<&[u8]> for ScriptSig {
    fn from(bytes: &[u8]) -> ScriptSig {
        ScriptSig { inner: SigBytes { script: ss::Script::from(bytes.to_vec()) } }
    }
}

impl From<cc::Condition> for ScriptSig {
    fn from(condition: cc::Condition) -> ScriptSig {
        ScriptSig { inner: ConditionSig { condition: PyCondition { cond: condition } } }
    }
}

impl From<&kk::Address> for ScriptSig {
    fn from(address: &keys::Address) -> Self {
        Self { inner: AddressSig { address: address.clone(), signature: None } }
    }
}

fn parse_address(s: &str) -> PyResult<kk::Address> {
    s.parse().ok().ok_or(
    exceptions::ValueError::py_err("Could not parse address"))
}


#[pyclass(name=Condition)]
#[derive(PartialEq, Clone, Debug)]
pub struct PyCondition {
    cond: cc::Condition
}

#[pymethods]
impl PyCondition {
    fn to_py(&self, py: Python) -> PyResult<PyObject> {
        let d = PyDict::new(py);
        d.set_item("type", self.cond.get_type().name())?;
        match &self.cond {
            cc::Threshold { threshold, subconditions } => {
                d.set_item("threshold", threshold)?;
                let f = |cond:&cc::Condition|PyCondition { cond: cond.clone() }.to_py(py);
                d.set_item("subconditions", subconditions.iter().map(f).collect::<PyResult<Vec<PyObject>>>()?)?;
            },
            cc::Secp256k1 { pubkey, signature } => {
                d.set_item("pubkey", pubkey.serialize_compressed().to_hex::<String>())?;
                match signature {
                    Some(sig) => 
                        d.set_item("signature", sig.serialize().to_hex::<String>())?,
                    _ => ()
                }
            },
            cc::Preimage { preimage } => {
                d.set_item("preimage", preimage.to_hex::<String>())?;
            },
            cc::Eval { code } => {
                d.set_item("code", code.to_hex::<String>())?;
            },
            cc::Anon { .. } => {
                d.set_item("condition", self.cond.encode_condition().to_hex::<String>())?;
            }
        };
        Ok(d.into())
    }

    #[staticmethod]
    fn decode_fulfillment(condition_hex: String) -> PyResult<Self> {
        let cond_bin = condition_hex.from_hex::<Vec<u8>>().map_err(
            |e| exceptions::ValueError::py_err(e.to_string()))?;
        Self::decode_fulfillment_bin(&cond_bin)
    }

    #[staticmethod]
    fn decode_fulfillment_bin(condition_bin: &[u8]) -> PyResult<Self> {
        let cond = cc::decode_fulfillment(condition_bin).map_err(
            |_| exceptions::ValueError::py_err("Invalid fulfillment data"))?;
        Ok(Self { cond })
    }

    fn encode_condition(&self, py: Python) -> PyResult<PyObject> {
        Ok(PyBytes::new(py, &self.cond.encode_condition()).into())
    }

    fn encode_fulfillment(&self, py: Python) -> PyResult<PyObject> {
        let ffill = self.cond.encode_fulfillment().map_err(|e|
            CCEncodeError::py_err(e.to_string()))?;
        Ok(PyBytes::new(py, &ffill).into())
    }

    fn to_anon(&self) -> PyCondition {
        return Self { cond: self.cond.to_anon() }
    }

    fn is_same_condition(&self, other: PyCondition) -> bool {
        self.cond.encode_condition() == other.cond.encode_condition()
    }
}

#[pyfunction]
pub fn cc_preimage(preimage: Vec<u8>) -> PyCondition {
    PyCondition { cond: cc::Preimage { preimage } }
}
#[pyfunction]
pub fn cc_eval(code: Vec<u8>) -> PyCondition {
    PyCondition { cond: cc::Eval { code } }
}
#[pyfunction]
pub fn cc_secp256k1(pubkey_hex: String) -> PyResult<PyCondition> {
    let pubkey_bin = pubkey_hex.from_hex::<Vec<u8>>().map_err(|_|
        exceptions::ValueError::py_err("Invalid pubkey hex"))?;
    let pubkey = secp256k1::PublicKey::parse_slice(&pubkey_bin, None).map_err(|_|
        exceptions::ValueError::py_err("Invalid pubkey"))?;
    Ok(PyCondition { cond: cc::Secp256k1 { pubkey, signature: None }})
}
#[pyfunction]
pub fn cc_threshold(threshold: u16, subconditions: Vec<PyCondition>) -> PyCondition {
    let subs = subconditions.iter().map(|c|c.cond.clone()).collect();
    PyCondition { cond: cc::Threshold { threshold, subconditions: subs }}
}

pub fn setup_module(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<ScriptPubKey>()?;
    m.add_class::<ScriptSig>()?;
    m.add_class::<PyCondition>()?;
    m.add_wrapped(wrap_pyfunction!(cc_eval))?;
    m.add_wrapped(wrap_pyfunction!(cc_preimage))?;
    m.add_wrapped(wrap_pyfunction!(cc_secp256k1))?;
    m.add_wrapped(wrap_pyfunction!(cc_threshold))?;
    Ok(())
}


#[cfg(test)]
mod tests {
    use super::*;
    use std::str::FromStr;

    #[test]
    fn test_sig_encoding() {
        let privkey = kk::Private::from_str("UrLfELwGtHeXmvFYhpLZvCWbc3d9xH1nCvADXrzDGLPy2HY6nGm7").unwrap();
        let kp = kk::KeyPair::from_private(privkey.clone()).unwrap();
        let flags = ss::VerificationFlags::default().verify_strictenc(true);

        let f = |sig| {
            let script = Builder::default()
                .push_data(sig).push_data(&kp.public()).push_opcode(ss::Opcode::OP_CHECKSIG).into_script();
            let mut stack = ss::Stack::new();
            ss::eval_script(&mut stack, &script, &flags, &ss::NoopSignatureChecker, ss::SignatureVersion::Base)
        };

        let sig = privkey.sign(&hash::H256::default()).unwrap();
        assert_eq!(Err(ss::Error::SignatureDer), f(&*sig));

        let mut sigdata = (*sig).to_vec();
        sigdata.push(1);
        assert_eq!(Ok(false), f(&*sigdata)); // NoopSignatureChecker returns false
    }
}
