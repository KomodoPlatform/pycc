
use pyo3::{create_exception, prelude::*};

create_exception!(pycctx, DecodeError, pyo3::exceptions::Exception);
create_exception!(pycctx, TxNotSigned, pyo3::exceptions::Exception);
create_exception!(pycctx, TxSignError, pyo3::exceptions::Exception);



pub fn setup_module(py: Python, m: &PyModule) -> PyResult<()> {
    m.add("DecodeError", py.get_type::<DecodeError>())?;
    m.add("TxSignError", py.get_type::<DecodeError>())?;
    m.add("TxNotSigned", py.get_type::<DecodeError>())?;
    Ok(())
}