
use cryptoconditions::Condition;
use pyo3::{create_exception, prelude::*, PyCell, types::{PyBytes, PyDict, PyTuple}, wrap_pyfunction};

extern crate script as sscript;
use sscript::*;


#[pyclass]
pub struct ScriptPubKey {
    script: Script
}


#[pymethods]
impl ScriptPubKey {
    #[new]
    pub fn new(s: &[u8]) -> Self {
        ScriptPubKey { script: Script::from(s.to_vec()) }
    }

    pub fn get_opret_data(&self, py: Python) -> Option<PyObject> {
        if self.script.is_null_data_script() {
            let bytes = PyBytes::new(py, self.script.get_instruction(1).ok()?.data?);
            return Some(bytes.into())
        }
        None
    }

    #[staticmethod]
    pub fn p2pkh_from_addr(addr: &[u8]) -> ScriptPubKey {
        ScriptPubKey { script: Builder::build_p2pkh(addr) }
    }
}


#[pyclass]
pub enum ScriptSig {
    ScriptSig {
        script: Vec<u8>
    },
    AddressSig {
        address: Vec<u8>
    }
}


#[pymethods]
impl ScriptSig {
    #[new]
    pub fn new(s: &[u8]) -> Self {
        ScriptSig { script: s.to_vec() }
    }
}
