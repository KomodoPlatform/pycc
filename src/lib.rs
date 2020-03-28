// #[macro_use]
extern crate chain;
extern crate primitives;
extern crate serialization;

use pyo3::{create_exception, prelude::*, types::PyDict, wrap_pyfunction};
use rustc_hex::FromHex;

#[pyclass]
struct KomodoTxIn {
    vin: chain::TransactionInput,
}

#[pymethods]
impl KomodoTxIn {
    #[getter]
    fn previous_output(&self) -> PyResult<(String, u32)> {
        Ok((
            self.vin.previous_output.hash.to_reversed_str(),
            self.vin.previous_output.index,
        ))
    }

    #[getter]
    fn script_sig(&self) -> PyResult<&[u8]> {
        Ok(self.vin.script_sig.as_ref())
    }

    fn as_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item("previous_output", self.previous_output().unwrap())?;
        a.set_item("script_sig", self.script_sig().unwrap())?;
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
    fn value(&self) -> PyResult<u64> {
        Ok(self.vout.value)
    }

    #[getter]
    fn script_pubkey(&self) -> PyResult<&[u8]> {
        Ok(self.vout.script_pubkey.as_ref())
    }

    fn as_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item("value", self.value().unwrap())?;
        a.set_item("script_pubkey", self.script_pubkey().unwrap())?;
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
    fn txid(&self) -> PyResult<String> {
        Ok(self.tx.hash().to_reversed_str())
    }

    #[getter]
    fn version(&self) -> PyResult<i32> {
        Ok(self.tx.version)
    }

    #[getter]
    fn lock_time(&self) -> PyResult<u32> {
        Ok(self.tx.lock_time)
    }

    #[getter]
    fn inputs(&self) -> PyResult<Vec<KomodoTxIn>> {
        Ok(self
            .tx
            .inputs
            .iter()
            .map(|vin| KomodoTxIn { vin: vin.clone() })
            .collect())
    }

    #[getter]
    fn outputs(&self) -> PyResult<Vec<KomodoTxOut>> {
        Ok(self
            .tx
            .outputs
            .iter()
            .map(|vout| KomodoTxOut { vout: vout.clone() })
            .collect())
    }

    fn as_py(&self, py: Python) -> PyResult<PyObject> {
        let a = PyDict::new(py);
        a.set_item(
            "inputs",
            self.inputs()
                .unwrap()
                .iter()
                .map(|vin| vin.as_py(py).unwrap())
                .collect::<Vec<PyObject>>(),
        )?;
        a.set_item(
            "outputs",
            self.outputs()
                .unwrap()
                .iter()
                .map(|vout| vout.as_py(py).unwrap())
                .collect::<Vec<PyObject>>(),
        )?;
        Ok(a.into())
    }
}

fn tx_decode(s: &[u8]) -> PyResult<KomodoTx> {
    let t: chain::Transaction = match serialization::deserialize(s) {
        Ok(t) => t,
        Err(e) => {
            return Err(DecodeError::py_err(format!(
                "Error decoding transaction: {:?}",
                e
            )))
        }
    };
    Ok(KomodoTx { tx: t })
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
