extern crate chain;
extern crate primitives;
extern crate serialization;

use pyo3::{create_exception, prelude::*, types::{PyDict, PyTuple, PyBytes}, exceptions};
use rustc_hex::{FromHex, ToHex};
use primitives::hash;
use std::str::FromStr;

use crate::script::*;
use crate::script::ScriptPubKey;


create_exception!(pycctx, DecodeError, pyo3::exceptions::Exception);

#[pyclass]
#[derive(Clone)]
struct TxIn {
    pub previous_output: chain::OutPoint,
    pub script: ScriptSig,
    pub input_amount: Option<u64>
}

#[pymethods]
impl TxIn {
    #[new]
    #[args(input_amount="None")]
    fn new(previous_output: (&str, u32), script: ScriptSig, input_amount: Option<u64>) -> PyResult<Self> {
        let mut outpoint = chain::OutPoint::default();
        outpoint.hash = hash::H256::from_str(previous_output.0).map_err(to_py_err)?.reversed();
        outpoint.index = previous_output.1;
        Ok(TxIn { previous_output: outpoint, script, input_amount })
    }

    #[getter]
    fn previous_output(&self) -> (String, u32) {
        (
            self.previous_output.hash.to_reversed_str(),
            self.previous_output.index,
        )
    }

    #[getter]
    fn script(&self) -> ScriptSig {
        self.script.clone()
    }

    #[getter]
    fn input_amount(&self) -> Option<u64> {
        self.input_amount
    }

    fn to_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item("previous_output", self.previous_output())?;
        a.set_item("script", self.script.to_py(py)?)?;
        Ok(a.into())
    }
}

impl From<&chain::TransactionInput> for TxIn {
    fn from(vin: &chain::TransactionInput) -> TxIn {
        let script = ScriptSig::from(&**vin.script_sig);
        TxIn { previous_output: vin.previous_output.clone(), script, input_amount: None }
    }
}

#[pyclass]
#[derive(Clone)]
struct TxOut {
    vout: chain::TransactionOutput,
}

#[pymethods]
impl TxOut {
    #[new]
    fn new(amount: u64, script: &ScriptPubKey) -> Self {
        let mut vout = chain::TransactionOutput::default();
        vout.value = amount;
        vout.script_pubkey = script.into_vec().into();
        TxOut { vout }
    }

    #[getter]
    fn amount(&self) -> u64 {
        self.vout.value
    }

    #[getter]
    fn script(&self) -> ScriptPubKey {
        ScriptPubKey::new(&self.vout.script_pubkey)
    }

    fn to_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item("amount", self.amount())?;
        a.set_item("script", PyBytes::new(py, &self.script().into_vec()))?;
        Ok(a.into())
    }

    #[staticmethod]
    fn op_return(data: &[u8]) -> Self {
        Self::new(0, &ScriptPubKey::from_opret_data(data))
    }
}


fn get_py_outputs(tx: &chain::Transaction) -> Vec<TxOut> {
    tx.outputs
        .iter()
        .map(|vout| TxOut { vout: vout.clone() })
        .collect()
}

macro_rules! vec_to_tuple {
    ($py:expr, $vec:expr) => {
        PyTuple::new($py, $vec.into_iter().map(|c| PyCell::new($py, c).unwrap())).into()
    }
}

#[pyclass]
struct Tx {
    tx: chain::Transaction,
    inputs: Vec<TxIn>
}

#[pymethods]
impl Tx {
    #[new]
    fn new(inputs, outputs, version) -> Self {
        let mut tx = chain::Transaction::default();
        tx.version = 1;
        Tx { tx, inputs: vec![] }
    }

    #[getter]
    fn hash(&self) -> PyResult<String> {
        Ok(self.freeze()?.tx.hash().to_reversed_str())
    }

    #[getter] fn get_version(&self) -> i32 { self.tx.version }
    #[setter] fn set_version(&mut self, version: i32) -> () { self.tx.version = version }

    #[getter] fn get_lock_time(&self) -> u32 { self.tx.lock_time }
    #[setter] fn set_lock_time(&mut self, lock_time: u32) -> () { self.tx.lock_time = lock_time }

    #[getter] fn get_inputs(&self, py: Python) -> PyObject { vec_to_tuple!(py, self.inputs.clone()) }
    #[setter] fn set_inputs(&mut self, inputs: Vec<TxIn>) { self.inputs = inputs }

    #[getter] fn get_outputs(&self, py: Python) -> PyObject { vec_to_tuple!(py, get_py_outputs(&self.tx)) }
    #[setter] fn set_outputs(&mut self, outputs: Vec<TxOut>) -> () {
        self.tx.outputs = outputs.iter().map(|kvout| kvout.vout.clone()).collect();
    }

    fn sign(&mut self, privkeys_strings: Vec<String>) -> PyResult<()> {
        fn decode_wif(s: &String) -> PyResult<kk::Private> {
            kk::Private::from_str(s).map_err(|_| exceptions::ValueError::py_err("Cannot decode privkey WIF"))
        }
        let privkeys: Vec<kk::Private> = privkeys_strings.iter().map(decode_wif).collect::<PyResult<Vec<kk::Private>>>()?;
        let mut tx = self.tx.clone();

        self.tx.inputs.truncate(0);

        for input in &self.inputs {
            let mut inp = chain::TransactionInput::default();
            inp.previous_output = input.previous_output.clone();
            tx.inputs.push(inp);
        }

        let signer = ss::TransactionInputSigner::from(tx.clone());
        'outer: for (i, input) in self.inputs.iter_mut().enumerate() {
            let pubkey = input.script.to_pubkey_script()?;
            let amount = input.input_amount.ok_or(exceptions::ValueError::py_err("Missing input amount"))?;
            let sighash = signer.signature_hash(i as usize, amount, &pubkey, ss::SignatureVersion::Base, 1);
            for key in &privkeys {
                input.script.sign(&sighash, &key).map_err(to_py_err)?;
                match input.script.as_signed() {
                    Some(script) => {
                        let mut tx_input = chain::TransactionInput::default();
                        tx_input.previous_output = input.previous_output.clone();
                        tx_input.script_sig = script.into();
                        tx.inputs[i] = tx_input;
                        continue 'outer;
                    },
                    None => { }
                }
            }
            return Err(exceptions::ValueError::py_err("Cannot sign input with given keys"));
        }

        Ok(())
    }

    fn to_py(&self, py: Python) -> PyResult<PyObject> {
       let a = PyDict::new(py);
       a.set_item(
           "inputs",
            self.inputs.iter().map(|vin| vin.to_py(py)).collect::<PyResult<Vec<PyObject>>>()?)?;
       a.set_item(
           "outputs",
           get_py_outputs(&self.tx)
               .iter()
               .map(|vout| vout.to_py(py))
               .collect::<PyResult<Vec<PyObject>>>()?,
       )?;
       Ok(a.into())
    }

    fn freeze(&self) -> PyResult<FrozenTx> {
        let mut tx = self.tx.clone();
        tx.inputs.truncate(0);
        for input in &self.inputs {
            match input.script.as_signed() {
                Some(script) => {
                    let mut tx_input = chain::TransactionInput::default();
                    tx_input.previous_output = input.previous_output.clone();
                    tx_input.script_sig = script.into();
                    tx.inputs.push(tx_input);
                },
                _ => return Err(to_py_err("Can't freeze tx, has unsigned inputs"))
            }
        }
        Ok(FrozenTx { tx })
    }

    fn encode(&self) -> PyResult<String> {
        Ok(serialization::serialize(&self.freeze()?.tx).to_hex())
    }

    fn encode_bin(&self, py: Python) -> PyResult<PyObject> {
        Ok(PyBytes::new(py, &serialization::serialize(&self.freeze()?.tx)).into())
    }

    #[staticmethod]
    fn decode_bin(bin_data: Vec<u8>) -> PyResult<Self> {
        let tx: chain::Transaction = serialization::deserialize(&*bin_data).map_err(
            |_| exceptions::ValueError::py_err("Invalid tx bin"))?;
        Ok(Tx { tx: tx.clone(), inputs: tx.inputs.iter().map(From::from).collect() })
    }

    #[staticmethod]
    fn decode(hex_data: String) -> PyResult<Self> {
        Self::decode_bin(hex_data.from_hex::<Vec<u8>>().map_err(|_|DecodeError::py_err("Invalid hex"))?)
    }
}

#[pyclass]
struct FrozenTx {
    tx: chain::Transaction
}

fn to_py_err(e: impl ToString) -> pyo3::PyErr {
    exceptions::ValueError::py_err(e.to_string())
}


pub fn pycctx_transaction(py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Tx>()?;
    m.add_class::<TxIn>()?;
    m.add_class::<TxOut>()?;
    m.add("DecodeError", py.get_type::<DecodeError>())?;
    Ok(())
}
