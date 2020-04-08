
use pyo3::{create_exception, prelude::*};

create_exception!(pycctx, DecodeError, pyo3::exceptions::Exception);
create_exception!(pycctx, TxNotSigned, pyo3::exceptions::Exception);
create_exception!(pycctx, TxSignError, pyo3::exceptions::Exception);
create_exception!(pycctx, TxBadVersion, pyo3::exceptions::Exception);



pub fn setup_module(py: Python, m: &PyModule) -> PyResult<()> {
    m.add("DecodeError", py.get_type::<DecodeError>())?;
    m.add("TxSignError", py.get_type::<TxSignError>())?;
    m.add("TxNotSigned", py.get_type::<TxNotSigned>())?;
    m.add("TxBadVersion", py.get_type::<TxBadVersion>())?;
    Ok(())
}
