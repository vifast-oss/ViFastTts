//! Port lấy model bytes; không biết filesystem, HTTP hay cache cụ thể.

#[derive(Clone, Debug)]
pub struct ModelBytes {
    pub acoustic: Vec<u8>,
    pub vocoder: Vec<u8>,
}

pub trait ModelSource {
    fn load(&self) -> Result<ModelBytes, String>;
}
