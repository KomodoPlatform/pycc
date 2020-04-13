
// use pyo3::{exceptions, prelude::*, types::{PyBytes, PyDict}, wrap_pyfunction};
// 
// 
// 
// #[pyclass]
// pub struct Private {
//     secret: kk::Private
// }
// 
// #[pymethods]
// impl Private {
// }
// 
// 
// struct Address {
//     address: kk::Address
// }

use primitives::hash as hash;

pub fn to_kmd_address(hash: hash::H160) -> kk::Address {
    kk::Address {
        prefix: 60,
        t_addr_prefix: 0,
        hash,
        checksum_type: bitcrypto::ChecksumType::DSHA256
    }
}
