/**
 * CSI MasterFormat 2016 cost code structure.
 *
 * MasterFormat is the industry-standard classification system for organizing
 * construction specifications and cost data. It uses a hierarchical numbering
 * scheme: Division (2 digits) → Section (6 digits) → Subsection.
 *
 * The MVP includes Division-level codes. Full section-level detail
 * will be added as the cost database grows.
 */

export interface CostCodeDivision {
  code: string;
  title: string;
  description: string;
}

export interface CostCodeSection {
  code: string;
  title: string;
  divisionCode: string;
}

/**
 * CSI MasterFormat 2016 Divisions (Level 1).
 * Covers all 49 divisions used in commercial construction.
 */
export const CSI_DIVISIONS: CostCodeDivision[] = [
  // Procurement & Contracting Requirements Group
  { code: "00", title: "Procurement and Contracting Requirements", description: "Bidding requirements, contracting forms, conditions" },

  // Specifications Group - General Requirements
  { code: "01", title: "General Requirements", description: "Summary, price & payment, admin, quality, temporary facilities" },

  // Specifications Group - Facility Construction
  { code: "02", title: "Existing Conditions", description: "Assessment, demolition, remediation" },
  { code: "03", title: "Concrete", description: "Concrete forming, reinforcing, casting, precast" },
  { code: "04", title: "Masonry", description: "Unit masonry, stone, assemblies" },
  { code: "05", title: "Metals", description: "Structural steel, joists, decking, cold-formed framing" },
  { code: "06", title: "Wood, Plastics, and Composites", description: "Rough carpentry, finish carpentry, millwork" },
  { code: "07", title: "Thermal and Moisture Protection", description: "Waterproofing, insulation, roofing, siding" },
  { code: "08", title: "Openings", description: "Doors, windows, hardware, glazing" },
  { code: "09", title: "Finishes", description: "Plaster, gypsum board, tiling, flooring, painting" },
  { code: "10", title: "Specialties", description: "Signage, lockers, partitions, toilet accessories" },
  { code: "11", title: "Equipment", description: "Commercial, institutional, residential equipment" },
  { code: "12", title: "Furnishings", description: "Art, window treatments, casework, seating" },
  { code: "13", title: "Special Construction", description: "Pre-engineered structures, pools, ice rinks" },
  { code: "14", title: "Conveying Equipment", description: "Elevators, escalators, lifts, hoists" },

  // Specifications Group - Facility Services
  { code: "21", title: "Fire Suppression", description: "Fire-suppression sprinkler systems, standpipes" },
  { code: "22", title: "Plumbing", description: "Plumbing piping, fixtures, equipment" },
  { code: "23", title: "Heating, Ventilating, and Air Conditioning (HVAC)", description: "HVAC piping, ducts, equipment" },
  { code: "25", title: "Integrated Automation", description: "Facility system control, BAS integration" },
  { code: "26", title: "Electrical", description: "Medium/low voltage distribution, lighting, grounding" },
  { code: "27", title: "Communications", description: "Data, voice, audio-video, electronic safety" },
  { code: "28", title: "Electronic Safety and Security", description: "Access control, surveillance, detection" },

  // Specifications Group - Site and Infrastructure
  { code: "31", title: "Earthwork", description: "Site clearing, grading, excavation, fill" },
  { code: "32", title: "Exterior Improvements", description: "Paving, curbs, fences, landscaping, irrigation" },
  { code: "33", title: "Utilities", description: "Water, sanitary, storm, electrical, gas utilities" },
  { code: "34", title: "Transportation", description: "Roadways, railways, bridges" },
  { code: "35", title: "Waterway and Marine Construction", description: "Waterway, coastal, dam construction" },

  // Specifications Group - Process Equipment
  { code: "40", title: "Process Interconnections", description: "Process piping, instrumentation" },
  { code: "41", title: "Material Processing and Handling Equipment", description: "Crushers, conveyors, storage" },
  { code: "42", title: "Process Heating, Cooling, and Drying Equipment", description: "Boilers, furnaces, dryers" },
  { code: "43", title: "Process Gas and Liquid Handling, Purification, and Storage Equipment", description: "Gas/liquid processing" },
  { code: "44", title: "Pollution and Waste Control Equipment", description: "Air/water purification, waste handling" },
  { code: "45", title: "Industry-Specific Manufacturing Equipment", description: "Manufacturing-specific equipment" },
  { code: "46", title: "Water and Wastewater Equipment", description: "Water/wastewater treatment" },
  { code: "48", title: "Electrical Power Generation", description: "Power generation equipment" },
];

/**
 * Common CSI sections used in commercial construction (Level 2).
 * This is a subset — the full database has 1000+ sections.
 */
export const CSI_COMMON_SECTIONS: CostCodeSection[] = [
  // Division 03 - Concrete
  { code: "03 10 00", title: "Concrete Forming and Accessories", divisionCode: "03" },
  { code: "03 20 00", title: "Concrete Reinforcing", divisionCode: "03" },
  { code: "03 30 00", title: "Cast-in-Place Concrete", divisionCode: "03" },
  { code: "03 40 00", title: "Precast Concrete", divisionCode: "03" },

  // Division 04 - Masonry
  { code: "04 20 00", title: "Unit Masonry", divisionCode: "04" },
  { code: "04 40 00", title: "Stone Assemblies", divisionCode: "04" },

  // Division 05 - Metals
  { code: "05 10 00", title: "Structural Metal Framing", divisionCode: "05" },
  { code: "05 20 00", title: "Metal Joists", divisionCode: "05" },
  { code: "05 30 00", title: "Metal Decking", divisionCode: "05" },
  { code: "05 50 00", title: "Metal Fabrications", divisionCode: "05" },

  // Division 06 - Wood
  { code: "06 10 00", title: "Rough Carpentry", divisionCode: "06" },
  { code: "06 20 00", title: "Finish Carpentry", divisionCode: "06" },

  // Division 07 - Thermal & Moisture
  { code: "07 10 00", title: "Dampproofing and Waterproofing", divisionCode: "07" },
  { code: "07 20 00", title: "Thermal Protection", divisionCode: "07" },
  { code: "07 50 00", title: "Membrane Roofing", divisionCode: "07" },
  { code: "07 60 00", title: "Flashing and Sheet Metal", divisionCode: "07" },

  // Division 08 - Openings
  { code: "08 10 00", title: "Doors and Frames", divisionCode: "08" },
  { code: "08 40 00", title: "Entrances, Storefronts, and Curtain Walls", divisionCode: "08" },
  { code: "08 50 00", title: "Windows", divisionCode: "08" },
  { code: "08 70 00", title: "Hardware", divisionCode: "08" },

  // Division 09 - Finishes
  { code: "09 20 00", title: "Plaster and Gypsum Board", divisionCode: "09" },
  { code: "09 30 00", title: "Tiling", divisionCode: "09" },
  { code: "09 60 00", title: "Flooring", divisionCode: "09" },
  { code: "09 90 00", title: "Painting and Coating", divisionCode: "09" },

  // Division 22 - Plumbing
  { code: "22 10 00", title: "Plumbing Piping and Pumps", divisionCode: "22" },
  { code: "22 40 00", title: "Plumbing Fixtures", divisionCode: "22" },

  // Division 23 - HVAC
  { code: "23 30 00", title: "HVAC Air Distribution", divisionCode: "23" },
  { code: "23 60 00", title: "Central Cooling Equipment", divisionCode: "23" },
  { code: "23 70 00", title: "Central HVAC Equipment", divisionCode: "23" },

  // Division 26 - Electrical
  { code: "26 05 00", title: "Common Work Results for Electrical", divisionCode: "26" },
  { code: "26 20 00", title: "Low-Voltage Electrical Power Generation and Storage", divisionCode: "26" },
  { code: "26 50 00", title: "Lighting", divisionCode: "26" },

  // Division 31 - Earthwork
  { code: "31 10 00", title: "Site Clearing", divisionCode: "31" },
  { code: "31 20 00", title: "Earth Moving", divisionCode: "31" },

  // Division 32 - Exterior
  { code: "32 10 00", title: "Bases, Ballasts, and Paving", divisionCode: "32" },
  { code: "32 90 00", title: "Planting", divisionCode: "32" },

  // Division 33 - Utilities
  { code: "33 10 00", title: "Water Utilities", divisionCode: "33" },
  { code: "33 30 00", title: "Sanitary Sewerage", divisionCode: "33" },
  { code: "33 40 00", title: "Storm Drainage", divisionCode: "33" },
];

/**
 * Look up a division by code.
 */
export function getDivision(code: string): CostCodeDivision | undefined {
  return CSI_DIVISIONS.find((d) => d.code === code);
}

/**
 * Get all sections for a given division code.
 */
export function getSectionsForDivision(divisionCode: string): CostCodeSection[] {
  return CSI_COMMON_SECTIONS.filter((s) => s.divisionCode === divisionCode);
}

/**
 * Search cost codes by keyword.
 */
export function searchCostCodes(query: string): (CostCodeDivision | CostCodeSection)[] {
  const lower = query.toLowerCase();
  const divisions = CSI_DIVISIONS.filter(
    (d) =>
      d.code.includes(lower) ||
      d.title.toLowerCase().includes(lower) ||
      d.description.toLowerCase().includes(lower)
  );
  const sections = CSI_COMMON_SECTIONS.filter(
    (s) =>
      s.code.includes(lower) ||
      s.title.toLowerCase().includes(lower)
  );
  return [...divisions, ...sections];
}

/**
 * Common construction units of measure.
 */
export const UNITS = [
  { abbr: "LF", name: "Linear Feet" },
  { abbr: "SF", name: "Square Feet" },
  { abbr: "SY", name: "Square Yards" },
  { abbr: "CY", name: "Cubic Yards" },
  { abbr: "EA", name: "Each" },
  { abbr: "TON", name: "Ton" },
  { abbr: "LB", name: "Pound" },
  { abbr: "GAL", name: "Gallon" },
  { abbr: "HR", name: "Hour" },
  { abbr: "DAY", name: "Day" },
  { abbr: "LS", name: "Lump Sum" },
  { abbr: "MBF", name: "Thousand Board Feet" },
  { abbr: "CLF", name: "Hundred Linear Feet" },
  { abbr: "CSF", name: "Hundred Square Feet" },
] as const;
