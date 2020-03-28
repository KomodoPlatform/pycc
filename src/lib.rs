// #[macro_use]
extern crate chain;
extern crate primitives;
extern crate serialization;

use pyo3::{create_exception, prelude::*, types::PyBytes, types::PyDict, wrap_pyfunction};
use rustc_hex::FromHex;

#[pyclass]
struct KomodoTxIn {
    vin: chain::TransactionInput,
}

#[pymethods]
impl KomodoTxIn {
    #[getter]
    fn previous_output(&self) -> (String, u32) {
        (
            self.vin.previous_output.hash.to_reversed_str(),
            self.vin.previous_output.index,
        )
    }

    #[getter]
    fn script_sig(&self, py: Python) -> PyObject {
        PyBytes::new(py, self.vin.script_sig.as_ref()).into()
    }

    fn as_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item("previous_output", self.previous_output())?;
        a.set_item("script_sig", self.script_sig(py))?;
        Ok(a.into())
    }
}

#[pyclass]
struct KomodoTxOut {
    vout: chain::TransactionOutput,
}

#[pymethods]
impl KomodoTxOut {
    #[getter]
    fn value(&self) -> u64 {
        self.vout.value
    }

    #[getter]
    fn script_pubkey(&self, py: Python) -> PyObject {
        PyBytes::new(py, self.vout.script_pubkey.as_ref()).into()
    }

    fn as_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item("value", self.value())?;
        a.set_item("script_pubkey", self.script_pubkey(py))?;
        Ok(a.into())
    }
}

create_exception!(pycctx, DecodeError, pyo3::exceptions::Exception);

#[pyclass]
struct KomodoTx {
    tx: chain::Transaction,
}

#[pymethods]
impl KomodoTx {
    #[getter]
    fn txid(&self) -> String {
        self.tx.hash().to_reversed_str()
    }

    #[getter]
    fn version(&self) -> i32 {
        self.tx.version
    }

    #[getter]
    fn lock_time(&self) -> u32 {
        self.tx.lock_time
    }

    #[getter]
    fn inputs(&self) -> Vec<KomodoTxIn> {
        self.tx
            .inputs
            .iter()
            .map(|vin| KomodoTxIn { vin: vin.clone() })
            .collect()
    }

    #[getter]
    fn outputs(&self) -> Vec<KomodoTxOut> {
        self.tx
            .outputs
            .iter()
            .map(|vout| KomodoTxOut { vout: vout.clone() })
            .collect()
    }

    fn as_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item(
            "inputs",
            self.inputs()
                .iter()
                .map(|vin| vin.as_py(py).unwrap())
                .collect::<Vec<PyObject>>(),
        )?;
        a.set_item(
            "outputs",
            self.outputs()
                .iter()
                .map(|vout| vout.as_py(py).unwrap())
                .collect::<Vec<PyObject>>(),
        )?;
        Ok(a.into())
    }
}

fn tx_decode(s: &[u8]) -> PyResult<KomodoTx> {
    match serialization::deserialize(s) {
        Ok(t) => Ok(KomodoTx { tx: t }),
        Err(e) => {
            return Err(DecodeError::py_err(format!(
                "Error decoding transaction: {:?}",
                e
            )))
        }
    }
}

#[pyfunction]
fn tx_from_bin(s: &[u8]) -> PyResult<KomodoTx> {
    tx_decode(s)
}

#[pyfunction]
fn tx_from_hex(s: String) -> PyResult<KomodoTx> {
    match s.from_hex::<Vec<u8>>() {
        Ok(s) => tx_decode(&s),
        Err(e) => return Err(DecodeError::py_err(format!("Invalid hex: {:?}", e))),
    }
}

/// This module is a python module implemented in Rust.
#[pymodule]
fn pycctx(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<KomodoTx>()?;
    m.add_wrapped(wrap_pyfunction!(tx_from_bin))?;
    m.add_wrapped(wrap_pyfunction!(tx_from_hex))?;
    Ok(())
}
