/// PDF processing service.
///
/// Handles:
/// - PDF page counting and metadata extraction
/// - Thumbnail generation for sheet navigation
/// - Page rendering for the viewer (server-side fallback)
///
/// Construction drawings can be 100+ MB with 500+ sheets.
/// All processing must be memory-efficient and streaming.

use anyhow::Result;

/// Extract metadata from a PDF file.
pub struct PdfMetadata {
    pub page_count: usize,
    pub title: Option<String>,
    pub file_size: u64,
}

/// Process an uploaded PDF drawing set.
///
/// 1. Store the original in S3/MinIO
/// 2. Extract page count and metadata
/// 3. Generate thumbnails for each page
/// 4. Return metadata for the database record
pub async fn process_drawing_upload(
    _file_data: &[u8],
    _file_name: &str,
) -> Result<PdfMetadata> {
    // TODO: Implement PDF processing
    // Use lopdf for page counting
    // Use image crate for thumbnail generation
    Ok(PdfMetadata {
        page_count: 0,
        title: None,
        file_size: _file_data.len() as u64,
    })
}
