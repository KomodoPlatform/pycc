extern crate chain;
extern crate primitives;
extern crate serialization;
extern crate script as ss;
extern crate keys as kk;

mod transaction;
mod script;
mod exceptions;

use pyo3::{prelude::*};



#[pymodule]
fn pycctx(py: Python, m: &PyModule) -> PyResult<()> {
    transaction::setup_module(py, m)?;
    script::setup_module(py, m)?;
    exceptions::setup_module(py, m)?;
    Ok(())
}
