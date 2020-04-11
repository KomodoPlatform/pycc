
use cryptoconditions as cc;
use pyo3::{exceptions, prelude::*, types::{PyBytes, PyDict}, wrap_pyfunction};

use rustc_hex::{FromHex, ToHex};
use ss::{Script, Builder};
use primitives::hash as hash;


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

    pub fn into_vec(&self) -> Vec<u8> {
        self.script.to_vec()
    }

    #[staticmethod]
    pub fn from_address(addr: &str) -> PyResult<Self> {
        Ok(Self::from(&parse_address(addr)?))
    }

    #[staticmethod]
    pub fn from_condition(cond: PyCondition) -> Self {
        Self::from(&cond)
    }

    #[staticmethod]
    pub fn from_opret_data(data: &[u8]) -> Self {
        Self { script: Builder::build_nulldata(data) }
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


use ScriptSigInner::*;

#[derive(PartialEq, Clone, Debug)]
pub enum ScriptSigInner {
    AddressSig {
        address: kk::Address,
        signature: Option<(kk::Public, kk::Signature)>
    },
    ConditionSig {
        condition: PyCondition
    },
    SigBytes {
        script: Vec<u8>
    }
}

#[pyclass]
#[derive(PartialEq, Clone, Debug)]
pub struct ScriptSig {
    script: ScriptSigInner
}

#[pymethods]
impl ScriptSig {
    #[new]
    pub fn new(s: Vec<u8>) -> Self {
        Self { script: SigBytes { script: s } }
    }

    pub fn to_py(&self, py: Python) -> PyResult<PyObject> {
        let d = PyDict::new(py);

        let f = |k, o: PyObject| {
            d.set_item(k, o)?;
            Ok(d.into())
        };

        match &self.script {
            AddressSig { address, signature } => {
                let inner = PyDict::new(py);
                inner.set_item("address", address.to_string())?;
                match signature {
                    Some((public, sig)) => {
                        inner.set_item("pubkey", public.to_string())?;
                        inner.set_item("signature", sig.to_string())?;
                    },
                    _ => ()
                };
                f("address", inner.into())
            },
            ConditionSig { condition } => {
                f("condition", condition.to_py(py)?)
            },
            SigBytes { script } => {
                Ok(PyBytes::new(py, &script).into())
            }
        }
    }

    #[staticmethod]
    pub fn from_address(address: &str) -> PyResult<Self> {
        Ok(Self { script: AddressSig { address: parse_address(address)?, signature: None } })
    }

    #[staticmethod]
    pub fn from_condition(condition: PyCondition) -> Self {
        Self { script: ConditionSig { condition } }
    }
}

impl ScriptSig {
    pub fn as_signed(&self) -> Option<Script> {
        let append_hash_type = |l:&[u8]| {
            let mut v = l.to_vec();
            v.push(1);
            v
        };
        match &self.script {
            AddressSig { signature: Some((public, sig)), .. } => {
                Some(Builder::default().push_data(&append_hash_type(&**sig)).push_data(&**public).into_script())
            }
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
        match &self.script {
            AddressSig { address, .. } => Ok(ScriptPubKey::from(address).script),
            ConditionSig { condition } => Ok(ScriptPubKey::from(condition).script),
            SigBytes { .. } => Err(exceptions::ValueError::py_err("Cannot convert SigBytes to pubkey"))
        }
    }

    pub fn sign(&mut self, sighash: &hash::H256, private: &kk::Private) -> Result<(), kk::Error> {
        match &mut self.script {
            AddressSig { address, ref mut signature } => {
                let public = kk::KeyPair::from_private(private.clone())?.public().clone();
                if public.address_hash() == address.hash {
                    *signature = Some((public, private.sign(sighash)?));
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
        ScriptSig { script: SigBytes { script: bytes.to_vec() } }
    }
}

impl From<cc::Condition> for ScriptSig {
    fn from(condition: cc::Condition) -> ScriptSig {
        ScriptSig { script: ConditionSig { condition: PyCondition { cond: condition } } }
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
        let cond = cc::decode_fulfillment(&cond_bin).map_err(
            |_| exceptions::ValueError::py_err("Invalid fulfillment data"))?;
        Ok(Self { cond })
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
