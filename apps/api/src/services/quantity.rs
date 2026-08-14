//! Quantity helpers shared by route handlers (Spec §5, §6, §10).

use crate::models::MeasurementType;

/// Round a quantity to the precision defined for its unit of measure (Spec §10).
/// Mirrors UOM_PRECISION in @openbuild/types so app and exports agree.
pub fn round_quantity(value: f64, uom: &str) -> f64 {
    let precision: i32 = match uom.to_lowercase().as_str() {
        "ea" | "lb" | "gal" | "mm" => 0,
        "m" => 3,
        _ => 2,
    };
    let factor = 10f64.powi(precision);
    (value * factor).round() / factor
}

/// The unit of measure a measurement must carry (Spec §5).
///
/// Calibrated quantities are derived in the calibration's display unit:
/// linear quantities carry the display unit itself, areas its squared
/// companion. Counts are always "ea" regardless of calibration. Returns
/// None when there is no expectation to enforce (volume, or a
/// linear/area measurement with no calibration to define real units).
pub fn expected_uom(
    measurement_type: &MeasurementType,
    display_unit: Option<&str>,
) -> Option<&'static str> {
    match measurement_type {
        MeasurementType::Count => Some("ea"),
        MeasurementType::Volume => None,
        MeasurementType::Linear => match display_unit? {
            "ft" => Some("ft"),
            "in" => Some("in"),
            "m" => Some("m"),
            "mm" => Some("mm"),
            _ => None,
        },
        MeasurementType::Area => match display_unit? {
            "ft" => Some("sf"),
            "in" => Some("sqin"),
            "m" => Some("sm"),
            "mm" => Some("sqmm"),
            _ => None,
        },
    }
}
