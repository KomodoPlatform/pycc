extern crate chain;
extern crate primitives;
extern crate serialization;
extern crate script as ss;
extern crate keys as kk;

mod transaction;
mod script;



use pyo3::{prelude::*};
use crate::script::script_setup_module;
use transaction::pycctx_transaction;



#[pymodule]
fn pycctx(py: Python, m: &PyModule) -> PyResult<()> {
    pycctx_transaction(py, m)?;
    script_setup_module(py, m)?;
    Ok(())
}
