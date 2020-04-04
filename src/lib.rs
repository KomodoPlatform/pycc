extern crate chain;
extern crate primitives;
extern crate serialization;

use pyo3::{create_exception, prelude::*, types::{PyBytes, PyDict, PyTuple}};
use rustc_hex::FromHex;
use primitives::hash;
use std::str::FromStr;

mod script;
use crate::script::*;


create_exception!(pycctx, DecodeError, pyo3::exceptions::Exception);

#[pyclass]
#[derive(Clone)]
struct TxIn {
    vin: chain::TransactionInput,
}

#[pymethods]
impl TxIn {
    #[new]
    fn new(outpoint: (&str, u32), script: &[u8]) -> PyResult<Self> {
        let mut vin = chain::TransactionInput::default();
        let (hash_str, index) = outpoint;
        vin.previous_output.index = index;
        vin.script_sig = script.into();
        vin.previous_output.hash = match hash::H256::from_str(hash_str) {
            Err(e) => return Err(DecodeError::py_err(format!("Invalid hex: {:?}", e))),
            Ok(h)  => h.reversed()
        };
        Ok(TxIn { vin })
    }

    #[getter]
    fn previous_output(&self) -> (String, u32) {
        (
            self.vin.previous_output.hash.to_reversed_str(),
            self.vin.previous_output.index,
        )
    }

    #[getter]
    fn script(&self) -> ScriptSig {
        ScriptSig::new(&self.vin.script_sig)
    }

    fn to_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item("previous_output", self.previous_output())?;
        a.set_item("script", PyCell::new(py, self.script())?)?;
        Ok(a.into())
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
    fn new(amount: u64, script: &[u8]) -> Self {
        let mut vout = chain::TransactionOutput::default();
        vout.value = amount;
        vout.script_pubkey = script.into();
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
        a.set_item("script", PyCell::new(py, self.script())?)?;
        Ok(a.into())
    }
}

#[pyclass]
struct Tx {
    tx: chain::Transaction,
}

#[pyclass]
struct MutableTx {
    tx: chain::Transaction,
}

fn get_py_inputs(tx: &chain::Transaction) -> Vec<TxIn> {
    tx.inputs
        .iter()
        .map(|vin| TxIn { vin: vin.clone() })
        .collect()
}

fn get_py_outputs(tx: &chain::Transaction) -> Vec<TxOut> {
    tx.outputs
        .iter()
        .map(|vout| TxOut { vout: vout.clone() })
        .collect()
}

fn tx_to_py(tx: &chain::Transaction, py: Python) -> PyResult<PyObject> {
    let a = PyDict::new(py);
    a.set_item(
        "inputs",
        get_py_inputs(tx)
            .iter()
            .map(|vin| vin.to_py(py).unwrap())
            .collect::<Vec<PyObject>>(),
    )?;
    a.set_item(
        "outputs",
        get_py_outputs(tx)
            .iter()
            .map(|vout| vout.to_py(py).unwrap())
            .collect::<Vec<PyObject>>(),
    )?;
    Ok(a.into())
}

macro_rules! vec_to_tuple {
    ($py:expr, $vec:expr) => {
        PyTuple::new($py, $vec.into_iter().map(|c| PyCell::new($py, c).unwrap())).into()
    }
}

#[pymethods]
impl Tx {
    #[new]
    fn new(inputs: Vec<TxIn>, outputs: Vec<TxOut>) -> Self {
        let mut tx = chain::Transaction::default();
        tx.inputs = inputs.iter().map(|i|i.vin.clone()).collect();
        tx.outputs = outputs.iter().map(|i|i.vout.clone()).collect();
        Tx { tx }
    }
    #[getter] fn txid(&self) -> String { self.tx.hash().to_reversed_str() }
    #[getter] fn version(&self) -> i32 { self.tx.version }
    #[getter] fn lock_time(&self) -> u32 { self.tx.lock_time }
    #[getter] fn inputs(&self, py: Python) -> PyObject { vec_to_tuple!(py, get_py_inputs(&self.tx)) }
    #[getter] fn outputs(&self, py: Python) -> PyObject { vec_to_tuple!(py, get_py_outputs(&self.tx)) }
    fn to_py(&self, py: Python) -> PyResult<PyObject> { tx_to_py(&self.tx, py) }

    #[staticmethod]
    fn from_bin(bin_data: Vec<u8>) -> PyResult<Self> {
        tx_decode(&bin_data)
    }

    #[staticmethod]
    fn from_hex(hex_data: String) -> PyResult<Self> {
        match hex_data.from_hex::<Vec<u8>>() {
            Ok(s) => tx_decode(&s),
            Err(e) => return Err(DecodeError::py_err(format!("Invalid hex: {:?}", e))),
        }
    }
}

#[pymethods]
impl MutableTx {
    #[new]
    fn new() -> Self {
        MutableTx { tx: chain::Transaction::default() }
    }
    #[getter]
    fn txid(&self) -> String {
        self.tx.hash().to_reversed_str()
    }

    #[getter] fn get_version(&self) -> i32 { self.tx.version }
    #[setter] fn set_version(&mut self, version: i32) -> () { self.tx.version = version }

    #[getter] fn get_lock_time(&self) -> u32 { self.tx.lock_time }
    #[setter] fn set_lock_time(&mut self, lock_time: u32) -> () { self.tx.lock_time = lock_time }

    #[getter] fn get_inputs(&self, py: Python) -> PyObject { vec_to_tuple!(py, get_py_inputs(&self.tx)) }
    #[setter] fn set_inputs(&mut self, inputs: Vec<TxIn>) -> () {
        self.tx.inputs = inputs.iter().map(|kvin| kvin.vin.clone()).collect();
    }

    #[getter] fn get_outputs(&self, py: Python) -> PyObject { vec_to_tuple!(py, get_py_outputs(&self.tx)) }
    #[setter] fn set_outputs(&mut self, outputs: Vec<TxOut>) -> () {
        self.tx.outputs = outputs.iter().map(|kvout| kvout.vout.clone()).collect();
    }

    fn freeze(&self) -> Tx {
        Tx { tx: self.tx.clone() }
    }

    fn to_py(&self, py: Python) -> PyResult<PyObject> {
        tx_to_py(&self.tx, py)
    }
}

fn tx_decode(s: &[u8]) -> PyResult<Tx> {
    match serialization::deserialize(s) {
        Ok(t) => Ok(Tx { tx: t }),
        Err(e) => {
            return Err(DecodeError::py_err(format!(
                "Error decoding transaction: {:?}",
                e
            )))
        }
    }
}

/// This module is a python module implemented in Rust.
#[pymodule]
fn pycctx(py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Tx>()?;
    m.add_class::<MutableTx>()?;
    m.add_class::<TxIn>()?;
    m.add_class::<TxOut>()?;
    m.add_class::<ScriptPubKey>()?;
    m.add_class::<ScriptSig>()?;
    m.add("DecodeError", py.get_type::<DecodeError>())?;
    Ok(())
}
