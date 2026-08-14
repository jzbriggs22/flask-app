-- CSI MasterFormat 2016 Division-level cost codes
-- Seed data for the unit cost database

-- Note: This table would be part of a future migration when we add
-- a dedicated cost_codes table. For MVP, cost codes are stored as
-- strings on line items and validated client-side.

-- Sample unit costs for demonstration (regional: US National Average)
-- All costs in cents (integer arithmetic only)

-- This file serves as reference data for the MVP.
-- In production, this would be loaded into a cost_codes table with:
--   code TEXT PRIMARY KEY,
--   title TEXT NOT NULL,
--   default_unit TEXT,
--   default_unit_cost_cents BIGINT,
--   region TEXT,
--   year INTEGER

-- Division 03 - Concrete
-- 03 30 00 Cast-in-Place Concrete: ~$150-250/CY installed
-- 03 20 00 Concrete Reinforcing: ~$0.80-1.20/LB
-- 03 10 00 Concrete Forming: ~$3.50-6.00/SF

-- Division 04 - Masonry
-- 04 20 00 CMU Block (8"): ~$12-18/SF installed

-- Division 05 - Metals
-- 05 10 00 Structural Steel: ~$3,000-5,000/TON installed
-- 05 30 00 Metal Decking: ~$4-7/SF

-- Division 07 - Thermal & Moisture Protection
-- 07 50 00 Membrane Roofing (TPO): ~$8-14/SF
-- 07 20 00 Insulation (rigid): ~$2-5/SF

-- Division 08 - Openings
-- 08 10 00 Hollow Metal Door & Frame: ~$800-1,500/EA
-- 08 50 00 Aluminum Window: ~$35-65/SF

-- Division 09 - Finishes
-- 09 20 00 Gypsum Board (5/8"): ~$2.50-4.00/SF
-- 09 30 00 Ceramic Tile: ~$8-15/SF
-- 09 60 00 VCT Flooring: ~$3-5/SF
-- 09 90 00 Paint (2 coats): ~$1.50-3.00/SF

-- Division 22 - Plumbing
-- 22 40 00 Water Closet: ~$400-800/EA
-- 22 40 00 Lavatory: ~$300-600/EA

-- Division 26 - Electrical
-- 26 50 00 2x4 LED Troffer: ~$200-400/EA
-- 26 05 00 Duplex Receptacle: ~$80-150/EA

-- Division 31 - Earthwork
-- 31 20 00 Excavation: ~$8-15/CY
-- 31 20 00 Fill and Compaction: ~$12-20/CY

-- Division 32 - Exterior
-- 32 10 00 Asphalt Paving: ~$4-8/SF
-- 32 10 00 Concrete Sidewalk: ~$6-10/SF
